#!/usr/bin/env python3
"""Wasserzeichen-Werkstatt — Logo stapelweise in Fotos und Videos einbrennen.

Normale Bedienung läuft über das Fenster (oberflaeche.py) — Doppelklick auf
„Wasserzeichen.command" bzw. „Wasserzeichen.exe". Diese Datei ist der Motor
darunter und lässt sich zusätzlich direkt aufrufen:

  python3 wasserzeichen.py alles                verarbeitet alles aus input/
  python3 wasserzeichen.py logo <screenshot>    neues Logo freistellen -> wasserzeichen.png
  python3 wasserzeichen.py fotos <bild...>      einzelne Fotos stempeln
  python3 wasserzeichen.py video <video...>     einzelne Videos stempeln (nacheinander)

Jeder Durchgang bekommt einen eigenen Ordner mit Datum und Uhrzeit, darin getrennt
nach Art:  output/24.07.2026 15-12 Uhr/fotos/  bzw.  .../videos/ . Verarbeitete
Originale wandern nach  input/erledigt/  — nichts wird gelöscht.

Läuft unter macOS und Windows aus derselben Datei: unter Windows werden
ffmpeg.exe/ffprobe.exe aus dem Tool-Ordner genutzt und RAW über rawpy gelesen.
"""
import json, os, re, shutil, subprocess, sys
from datetime import datetime
from PIL import Image, ImageDraw, ImageOps

try:
    import pillow_heif
    pillow_heif.register_heif_opener()  # iPhone-HEIC lesbar machen
except ImportError:
    pass

IST_WINDOWS = sys.platform.startswith("win")

# Zwei getrennte Orte, weil ein Update den Programmordner austauscht:
#
#   PROG_DIR   exe, ffmpeg, app/ — wird bei Updates überschrieben, nichts von Wert darin
#   DATEN_DIR  Fotos, Logo, Einstellungen — bleibt bei Updates unangetastet
#
# Bei einer PyInstaller-exe liegt der Programmordner neben der exe, nicht im _internal/;
# die Nutzdaten stehen dann in „Dokumente/Wasserzeichen", wo der Nutzer sie auch findet.
# Im Entwicklerbetrieb (Skript direkt gestartet) bleibt beides zusammen wie bisher.
if getattr(sys, "frozen", False):
    PROG_DIR = os.path.dirname(os.path.abspath(sys.executable))
    DATEN_DIR = os.path.join(os.path.expanduser("~"), "Documents", "Wasserzeichen")
    os.makedirs(DATEN_DIR, exist_ok=True)
else:
    PROG_DIR = os.path.dirname(os.path.abspath(__file__))
    DATEN_DIR = PROG_DIR


def _version_lesen():
    """Versionsnummer aus version.txt neben diesem Modul — eine Quelle für alle."""
    pfad = os.path.join(os.path.dirname(os.path.abspath(__file__)), "version.txt")
    try:
        with open(pfad, encoding="utf-8") as f:
            return f.read().strip() or "0.0.0"
    except OSError:
        return "0.0.0"


VERSION = _version_lesen()

WZ_PATH = os.path.join(DATEN_DIR, "wasserzeichen.png")
EINST_PATH = os.path.join(DATEN_DIR, "einstellungen.json")
BESCHR_PATH = os.path.join(DATEN_DIR, "beschriftung.json")
IN_DIR = os.path.join(DATEN_DIR, "input")
DONE_DIR = os.path.join(IN_DIR, "erledigt")
OUT_DIR = os.path.join(DATEN_DIR, "output")
LAUF_MUSTER = re.compile(r"^\d{2}\.\d{2}\.\d{4} \d{2}-\d{2} Uhr")  # 24.07.2026 15-12 Uhr

FOTO_ENDUNGEN = {".jpg", ".jpeg", ".png", ".heic", ".webp", ".tif", ".tiff"}
RAW_ENDUNGEN = {".arw", ".cr2", ".cr3", ".nef", ".dng", ".raf", ".orf", ".rw2"}  # Sony .arw etc.
VIDEO_ENDUNGEN = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".mts", ".m2ts",  # Sony XAVC S / AVCHD
                  ".webm", ".mpg", ".mpeg", ".wmv", ".3gp"}

ECKEN = ["oben-links", "oben-rechts", "unten-links", "unten-rechts"]

