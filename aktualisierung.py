#!/usr/bin/env python3
"""Nachsehen, ob eine neuere Fassung bereitliegt, und sie holen.

Bezugsquelle sind die Releases des Projekts auf GitHub. Dort hängen an jeder
Version zwei Dateien:

    Wasserzeichen-<version>-Setup.exe   die vollständige Installation
    app-<version>.zip                   nur der Programmcode, rund 30 KB

Der Normalfall ist das kleine Paket: Es wird als „app.neu“ neben dem Programm
abgelegt, den Rest erledigt start.py beim nächsten Start. Damit wird nie eine
Datei ersetzt, die gerade in Benutzung ist, und weil keine ausführbare Datei
angefasst wird, meldet sich auch Windows nicht mit einer Sicherheitswarnung.

Braucht eine neue Fassung eine zusätzliche Bibliothek, reicht das kleine Paket
nicht — dann fehlt das ZIP am Release und es wird auf die Setup-Datei verwiesen.

Ohne Netz oder bei jedem anderen Fehler passiert schlicht nichts: Das Programm
ist zum Arbeiten da, nicht zum Aktualisieren.
"""
import json
import os
import re
import shutil
import ssl
import tempfile
import urllib.error
import urllib.request
import zipfile

BENUTZER = "MarkusAureliusII"
PROJEKT = "wasserzeichen-werkstatt"

API = f"https://api.github.com/repos/{BENUTZER}/{PROJEKT}/releases"
SEITE = f"https://github.com/{BENUTZER}/{PROJEKT}/releases/latest"

ZEITLIMIT = 10          # Sekunden — lieber kein Update als ein hängendes Fenster
GROESSTMASS = 20 << 20  # 20 MB; das Paket ist ~30 KB, alles darüber ist Unfug


class KeinUpdate(Exception):
    """Nichts zu tun oder nicht erreichbar — beides kein Grund zur Aufregung."""


# ------------------------------------------------------------- Versionsvergleich

def _teile(version):
    """„1.2.3-beta.4“ -> ((1, 2, 3), ('beta', 4)). Unbrauchbares -> None."""
    treffer = re.match(r"^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.]+))?$", version.strip())
    if not treffer:
        return None
    zahlen = tuple(int(treffer.group(i)) for i in (1, 2, 3))
    rest = treffer.group(4)
    if not rest:
        return zahlen, ()
    stufen = tuple(int(t) if t.isdigit() else t for t in rest.split("."))
    return zahlen, stufen


def ist_neuer(kandidat, laufend):
    """Ist „kandidat“ neuer als „laufend“? Nach den üblichen Versionsregeln.

    Entscheidend ist die Sonderregel für Vorabversionen: 1.0.0-beta.3 ist
    ÄLTER als 1.0.0, obwohl die Zeichenkette länger ist.
    """
    a, b = _teile(kandidat), _teile(laufend)
    if a is None or b is None:
        return False
    if a[0] != b[0]:
        return a[0] > b[0]

    a_vorab, b_vorab = a[1], b[1]
    if not a_vorab and not b_vorab:
        return False
    if not a_vorab:          # fertige Fassung schlägt Vorabversion
        return True
    if not b_vorab:
        return False

    for x, y in zip(a_vorab, b_vorab):
        if x == y:
            continue
        # Zahlen gelten als kleiner als Wörter, wie bei Versionsnummern üblich
        if isinstance(x, int) and isinstance(y, int):
            return x > y
        if isinstance(x, int):
            return False
        if isinstance(y, int):
            return True
        return x > y
    return len(a_vorab) > len(b_vorab)


# ------------------------------------------------------------------ Nachsehen

def _zertifikate():
    """Prüfstelle für HTTPS.

    Weder ein gepacktes Python unter Windows noch eines auf macOS greift auf den
    Zertifikatsspeicher des Systems zu — ohne certifi scheitert jede Verbindung
    mit „certificate verify failed“. Darum liegt certifi im Build bei.
    """
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _abrufen(url, roh=False):
    anfrage = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": f"{PROJEKT}-updater",
    })
    zusammenhang = _zertifikate()
    with urllib.request.urlopen(anfrage, timeout=ZEITLIMIT, context=zusammenhang) as antwort:
        laenge = antwort.headers.get("Content-Length")
        if laenge and int(laenge) > GROESSTMASS:
            raise KeinUpdate("Das Paket ist unerwartet groß.")
        daten = antwort.read(GROESSTMASS + 1)
    if len(daten) > GROESSTMASS:
        raise KeinUpdate("Das Paket ist unerwartet groß.")
    return daten if roh else json.loads(daten.decode("utf-8"))


def nachsehen(laufende_version):
    """Gibt die Angaben zur neuesten Fassung zurück oder wirft KeinUpdate.

    Wer eine Vorabversion einsetzt, bekommt auch Vorabversionen angeboten —
    wer eine fertige Fassung nutzt, nur fertige.
    """
    vorab_erlaubt = "-" in laufende_version

    try:
        veroeffentlichungen = _abrufen(API)
    except (urllib.error.URLError, OSError, ValueError, TimeoutError) as e:
        raise KeinUpdate(f"nicht erreichbar: {e}")

    bester = None
    for v in veroeffentlichungen:
        if v.get("draft"):
            continue
        if v.get("prerelease") and not vorab_erlaubt:
            continue
        nummer = (v.get("tag_name") or "").lstrip("v")
        if not _teile(nummer):
            continue
        if not ist_neuer(nummer, laufende_version):
            continue
        if bester is None or ist_neuer(nummer, bester["version"]):
            paket = next((a["browser_download_url"] for a in v.get("assets", [])
                          if a["name"] == f"app-{nummer}.zip"), None)
            bester = {
                "version": nummer,
                "paket": paket,             # None -> nur als Vollversion zu haben
                "seite": v.get("html_url") or SEITE,
            }

    if bester is None:
        raise KeinUpdate("Das Programm ist auf dem neuesten Stand.")
    return bester


# --------------------------------------------------------------------- Holen

def herunterladen(auskunft, programmordner):
    """Das kleine Paket holen und als „app.neu“ bereitlegen.

    Eingesetzt wird es erst beim nächsten Start durch start.py — dann ist keine
    Datei daraus in Benutzung. Rückgabe: der Pfad des bereitgelegten Ordners.
    """
    if not auskunft.get("paket"):
        raise KeinUpdate("Diese Fassung gibt es nur als vollständige Installation.")

    ziel = os.path.join(programmordner, "app.neu")
    arbeitsordner = tempfile.mkdtemp(prefix="wz-update-", dir=programmordner)

    try:
        daten = _abrufen(auskunft["paket"], roh=True)

        archiv = os.path.join(arbeitsordner, "app.zip")
        with open(archiv, "wb") as f:
            f.write(daten)

        # Vor dem Einsetzen prüfen, ob das Archiv überhaupt heil ist.
        with zipfile.ZipFile(archiv) as z:
            if z.testzip() is not None:
                raise KeinUpdate("Das heruntergeladene Paket ist beschädigt.")
            namen = z.namelist()
            if not any(n.endswith("oberflaeche.py") for n in namen):
                raise KeinUpdate("Das Paket ist unvollständig.")
            for n in namen:
                # Keine Pfade, die aus dem Zielordner herausführen.
                if os.path.isabs(n) or ".." in n.replace("\\", "/").split("/"):
                    raise KeinUpdate("Das Paket enthält unerwartete Pfade.")
            entpackt = os.path.join(arbeitsordner, "app")
            z.extractall(entpackt)

        shutil.rmtree(ziel, ignore_errors=True)
        os.rename(entpackt, ziel)
        return ziel

    except KeinUpdate:
        raise
    except (urllib.error.URLError, OSError, ValueError, zipfile.BadZipFile) as e:
        raise KeinUpdate(f"Herunterladen fehlgeschlagen: {e}")
    finally:
        shutil.rmtree(arbeitsordner, ignore_errors=True)


def bereitgelegt(programmordner):
    """Liegt schon ein Update fertig, das nur noch auf den Neustart wartet?"""
    return os.path.isdir(os.path.join(programmordner, "app.neu"))