STANDARD = {
    "ecke": "unten-rechts",
    "breite_prozent": 24.0,     # Logobreite relativ zur Bildbreite
    "rand_prozent": 2.5,        # Abstand zur Ecke relativ zur Bildbreite
    "deckkraft_prozent": 95.0,  # 100 = voll deckend
    "jpeg_qualitaet": 92,
}

# Aufschriften im Fenster. Wer das Tool nutzt, steht in beschriftung.json neben
# dem Programm — nicht hier, damit der Quelltext ohne Kundenbezug bleibt.
BESCHRIFTUNG = {
    "fenstertitel": "Wasserzeichen",
    "untertitel": "",
    "marke": "",
}

ECKRADIUS_ANTEIL = 0.16  # relativ zur Kachelhöhe — nur beim Logo-Freistellen
PADDING_ANTEIL = 0.05    # Innenabstand relativ zur Kachelbreite


class WerkstattFehler(Exception):
    """Fehler, den der Benutzer versteht und selbst beheben kann."""


def _klartext(e):
    """Technische Ausnahmen in einen Satz übersetzen, der dem Nutzer weiterhilft."""
    if isinstance(e, WerkstattFehler):
        return str(e)
    name = type(e).__name__
    if name == "UnidentifiedImageError":
        return "Die Datei ist beschädigt oder gar kein Bild."
    if isinstance(e, PermissionError):
        return "Keine Berechtigung für die Datei — ist sie noch in einem anderen Programm offen?"
    if isinstance(e, FileNotFoundError):
        return "Die Datei war plötzlich nicht mehr da."
    if isinstance(e, subprocess.CalledProcessError):
        return "Die Datei konnte nicht umgewandelt werden (beschädigt oder unbekanntes Format)."
    if isinstance(e, OSError) and getattr(e, "errno", None) == 28:
        return "Kein Speicherplatz mehr auf der Festplatte."
    return f"Unerwarteter Fehler ({name}): {e}"


# ---------------------------------------------------------------- Einstellungen

def einstellungen_laden():
    """Gespeicherte Werte lesen; unbekannte/kaputte Angaben fallen auf Standard zurück."""
    werte = dict(STANDARD)
    try:
        with open(EINST_PATH, encoding="utf-8") as f:
            gespeichert = json.load(f)
    except (OSError, ValueError):
        return werte
    for schluessel, standard in STANDARD.items():
        wert = gespeichert.get(schluessel, standard)
        if schluessel == "ecke":
            werte[schluessel] = wert if wert in ECKEN else standard
        else:
            try:
                werte[schluessel] = type(standard)(wert)
            except (TypeError, ValueError):
                werte[schluessel] = standard
    return werte


def einstellungen_speichern(werte):
    with open(EINST_PATH, "w", encoding="utf-8") as f:
        json.dump(werte, f, indent=2, ensure_ascii=False)


def beschriftung_laden():
    """Aufschriften aus beschriftung.json; fehlt die Datei, bleibt es beim neutralen Text."""
    werte = dict(BESCHRIFTUNG)
    try:
        with open(BESCHR_PATH, encoding="utf-8") as f:
            gespeichert = json.load(f)
    except (OSError, ValueError):
        return werte
    for schluessel in BESCHRIFTUNG:
        wert = gespeichert.get(schluessel)
        if isinstance(wert, str) and wert.strip():
            werte[schluessel] = wert.strip()
    return werte


# ---------------------------------------------------------------- Läufe

def _jetzt():
    """Deutsche Ortszeit. Fällt auf die Systemzeit zurück, falls die Zeitzonen-Daten
    fehlen — unter Windows bringt Python sie nicht selbst mit."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Europe/Berlin"))
    except Exception:
        return datetime.now()


def neuer_lauf():
    """Ordner für diesen Durchgang: output/24.07.2026 15-12 Uhr/ — deutsches Datum, auf
    einen Blick lesbar. Der Doppelpunkt der Uhrzeit ist durch einen Bindestrich
    ersetzt, weil Windows ihn in Dateinamen nicht erlaubt."""
    stempel = _jetzt().strftime("%d.%m.%Y %H-%M Uhr")
    pfad = os.path.join(OUT_DIR, stempel)
    zaehler = 2
    while os.path.exists(pfad):  # zweiter Durchgang in derselben Minute
        pfad = os.path.join(OUT_DIR, f"{stempel} ({zaehler})")
        zaehler += 1
    os.makedirs(pfad, exist_ok=True)
    return pfad


def letzter_lauf():
    """Jüngster Lauf-Ordner, sonst None — für den Knopf „Ergebnisse öffnen".
    Sortiert nach Änderungszeit, nicht nach Name: das deutsche Datumsformat
    beginnt mit dem Tag und ließe sich alphabetisch nicht chronologisch ordnen."""
    try:
        laeufe = [os.path.join(OUT_DIR, f) for f in os.listdir(OUT_DIR)
                  if LAUF_MUSTER.match(f) and os.path.isdir(os.path.join(OUT_DIR, f))]
    except OSError:
        return None
    return max(laeufe, key=os.path.getmtime) if laeufe else None


def _zielordner(lauf, art):
    """Fotos und Videos innerhalb eines Laufs trennen; nur anlegen, was gebraucht wird."""
    ordner = os.path.join(lauf or neuer_lauf(), art)
    os.makedirs(ordner, exist_ok=True)
    return ordner


# ---------------------------------------------------------------- Plattform

def _werkzeug(name):
    """ffmpeg/ffprobe finden: erst neben dem Tool (Windows-Übergabe), dann im System-PATH."""
    lokal = os.path.join(PROG_DIR, name + (".exe" if IST_WINDOWS else ""))
    if os.path.isfile(lokal):
        return lokal
    gefunden = shutil.which(name)
    if gefunden:
        return gefunden
    raise WerkstattFehler(
        f"'{name}' wurde nicht gefunden. Bitte {name}{'.exe' if IST_WINDOWS else ''} "
        f"in den Ordner des Programms legen — ohne das Programm gehen keine Videos.")


def _raw_oeffnen(pfad):
    """Sony .arw & Co. — macOS über sips (CoreImage), Windows über rawpy."""
    if IST_WINDOWS:
        try:
            import rawpy
        except ImportError:
            raise WerkstattFehler("Für RAW-Dateien fehlt das Modul 'rawpy'.")
        with rawpy.imread(pfad) as raw:
            return Image.fromarray(raw.postprocess())
    tmp = os.path.join(DATEN_DIR, ".raw_tmp.jpg")
    subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "95",
                    pfad, "--out", tmp], check=True, capture_output=True)
    img = Image.open(tmp)
    img.load()
    os.remove(tmp)
    return img


def _video_encoder():
    """Mac: Hardware-Encoder. Windows: libx264 (läuft überall, keine Treiberabhängigkeit)."""
    if IST_WINDOWS:
        return ["-c:v", "libx264", "-preset", "medium", "-pix_fmt", "yuv420p"]
    return ["-c:v", "h264_videotoolbox"]


# ---------------------------------------------------------------- Logo

def logo_freistellen(screenshot_pfad):
    """Logo aus einem Screenshot schneiden und als weiße Kachel mit runden Ecken sichern."""
    img = Image.open(screenshot_pfad).convert("L")
    w, h = img.size
    px = img.load()
    zeilen_hell = [sum(px[x, y] for x in range(0, w, 8)) / (w // 8) for y in range(h)]
    helle = [y for y, v in enumerate(zeilen_hell) if v > 200]
    if not helle:
        raise WerkstattFehler("Keine weiße Zone im Screenshot gefunden.")
    weiss = img.crop((0, min(helle), w, max(helle) + 1))
    invertiert = ImageOps.invert(weiss)
    schwelle = invertiert.point(lambda v: 255 if v > 60 else 0)
    bbox = schwelle.getbbox()
    if not bbox:
        raise WerkstattFehler("Kein Logo in der weißen Zone gefunden.")
    logo = weiss.crop(bbox).convert("RGBA")
    lw, lh = logo.size
    pad = int(lw * PADDING_ANTEIL)
    kw, kh = lw + 2 * pad, lh + 2 * pad
    kachel = Image.new("RGBA", (kw, kh), (255, 255, 255, 255))
    kachel.paste(logo, (pad, pad))
    radius = int(kh * ECKRADIUS_ANTEIL)
    maske = Image.new("L", (kw, kh), 0)
    # Volle Deckkraft in der Datei — die gewünschte Transparenz kommt erst beim Stempeln
    ImageDraw.Draw(maske).rounded_rectangle([0, 0, kw - 1, kh - 1], radius=radius, fill=255)
    kachel.putalpha(maske)
    kachel.save(WZ_PATH)
    return f"Wasserzeichen gebaut: {WZ_PATH} ({kw}x{kh}px)"


def _logo_skaliert(bild_breite, einst):
    """Logo auf Zielbreite bringen und die Deckkraft aus den Einstellungen anlegen."""
    if not os.path.isfile(WZ_PATH):
        raise WerkstattFehler(
            f"Das Logo fehlt: {WZ_PATH}\nBitte wasserzeichen.png in diesen Ordner legen.")
    wz = Image.open(WZ_PATH).convert("RGBA")
    ziel_b = max(1, int(bild_breite * einst["breite_prozent"] / 100))
    ziel_h = max(1, int(wz.height * ziel_b / wz.width))
    wz = wz.resize((ziel_b, ziel_h), Image.LANCZOS)
    # Alpha auf die Wunsch-Deckkraft normieren, egal wie transparent die Datei schon war;
    # die weichen Kanten der runden Ecken bleiben dabei proportional erhalten.
    alpha = wz.getchannel("A")
    hoechster = alpha.getextrema()[1] or 255
    faktor = (einst["deckkraft_prozent"] / 100) * 255 / hoechster
    wz.putalpha(alpha.point(lambda v: min(255, int(v * faktor))))
    return wz


def _ecken_position(bild_b, bild_h, wz_b, wz_h, einst):
    """Pixelposition der Logo-Ecke für Pillow."""
    rand = int(bild_b * einst["rand_prozent"] / 100)
    links = rand if einst["ecke"].endswith("links") else bild_b - wz_b - rand
    oben = rand if einst["ecke"].startswith("oben") else bild_h - wz_h - rand
    return links, oben


def _ecken_ausdruck(bild_b, einst):
    """Dasselbe als ffmpeg-overlay-Ausdruck (W/H = Video, w/h = Logo)."""
    rand = int(bild_b * einst["rand_prozent"] / 100)
    x = f"{rand}" if einst["ecke"].endswith("links") else f"W-w-{rand}"
    y = f"{rand}" if einst["ecke"].startswith("oben") else f"H-h-{rand}"
    return f"{x}:{y}"


# ---------------------------------------------------------------- Stempeln

def foto_bild(pfad, einst):
    """Foto laden und stempeln, ohne zu speichern — auch für die Vorschau im Fenster."""
    if os.path.splitext(pfad)[1].lower() in RAW_ENDUNGEN:
        img = _raw_oeffnen(pfad)
    else:
        img = Image.open(pfad)
    img = ImageOps.exif_transpose(img).convert("RGBA")
    wz = _logo_skaliert(img.width, einst)
    img.alpha_composite(wz, _ecken_position(img.width, img.height, wz.width, wz.height, einst))
    return img


def foto_stempeln(pfad, einst=None, lauf=None):
    einst = einst or einstellungen_laden()
    ordner = _zielordner(lauf, "fotos")
    img = foto_bild(pfad, einst)
    ziel = os.path.join(ordner, os.path.splitext(os.path.basename(pfad))[0] + "_wz.jpg")
    img.convert("RGB").save(ziel, quality=int(einst["jpeg_qualitaet"]))
    return ziel


def video_stempeln(pfad, einst=None, lauf=None):
    einst = einst or einstellungen_laden()
    ordner = _zielordner(lauf, "videos")
    probe = subprocess.run(
        [_werkzeug("ffprobe"), "-v", "quiet", "-select_streams", "v:0", "-show_entries",
         "stream=width,bit_rate", "-of", "csv=p=0", pfad], capture_output=True, text=True)
    zeilen = probe.stdout.strip().splitlines()
    if not zeilen:
        raise WerkstattFehler(f"Video nicht lesbar: {os.path.basename(pfad)}")
    werte = zeilen[0].rstrip(",").split(",")
    breite = int(werte[0])
    try:
        original_bps = int(werte[1])
    except (IndexError, ValueError):
        original_bps = 8_000_000  # z.B. VP9/mov ohne bit_rate-Angabe
    deckel = 40_000_000 if breite >= 3000 else 14_000_000  # 4K braucht mehr Luft
    ziel_bps = min(deckel, max(2_000_000, int(original_bps * 1.5)))
    wz = _logo_skaliert(breite, einst)
    wz_tmp = os.path.join(DATEN_DIR, ".wz_video_tmp.png")
    wz.save(wz_tmp)
    ziel = os.path.join(ordner, os.path.splitext(os.path.basename(pfad))[0] + "_wz.mp4")
    cmd = [_werkzeug("ffmpeg"), "-y", "-hide_banner", "-loglevel", "warning",
           "-i", pfad, "-i", wz_tmp,
           "-filter_complex", f"[0:v][1:v]overlay={_ecken_ausdruck(breite, einst)}",
           *_video_encoder(), "-b:v", str(ziel_bps),
           "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", ziel]
    try:
        subprocess.run(cmd, check=True)
    finally:
        if os.path.exists(wz_tmp):
            os.remove(wz_tmp)
    return ziel


# ---------------------------------------------------------------- Stapel

def input_dateien():
    """(Fotos, Videos, Unbekanntes) aus input/ — jeweils nur Dateinamen."""
    os.makedirs(IN_DIR, exist_ok=True)
    os.makedirs(DONE_DIR, exist_ok=True)
    dateien = sorted(f for f in os.listdir(IN_DIR)
                     if not f.startswith(".") and os.path.isfile(os.path.join(IN_DIR, f)))
    fotos, videos, rest = [], [], []
    for f in dateien:
        endung = os.path.splitext(f)[1].lower()
        if endung in FOTO_ENDUNGEN | RAW_ENDUNGEN:
            fotos.append(f)
        elif endung in VIDEO_ENDUNGEN:
            videos.append(f)
        else:
            rest.append(f)
    return fotos, videos, rest


def alles_verarbeiten(einst=None, melden=print, abbruch=None):
    """Alles aus input/ stempeln. Ein Fehler stoppt den Rest nicht.

    melden: Rückmeldung pro Schritt (Fenster oder Terminal).
    abbruch: Funktion, die True liefert, wenn der Benutzer abbrechen will.
    Rückgabe: (fertig, fehler, lauf) — fehler ist eine Liste (Dateiname, Grund),
    lauf der Ordner dieses Durchgangs (None, wenn nichts zu tun war).
    """
    einst = einst or einstellungen_laden()
    fotos, videos, rest = input_dateien()
    if not fotos and not videos:
        melden("Nichts zu tun — im Ordner input/ liegen keine Fotos oder Videos.")
        return 0, [], None
    gesamt = len(fotos) + len(videos)
    lauf = neuer_lauf()
    melden(f"Gefunden: {len(fotos)} Foto(s), {len(videos)} Video(s).")
    melden(f"Ergebnisse landen in output/{os.path.basename(lauf)}/")
    fertig, fehler = 0, []
    # Videos bewusst nacheinander und zuletzt, damit der Rechner benutzbar bleibt
    for art, name in [("Foto", f) for f in fotos] + [("Video", f) for f in videos]:
        if abbruch and abbruch():
            melden("Abgebrochen — der Rest bleibt in input/ liegen.")
            break
        pfad = os.path.join(IN_DIR, name)
        melden(f"[{fertig + len(fehler) + 1}/{gesamt}] {art}: {name}")
        try:
            ziel = (foto_stempeln(pfad, einst, lauf) if art == "Foto"
                    else video_stempeln(pfad, einst, lauf))
            shutil.move(pfad, os.path.join(DONE_DIR, name))
            melden(f"    fertig -> {os.path.basename(os.path.dirname(ziel))}/"
                   f"{os.path.basename(ziel)}")
            fertig += 1
        except Exception as e:  # eine kaputte Datei darf den Stapel nicht stoppen
            grund = _klartext(e)
            fehler.append((name, grund))
            melden(f"    FEHLER: {grund}")
    if rest:
        melden(f"Übersprungen (unbekanntes Format): {', '.join(rest)}")
    melden(f"Fertig: {fertig} von {gesamt}." + (f" {len(fehler)} Fehler." if fehler else ""))
    if not fertig:  # kein leerer Ordner, wenn nichts durchgelaufen ist
        try:
            os.rmdir(lauf)
        except OSError:
            pass
    return fertig, fehler, lauf


if __name__ == "__main__":
    args = sys.argv[1:]
    try:
        if not args or args[0] == "alles":
            alles_verarbeiten()
        elif args[0] == "logo" and len(args) > 1:
            print(logo_freistellen(args[1]))
        elif args[0] in ("fotos", "video") and len(args) > 1:
            lauf = neuer_lauf()  # ein Ordner für den ganzen Aufruf, nicht pro Datei
            stempeln = foto_stempeln if args[0] == "fotos" else video_stempeln
            for d in args[1:]:
                print(f"  {os.path.basename(d)} -> {stempeln(d, None, lauf)}")
        else:
            sys.exit(__doc__)
    except WerkstattFehler as e:
        sys.exit(str(e))
