#!/usr/bin/env python3
"""Fenster für die Wasserzeichen-Werkstatt — die Bedienoberfläche.

Start: Doppelklick auf „Wasserzeichen verarbeiten.command" (Mac) bzw.
„Wasserzeichen.exe" (Windows), oder  python3 oberflaeche.py

Der Motor steckt in wasserzeichen.py, die Optik in gestaltung.py.
Hier liegt nur der Ablauf: Dateien hinzufügen, Aussehen einstellen, verarbeiten.

Die Aufschriften im Kopf kommen aus beschriftung.json (siehe wasserzeichen.py);
fehlt die Datei, zeigt das Fenster neutrale Standardtexte.
"""
import ctypes, os, queue, shutil, subprocess, sys, threading, time
import tkinter as tk
from tkinter import filedialog, messagebox

from PIL import Image, ImageDraw, ImageOps, ImageTk

import webbrowser

import aktualisierung as akt
import wasserzeichen as w
from gestaltung import (FARBE, Buehne, EckenWahl, Fortschritt, Haken, Karte, Knopf,
                        Schieber, Titel, gesperrt, mono)

# Mindestmaße der Vorschau. Bewusst klein gehalten: Die Leinwand wächst mit dem
# Fenster, aber sie bestimmt, wie viel Höhe das Fenster überhaupt anfordert — und
# auf einem Windows-Rechner mit vergrößerter Darstellung ist davon wenig übrig.
VORSCHAU_B, VORSCHAU_H = 520, 260


def _ordner_oeffnen(pfad):
    os.makedirs(pfad, exist_ok=True)
    if w.IST_WINDOWS:
        os.startfile(pfad)  # noqa: S606 — Windows-eigener Öffnen-Aufruf
    else:
        subprocess.run(["open", pfad])


# --------------------------------------------------------------- Nur ein Fenster

# Die offene Sperrdatei. Muss als Modulvariable liegen bleiben: Sobald Python sie
# schließt, gibt das Betriebssystem die Sperre wieder frei.
_sperre = None


def _sperre_holen(wartesekunden=3.0):
    """Dafür sorgen, dass immer nur ein Fenster läuft.

    Zwei Fenster entstanden auf zwei Wegen: beim Neustart nach einem Update
    (der neue Vorgang startet, während der alte noch aufräumt) und beim zweiten
    Doppelklick, weil das Laden der mitgelieferten Laufzeit ein paar Sekunden
    dauert, in denen nichts zu sehen ist und man deshalb noch einmal klickt.

    Die Sperre ist eine Datei im Datenordner, die der laufende Vorgang offen
    hält. Stürzt das Programm ab, gibt das Betriebssystem sie von allein frei —
    anders als bei einer Datei mit der Vorgangsnummer, die liegen bleiben und
    den nächsten Start blockieren würde.

    Kurz gewartet wird, weil der abgelöste Vorgang beim Update noch ein paar
    Augenblicke braucht, bis er wirklich weg ist.
    """
    global _sperre
    pfad = os.path.join(w.DATEN_DIR, ".laeuft")
    ende = time.monotonic() + wartesekunden
    while True:
        datei = None
        try:
            datei = open(pfad, "a+")
            datei.seek(0)
            if w.IST_WINDOWS:
                import msvcrt
                msvcrt.locking(datei.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(datei.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            if datei is not None:
                datei.close()
            if time.monotonic() >= ende:
                return False
            time.sleep(0.25)
            continue
        except Exception:
            # Sperren nicht möglich (etwa auf einem Netzlaufwerk): dann lieber
            # starten als gar nicht starten.
            if datei is not None:
                datei.close()
            return True
        _sperre = datei
        return True


def _sperre_loesen():
    """Vor dem Neustart freigeben, damit der Nachfolger sofort weiterkann."""
    global _sperre
    if _sperre is not None:
        try:
            _sperre.close()
        except Exception:
            pass
        _sperre = None


def _vorhandenes_fenster_holen(titel):
    """Statt eines zweiten Fensters das bereits offene nach vorn holen."""
    if not w.IST_WINDOWS:
        return
    try:
        import ctypes
        benutzer = ctypes.windll.user32
        benutzer.FindWindowW.restype = ctypes.c_void_p
        benutzer.FindWindowW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
        fenster = benutzer.FindWindowW(None, titel)
        if fenster:
            benutzer.ShowWindow(ctypes.c_void_p(fenster), 9)   # SW_RESTORE
            benutzer.SetForegroundWindow(ctypes.c_void_p(fenster))
    except Exception:
        pass


def _arbeitsbereich(fenster):
    """Die freie Fläche des Bildschirms als (x, y, breite, höhe) — oder None.

    „Frei“ heißt: ohne Taskleiste, und zwar egal, wo sie steht. Windows gibt
    dafür ein fertiges Rechteck heraus, statt bloß einer Höhe — eine Leiste am
    linken Rand verschiebt eben den Anfang und nicht das Ende. Ausgeblendete
    Leisten sind darin ebenfalls schon berücksichtigt.

    Gefragt wird nach dem Bildschirm, auf dem das Fenster gerade steht: Bei zwei
    Monitoren hat jeder seine eigene Leiste. Klappt das nicht, tut es ersatzweise
    der Hauptbildschirm.

    Die Maße kommen in derselben Rechnung zurück, in der auch das Fenster misst:
    Windows rechnet für ein Programm, das nichts von vergrößerter Darstellung
    weiß, sämtliche Koordinaten um — beide Seiten also gleichermaßen.
    """
    if not w.IST_WINDOWS:
        return None
    try:
        import ctypes

        # Feldbreiten ausdrücklich: Windows rechnet hier immer mit 32 Bit,
        # während c_long anderswo acht Byte breit wäre.
        class Rechteck(ctypes.Structure):
            _fields_ = [("links", ctypes.c_int32), ("oben", ctypes.c_int32),
                        ("rechts", ctypes.c_int32), ("unten", ctypes.c_int32)]

        class Bildschirm(ctypes.Structure):
            _fields_ = [("groesse", ctypes.c_uint32), ("ganz", Rechteck),
                        ("frei", Rechteck), ("art", ctypes.c_uint32)]

        benutzer = ctypes.windll.user32
        # Fenster- und Bildschirmkennungen sind unter 64-Bit-Windows acht Byte
        # groß. Ohne diese Angaben nimmt ctypes vier an und schneidet sie ab.
        benutzer.GetParent.restype = ctypes.c_void_p
        benutzer.GetParent.argtypes = [ctypes.c_void_p]
        benutzer.MonitorFromWindow.restype = ctypes.c_void_p
        benutzer.MonitorFromWindow.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        benutzer.GetMonitorInfoW.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        frei = None

        # Der Bildschirm unter diesem Fenster. Tk hängt sein Fenster mitunter in
        # einen Rahmen — darum bis zum obersten Vorfahren hochgehen.
        griff = ctypes.c_void_p(fenster.winfo_id())
        while True:
            darueber = benutzer.GetParent(griff)
            if not darueber:
                break
            griff = ctypes.c_void_p(darueber)
        schirm = benutzer.MonitorFromWindow(griff, 2)   # 2 = der nächstgelegene
        if schirm:
            angaben = Bildschirm()
            angaben.groesse = ctypes.sizeof(Bildschirm)
            if benutzer.GetMonitorInfoW(ctypes.c_void_p(schirm), ctypes.byref(angaben)):
                frei = angaben.frei

        if frei is None:
            # SPI_GETWORKAREA — dasselbe für den Hauptbildschirm
            r = Rechteck()
            if not benutzer.SystemParametersInfoW(0x0030, 0, ctypes.byref(r), 0):
                return None
            frei = r

        breite, hoehe = frei.rechts - frei.links, frei.unten - frei.oben
        if breite < 400 or hoehe < 300:
            return None            # unplausibel — dann lieber der übliche Weg
        return frei.links, frei.oben, breite, hoehe
    except Exception:
        return None


def _musterbild():
    """Ersatzbild, solange nichts bereitliegt — Verlauf von dunkel nach hell, damit
    sichtbar wird, wie sich das Logo auf dunklen und hellen Motiven verhält."""
    bild = Image.new("RGB", (1600, 1067))
    zeichner = ImageDraw.Draw(bild)
    for y in range(bild.height):
        t = y / bild.height
        zeichner.line([(0, y), (bild.width, y)],
                      fill=(int(26 + 206 * t), int(26 + 202 * t), int(26 + 197 * t)))
    return bild


class AuswahlFenster(tk.Toplevel):
    """Zeigt, was bereitliegt, und nimmt Falsches wieder heraus.

    Ein eigenes Fenster, weil die Liste im Hauptfenster Platz bräuchte, den es
    dort nicht gibt — gebraucht wird sie ohnehin nur, wenn etwas schiefging.
    """

    def __init__(self, eltern, nach_aenderung):
        super().__init__(eltern, bg=FARBE["grund"])
        self.nach_aenderung = nach_aenderung
        self.title("Auswahl bearbeiten")
        self.transient(eltern)
        self.minsize(460, 380)

        rahmen = tk.Frame(self, bg=FARBE["grund"])
        rahmen.pack(fill="both", expand=True, padx=22, pady=20)
        rahmen.rowconfigure(1, weight=1)
        rahmen.columnconfigure(0, weight=1)

        self.kopf = Titel(rahmen, "Bereitliegende Dateien", bg=FARBE["grund"])
        self.kopf.grid(row=0, column=0, sticky="w", pady=(0, 10))

        self.liste = tk.Listbox(rahmen, selectmode="extended", font=mono(10),
                                bg=FARBE["feld"], fg=FARBE["text"],
                                selectbackground=FARBE["akzent"],
                                selectforeground=FARBE["invers"],
                                relief="flat", highlightthickness=1,
                                highlightbackground=FARBE["linie"],
                                activestyle="none", borderwidth=0)
        self.liste.grid(row=1, column=0, sticky="nsew")

        tk.Label(rahmen, text="Mehrere auf einmal: mit gedrückter Umschalt- oder Strg-Taste.",
                 font=mono(9), fg=FARBE["text_still"], bg=FARBE["grund"], anchor="w").grid(
            row=2, column=0, sticky="w", pady=(10, 14))

        knoepfe = tk.Frame(rahmen, bg=FARBE["grund"])
        knoepfe.grid(row=3, column=0, sticky="ew")
        self.knopf_weg = Knopf(knoepfe, "Ausgewählte entfernen", self._gewaehlte_weg,
                               breite=210, hintergrund=FARBE["grund"])
        self.knopf_weg.pack(side="left")
        self.knopf_alle = Knopf(knoepfe, "Alle entfernen", self._alle_weg,
                                breite=150, hintergrund=FARBE["grund"])
        self.knopf_alle.pack(side="left", padx=(10, 0))
        Knopf(knoepfe, "Fertig", self.destroy, stil="primaer", breite=110,
              hintergrund=FARBE["grund"]).pack(side="right")

        self._fuellen()
        self.liste.bind("<<ListboxSelect>>", lambda _: self._knoepfe_richten())
        self.bind("<Escape>", lambda _: self.destroy())
        self._mittig_setzen(eltern)
        self.grab_set()          # solange dieses Fenster offen ist, gilt es allein
        self.liste.focus_set()

    def _mittig_setzen(self, eltern):
        self.update_idletasks()
        b, h = max(self.winfo_reqwidth(), 460), max(self.winfo_reqheight(), 380)
        x = eltern.winfo_rootx() + (eltern.winfo_width() - b) // 2
        y = eltern.winfo_rooty() + (eltern.winfo_height() - h) // 3
        self.geometry(f"{b}x{h}+{max(0, x)}+{max(0, y)}")

    def _fuellen(self):
        fotos, videos, rest = w.input_dateien()
        self.namen = fotos + videos + rest
        self.liste.delete(0, "end")
        for name in self.namen:
            self.liste.insert("end", f"  {name}")
        anzahl = len(self.namen)
        self.kopf.configure(text=gesperrt(
            "NICHTS BEREIT" if not anzahl else
            "1 DATEI BEREIT" if anzahl == 1 else f"{anzahl} DATEIEN BEREIT"))
        self._knoepfe_richten()

    def _knoepfe_richten(self):
        self.knopf_weg.freigeben(bool(self.liste.curselection()))
        self.knopf_alle.freigeben(bool(self.namen))

    def _gewaehlte_weg(self):
        self._wegnehmen([self.namen[i] for i in self.liste.curselection()])

    def _alle_weg(self):
        self._wegnehmen(list(self.namen))

    def _wegnehmen(self, namen):
        if not namen:
            return
        was = namen[0] if len(namen) == 1 else f"{len(namen)} Dateien"
        if not messagebox.askokcancel(
                "Aus der Auswahl nehmen",
                f"{was} aus der Auswahl nehmen?\n\n"
                "Nichts wird gelöscht: Die Dateien wandern in den Ordner "
                "„entfernt“ innerhalb des Ablageordners und lassen sich von "
                "dort zurückholen.", parent=self):
            return
        genommen, fehler = w.aus_auswahl_nehmen(namen)
        self._fuellen()
        self.nach_aenderung(genommen)
        if fehler:
            liste = "\n".join(f"• {name}: {grund}" for name, grund in fehler[:8])
            messagebox.showwarning("Nicht alles ging",
                                   f"{len(fehler)} Datei(en) blieben liegen:\n\n{liste}",
                                   parent=self)


class Fenster(tk.Tk):
    def __init__(self):
        super().__init__()
        self.beschr = w.beschriftung_laden()
        self.standard = w.standard_laden()
        self.title(self.beschr["fenstertitel"])
        self.configure(bg=FARBE["grund"])
        # Nie mehr verlangen, als der Bildschirm hergibt: Ein Mindestmaß, das
        # nicht daraufpasst, hätte nur zur Folge, dass unten etwas abgeschnitten
        # wird, ohne dass man das Fenster kleiner ziehen könnte.
        self.minsize(min(940, self.winfo_screenwidth() - 40),
                     min(600, self.winfo_screenheight() - 80))
        self.einst = w.einstellungen_laden()
        self.meldungen = queue.Queue()
        self.update_meldungen = queue.Queue()
        self._update_laeuft = False
        self.laeuft = False
        self.abbruch_gewuenscht = False
        self.gesamt = 0
        self.erledigt = 0
        self._vorschau_original = None   # Ausgangsbild in voller Größe
        self._vorschau_quelle = None     # auf die aktuelle Leinwand gerechnet
        self._vorschau_masse = (0, 0)    # Leinwandgröße, für die das gilt
        self._vorschau_bild = None       # Referenz halten, sonst verwirft Tk das Bild
        self._nachzeichnen_job = None

        self._baue()
        self._gross_aufziehen()
        self._vorschau_quelle_neu_laden()
        self._zeichne_vorschau()
        self._zaehle_input()
        self.after(120, self._meldungen_abholen)
        self.protocol("WM_DELETE_WINDOW", self._schliessen)
        self._symbol_setzen()
        # Erst wenn das Fenster gezeichnet ist, sonst greift das Nachvornholen ins Leere.
        self.after(80, self._nach_vorn)

        if akt.bereitgelegt(w.PROG_DIR):
            # Beim letzten Mal geladen, aber noch nicht neu gestartet.
            self._streifen_zeigen("Eine neue Fassung liegt bereit.",
                                  "Neu starten", self._update_neu_starten)
        else:
            # Etwas verzögert, damit das Fenster zuerst steht.
            self.after(1500, self._update_pruefen)

    def _gross_aufziehen(self):
        """Beim Start die ganze freie Bildschirmfläche nutzen.

        Kein Vollbild: Titelleiste und Taskleiste bleiben sichtbar, das Fenster
        lässt sich normal verkleinern.

        Unter Windows wird die Fläche selbst gesetzt statt über den maximierten
        Zustand „zoomed“. Denn auf einem Rechner mit vergrößerter Darstellung
        rechnet Windows die Maße für ein Programm, das davon nichts weiß, ungenau
        um: Das Fenster reicht dann ein Stück unter die Taskleiste, und die
        unterste Zeile — bisher der Knopf für die Update-Suche — ist nicht mehr
        erreichbar. Unter macOS kennt Tk „zoomed“ und macht es richtig.
        """
        bereich = _arbeitsbereich(self)
        if bereich:
            x, y, breite, hoehe = bereich
            self.geometry(f"{breite}x{hoehe}+{x}+{y}")
            return
        try:
            self.state("zoomed")
            return
        except tk.TclError:
            pass
        b = self.winfo_screenwidth()
        h = self.winfo_screenheight()
        self.geometry(f"{b - 40}x{h - 120}+20+40")

    def _nach_vorn(self):
        """Das Fenster beim Start wirklich nach vorn holen.

        Windows legt ein neu erscheinendes Fenster hinter das gerade aktive:
        Nach der Installation hat der Installer den Fokus, und beim Doppelklick
        vergeht durch das Laden der Bibliotheken eine Sekunde, in der Windows
        ihn weitergibt. Ein Fenster darf sich den Fokus nicht einfach nehmen —
        wohl aber kurz „immer oben“ sein. Das Flag wird sofort wieder gelöst,
        damit das Fenster danach normal in den Stapel eingereiht bleibt.
        """
        try:
            self.deiconify()
            self.lift()
            self.attributes("-topmost", True)
            self.focus_force()
            self.after(400, lambda: self.attributes("-topmost", False))
        except tk.TclError:
            pass  # Fenster schon zu — dann eben nicht

    def _symbol_setzen(self):
        """Fenstersymbol aus app/symbol.png, falls eines mitgeliefert wurde.

        Liegt bewusst neben dem Programmcode und nicht in der exe: So lässt es
        sich mit einem kleinen Update austauschen. Das Symbol der exe selbst und
        der Verknüpfungen steckt dagegen fest in der Datei.
        """
        pfad = os.path.join(os.path.dirname(os.path.abspath(__file__)), "symbol.png")
        if not os.path.isfile(pfad):
            return
        try:
            self._symbol = ImageTk.PhotoImage(Image.open(pfad))
            self.iconphoto(True, self._symbol)
        except Exception:
            pass  # ein fehlendes Symbol ist kein Grund, nicht zu starten

    # ------------------------------------------------------------------ Aufbau

    def _baue(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        # Alles steht auf der Bühne: Passt der Inhalt nicht mehr in die Höhe,
        # erscheint ein Balken, statt dass unten etwas verschwindet.
        self.buehne = Buehne(self)
        self.buehne.grid(row=0, column=0, sticky="nsew")
        rumpf = self.buehne.inhalt
        rumpf.columnconfigure(0, weight=1)
        rumpf.rowconfigure(1, weight=1)

        self._kopf(rumpf)
        self._mitte(rumpf)
        self._fuss(rumpf)

    def _kopf(self, eltern):
        kopf = tk.Frame(eltern, bg=FARBE["grund"])
        kopf.grid(row=0, column=0, sticky="ew", padx=28, pady=(20, 14))
        kopf.columnconfigure(1, weight=1)

        links = tk.Frame(kopf, bg=FARBE["grund"])
        links.grid(row=0, column=0, sticky="w")
        tk.Label(links, text=gesperrt("WASSERZEICHEN"), font=mono(17, fett=True),
                 fg=FARBE["text"], bg=FARBE["grund"]).pack(anchor="w")
        if self.beschr["untertitel"]:
            tk.Label(links, text=self.beschr["untertitel"],
                     font=mono(10), fg=FARBE["text_leise"], bg=FARBE["grund"]).pack(
                anchor="w", pady=(6, 0))

        # Rechte Kopfecke: Marke, darunter Version und Update-Suche. Die standen
        # früher ganz unten im Fenster — also genau dort, wo als Erstes etwas
        # verschwindet, wenn der Platz knapp wird.
        rechts = tk.Frame(kopf, bg=FARBE["grund"])
        rechts.grid(row=0, column=2, sticky="ne")
        if self.beschr["marke"]:
            tk.Label(rechts, text=self.beschr["marke"], font=mono(9),
                     fg=FARBE["text_still"], bg=FARBE["grund"]).pack(anchor="e")
        zeile = tk.Frame(rechts, bg=FARBE["grund"])
        zeile.pack(anchor="e", pady=(8, 0))
        tk.Label(zeile, text=f"Version {w.VERSION}", font=mono(9),
                 fg=FARBE["text_still"], bg=FARBE["grund"]).pack(side="left", padx=(0, 12))
        Knopf(zeile, "Nach Updates suchen", lambda: self._update_pruefen(von_hand=True),
              breite=190, hoehe=26, hintergrund=FARBE["grund"]).pack(side="left")

        # Zweite Zeile im Kopf: bleibt leer, bis es etwas zu melden gibt.
        self.streifen = tk.Frame(kopf, bg=FARBE["karte"],
                                 highlightbackground=FARBE["linie"], highlightthickness=1)
        self.streifen.columnconfigure(0, weight=1)
        self.streifen_text = tk.Label(self.streifen, text="", font=mono(10),
                                      fg=FARBE["text"], bg=FARBE["karte"], anchor="w")
        self.streifen_text.grid(row=0, column=0, sticky="w", padx=16, pady=10)
        self.streifen_knopf = None
        self._streifen_sichtbar = False

    def _streifen_zeigen(self, text, knopftext=None, befehl=None):
        """Meldung über dem Fenster einblenden. Ohne Knopf nur als Hinweis."""
        self.streifen_text.configure(text=text)
        if self.streifen_knopf is not None:
            self.streifen_knopf.destroy()
            self.streifen_knopf = None
        if knopftext and befehl:
            self.streifen_knopf = Knopf(self.streifen, knopftext, befehl,
                                        stil="primaer", breite=190, hoehe=30)
            self.streifen_knopf.grid(row=0, column=1, sticky="e", padx=(10, 12), pady=8)
        if not self._streifen_sichtbar:
            self.streifen.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(16, 0))
            self._streifen_sichtbar = True

    def _streifen_verbergen(self):
        if self._streifen_sichtbar:
            self.streifen.grid_remove()
            self._streifen_sichtbar = False

    def _mitte(self, eltern):
        mitte = tk.Frame(eltern, bg=FARBE["grund"])
        mitte.grid(row=1, column=0, sticky="nsew", padx=28)
        # Beide Spalten wachsen mit, die Vorschau aber viermal so stark: sie
        # profitiert am meisten von Platz, die Einstellungen sollen nur nicht
        # gestaucht bleiben, wenn das Fenster größer wird.
        mitte.columnconfigure(0, weight=4)
        mitte.columnconfigure(1, weight=1, minsize=330)
        mitte.rowconfigure(0, weight=1)

        # --- Vorschau
        links = Karte(mitte)
        links.grid(row=0, column=0, sticky="nsew")
        links.rowconfigure(1, weight=1)
        links.columnconfigure(0, weight=1)
        # Kopfzeile der Vorschau: Der Knopf gehört hierher und nicht zu den
        # Einstellungen — er ändert nur, woran man sie ausprobiert.
        vorschau_kopf = tk.Frame(links, bg=FARBE["karte"])
        vorschau_kopf.grid(row=0, column=0, sticky="ew", padx=20, pady=(12, 8))
        vorschau_kopf.columnconfigure(0, weight=1)
        Titel(vorschau_kopf, "Vorschau").grid(row=0, column=0, sticky="w")
        Knopf(vorschau_kopf, "Anderes Bild", self._vorschaubild_waehlen,
              breite=150, hoehe=30).grid(row=0, column=1, sticky="e")
        self.leinwand = tk.Canvas(links, width=VORSCHAU_B, height=VORSCHAU_H,
                                  bg=FARBE["feld"], highlightthickness=0)
        self.leinwand.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 16))
        self.leinwand.bind("<Configure>", lambda _: self._geaendert())

        # --- Einstellungen
        rechts = Karte(mitte)
        rechts.grid(row=0, column=1, sticky="nsew", padx=(18, 0))
        innen = tk.Frame(rechts, bg=FARBE["karte"])
        innen.pack(fill="both", expand=True, padx=20, pady=16)

        Titel(innen, "Position des Logos").pack(anchor="w", pady=(0, 10))
        self.ecken = EckenWahl(innen, self.einst["ecke"],
                               bei_aenderung=lambda _: self._geaendert())
        self.ecken.pack(fill="x", pady=(0, 12))

        self.s_breite = Schieber(innen, "Größe", 8, 45, self.einst["breite_prozent"],
                                 bei_aenderung=lambda _: self._geaendert())
        self.s_breite.pack(fill="x", pady=(0, 12))
        self.s_rand = Schieber(innen, "Abstand zum Rand", 0, 10, self.einst["rand_prozent"],
                               nachkomma=1, bei_aenderung=lambda _: self._geaendert())
        self.s_rand.pack(fill="x", pady=(0, 12))
        self.s_deckkraft = Schieber(innen, "Deckkraft", 20, 100,
                                    self.einst["deckkraft_prozent"],
                                    bei_aenderung=lambda _: self._geaendert())
        self.s_deckkraft.pack(fill="x", pady=(0, 12))
        self.h_full_hd = Haken(innen, "Videos auf Full HD verkleinern",
                               "Reicht für Social Media und geht schneller. Betrifft nur Videos über Full HD.",
                               self.einst["video_full_hd"],
                               bei_aenderung=lambda _: self._geaendert())
        self.h_full_hd.pack(fill="x", pady=(0, 16))

        tk.Frame(innen, bg=FARBE["linie"], height=1).pack(fill="x", pady=(0, 14))
        knoepfe = tk.Frame(innen, bg=FARBE["karte"])
        knoepfe.pack(fill="x")
        self.knopf_standard = Knopf(knoepfe, "Als Standard setzen",
                                    self._als_standard_setzen, breite=180)
        self.knopf_standard.pack(side="left")
        Knopf(knoepfe, "Auf Standard zurücksetzen", self._zuruecksetzen,
              breite=220).pack(side="left", padx=(10, 0))

    def _fuss(self, eltern):
        fuss = tk.Frame(eltern, bg=FARBE["grund"])
        fuss.grid(row=2, column=0, sticky="ew", padx=28, pady=(14, 18))
        fuss.columnconfigure(0, weight=1)

        karte = Karte(fuss)
        karte.grid(row=0, column=0, sticky="ew")
        innen = tk.Frame(karte, bg=FARBE["karte"])
        innen.pack(fill="x", padx=20, pady=14)
        innen.columnconfigure(1, weight=1)

        # Zeile 1 — Dateien
        zeile1 = tk.Frame(innen, bg=FARBE["karte"])
        zeile1.grid(row=0, column=0, columnspan=3, sticky="ew")
        zeile1.columnconfigure(3, weight=1)
        Titel(zeile1, "Dateien").grid(row=0, column=0, columnspan=4, sticky="w",
                                      pady=(0, 10))
        Knopf(zeile1, "Fotos und Videos wählen", self._dateien_waehlen,
              breite=240).grid(row=1, column=0)
        self.knopf_auswahl = Knopf(zeile1, "Auswahl bearbeiten", self._auswahl_bearbeiten,
                                   breite=190)
        self.knopf_auswahl.grid(row=1, column=1, padx=10)
        Knopf(zeile1, "Ordner öffnen", self._input_oeffnen,
              breite=150).grid(row=1, column=2)
        self.lbl_input = tk.Label(zeile1, font=mono(10), fg=FARBE["text_leise"],
                                  bg=FARBE["karte"], anchor="e")
        self.lbl_input.grid(row=1, column=3, sticky="e")

        tk.Frame(innen, bg=FARBE["linie"], height=1).grid(
            row=1, column=0, columnspan=3, sticky="ew", pady=14)

        # Zeile 2 — Start
        zeile2 = tk.Frame(innen, bg=FARBE["karte"])
        zeile2.grid(row=2, column=0, columnspan=3, sticky="ew")
        zeile2.columnconfigure(1, weight=1)
        self.knopf_start = Knopf(zeile2, gesperrt("STARTEN"), self._starten,
                                 stil="primaer", breite=240, hoehe=40)
        self.knopf_start.grid(row=0, column=0)
        balken_feld = tk.Frame(zeile2, bg=FARBE["karte"])
        balken_feld.grid(row=0, column=1, sticky="ew", padx=18)
        self.lbl_status = tk.Label(balken_feld, text="", font=mono(9),
                                   fg=FARBE["text_still"], bg=FARBE["karte"], anchor="w")
        self.lbl_status.pack(fill="x", pady=(0, 6))
        self.balken = Fortschritt(balken_feld)
        self.balken.pack(fill="x")
        ausgang = tk.Frame(zeile2, bg=FARBE["karte"])
        ausgang.grid(row=0, column=2)
        Knopf(ausgang, "Ergebnisse öffnen", self._ergebnisse_oeffnen,
              breite=180).pack(side="left")
        Knopf(ausgang, "Frühere Läufe", lambda: _ordner_oeffnen(w.OUT_DIR),
              breite=150).pack(side="left", padx=(10, 0))

        # Protokoll
        self.protokoll = tk.Text(innen, height=4, wrap="word", state="disabled",
                                 bg=FARBE["feld"], fg=FARBE["text_leise"],
                                 font=mono(9), relief="flat", padx=14, pady=12,
                                 highlightthickness=1, highlightbackground=FARBE["linie"],
                                 insertbackground=FARBE["text"])
        self.protokoll.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(14, 0))
        self.protokoll.tag_configure("hell", foreground=FARBE["text"])
        self.protokoll.tag_configure("fehler", foreground=FARBE["warnung"])

    # ------------------------------------------------------------ Einstellungen

    def _aktuelle_einstellungen(self):
        return {
            "ecke": self.ecken.wert,
            "breite_prozent": round(self.s_breite.wert, 1),
            "rand_prozent": round(self.s_rand.wert, 1),
            "deckkraft_prozent": round(self.s_deckkraft.wert, 1),
            "jpeg_qualitaet": self.einst["jpeg_qualitaet"],
            "video_full_hd": self.h_full_hd.wert,
        }

    def _geaendert(self):
        """Regler bewegt: Vorschau gebündelt nachzeichnen, nicht bei jedem Pixel."""
        self.einst = self._aktuelle_einstellungen()
        if self._nachzeichnen_job:
            self.after_cancel(self._nachzeichnen_job)
        self._nachzeichnen_job = self.after(50, self._zeichne_vorschau)

    def _zuruecksetzen(self):
        self.ecken.setzen(self.standard["ecke"])
        self.s_breite.setzen(self.standard["breite_prozent"])
        self.s_rand.setzen(self.standard["rand_prozent"])
        self.s_deckkraft.setzen(self.standard["deckkraft_prozent"])
        self.h_full_hd.setzen(self.standard["video_full_hd"])
        self._geaendert()

    def _als_standard_setzen(self):
        """Die eingestellten Werte werden zum Ausgangspunkt für später."""
        werte = self._aktuelle_einstellungen()
        try:
            w.standard_speichern(werte)
        except OSError as e:
            messagebox.showwarning("Nicht gespeichert",
                                   f"Der Standard ließ sich nicht ablegen: {e}")
            return
        self.standard = werte
        # Rückmeldung am Ort der Handlung statt in einem Fenster, das man
        # wegklicken muss.
        self.knopf_standard.beschriften("Gespeichert")
        self.after(1600, lambda: self.knopf_standard.beschriften("Als Standard setzen"))

    # ---------------------------------------------------------------- Vorschau

    def _vorschau_quelle_neu_laden(self, pfad=None):
        """Vorschaubild wählen: übergebenes Bild, sonst erstes wartendes Foto, sonst Muster."""
        if pfad is None:
            fotos, _, _ = w.input_dateien()
            echte = [f for f in fotos
                     if os.path.splitext(f)[1].lower() not in w.RAW_ENDUNGEN]
            pfad = os.path.join(w.IN_DIR, echte[0]) if echte else None
        try:
            bild = ImageOps.exif_transpose(Image.open(pfad)).convert("RGB") if pfad \
                else _musterbild()
        except Exception:
            bild = _musterbild()
        self._vorschau_original = bild
        self._vorschau_masse = (0, 0)  # erzwingt Neuberechnung beim nächsten Zeichnen

    def _vorschau_anpassen(self, breite, hoehe):
        """Ausgangsbild auf die aktuelle Leinwandgröße rechnen. Alle Maße im Skript sind
        relativ zur Bildbreite — die verkleinerte Vorschau bleibt darum wahrheitsgetreu."""
        if self._vorschau_masse == (breite, hoehe):
            return
        bild = self._vorschau_original.copy()
        bild.thumbnail((max(80, breite), max(60, hoehe)), Image.LANCZOS)
        self._vorschau_quelle = bild
        self._vorschau_masse = (breite, hoehe)

    def _vorschaubild_waehlen(self):
        pfad = filedialog.askopenfilename(
            title="Bild für die Vorschau",
            filetypes=[("Bilder", "*.jpg *.jpeg *.png *.heic *.webp *.tif *.tiff")])
        if pfad:
            self._vorschau_quelle_neu_laden(pfad)
            self._zeichne_vorschau()

    def _zeichne_vorschau(self):
        self._nachzeichnen_job = None
        b = self.leinwand.winfo_width() or VORSCHAU_B
        h = self.leinwand.winfo_height() or VORSCHAU_H
        self._vorschau_anpassen(b, h)
        bild = self._vorschau_quelle.copy().convert("RGBA")
        try:
            logo = w._logo_skaliert(bild.width, self.einst)
            bild.alpha_composite(logo, w._ecken_position(bild.width, bild.height,
                                                         logo.width, logo.height, self.einst))
        except w.WerkstattFehler as e:
            self.leinwand.delete("all")
            self.leinwand.create_text(b / 2, h / 2, text=str(e), font=mono(10),
                                      fill=FARBE["text_leise"], width=b - 80,
                                      justify="center")
            return
        self._vorschau_bild = ImageTk.PhotoImage(bild.convert("RGB"))
        self.leinwand.delete("all")
        self.leinwand.create_image(b / 2, h / 2, image=self._vorschau_bild)

    # ---------------------------------------------------------------- Dateien

    def _ergebnisse_oeffnen(self):
        """Direkt in den jüngsten Lauf springen — von dort zieht man die Dateien weiter."""
        _ordner_oeffnen(w.letzter_lauf() or w.OUT_DIR)

    def _input_oeffnen(self):
        _ordner_oeffnen(w.IN_DIR)
        self.after(1500, self._nach_dateiaenderung)

    def _dateien_waehlen(self):
        pfade = filedialog.askopenfilenames(title="Fotos und Videos auswählen")
        if not pfade:
            return
        os.makedirs(w.IN_DIR, exist_ok=True)
        kopiert = 0
        for p in pfade:
            try:
                shutil.copy2(p, os.path.join(w.IN_DIR, os.path.basename(p)))
                kopiert += 1
            except OSError as e:
                self._schreibe(f"{os.path.basename(p)} konnte nicht übernommen werden: {e}",
                               "fehler")
        self._schreibe(f"{kopiert} Datei(en) übernommen.", "hell")
        self._nach_dateiaenderung()

    def _auswahl_bearbeiten(self):
        """Liste des Bereitliegenden öffnen — dort lässt sich Falsches herausnehmen."""
        if self.laeuft:
            messagebox.showinfo("Läuft gerade",
                                "Während der Verarbeitung lässt sich die Auswahl "
                                "nicht ändern.")
            return
        fotos, videos, rest = w.input_dateien()
        if not (fotos or videos or rest):
            messagebox.showinfo("Nichts ausgewählt",
                                "Es liegt noch nichts bereit.\n\n"
                                "Mit „Fotos und Videos wählen“ kommt etwas hinein.")
            return
        AuswahlFenster(self, self._auswahl_geaendert)

    def _auswahl_geaendert(self, genommen):
        if genommen:
            self._schreibe(f"{genommen} Datei(en) aus der Auswahl genommen — sie liegen "
                           "jetzt im Ordner „entfernt“.", "hell")
        self._nach_dateiaenderung()

    def _nach_dateiaenderung(self):
        self._zaehle_input()
        self._vorschau_quelle_neu_laden()
        self._zeichne_vorschau()

    def _zaehle_input(self):
        fotos, videos, rest = w.input_dateien()
        anzahl = len(fotos) + len(videos)
        text = (f"{len(fotos)} Foto(s) · {len(videos)} Video(s) bereit" if anzahl
                else "noch nichts ausgewählt")
        if rest:
            text += f"  ·  {len(rest)} unbekanntes Format"
        self.lbl_input.config(text=text,
                              fg=FARBE["text"] if anzahl else FARBE["text_still"])
        self.knopf_auswahl.freigeben(bool(fotos or videos or rest))
        return anzahl

    # ------------------------------------------------------------ Verarbeiten

    def _starten(self):
        if self.laeuft:  # der Knopf ist währenddessen der Abbrechen-Knopf
            self.abbruch_gewuenscht = True
            self.knopf_start.beschriften(gesperrt("STOPPT"))
            self.knopf_start.freigeben(False)
            return
        anzahl = self._zaehle_input()
        if not anzahl:
            messagebox.showinfo("Nichts zu tun",
                                "Es liegen keine Fotos oder Videos bereit.\n\n"
                                "Bitte unten „Fotos und Videos wählen“ anklicken.")
            return
        w.einstellungen_speichern(self.einst)
        self.laeuft = True
        self.abbruch_gewuenscht = False
        self.gesamt, self.erledigt = anzahl, 0
        self.knopf_start.beschriften(gesperrt("ABBRECHEN"))
        self.balken.setzen(0)
        self.lbl_status.config(text=f"0 von {anzahl}")
        self._schreibe("")
        threading.Thread(target=self._arbeit, args=(dict(self.einst),),
                         daemon=True).start()

    def _arbeit(self, einst):
        """Läuft im Hintergrund — das Fenster bleibt bedienbar."""
        # Windows soll mitten in einem langen Stapel nicht einschlafen. Der Zustand
        # gilt je Thread, darum hier und nicht im Fenster-Thread.
        if w.IST_WINDOWS:
            try:
                ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)  # CONTINUOUS | SYSTEM_REQUIRED
            except Exception:
                pass
        try:
            fertig, fehler, lauf = w.alles_verarbeiten(
                einst, melden=self.meldungen.put, abbruch=lambda: self.abbruch_gewuenscht)
            self.meldungen.put(("ENDE", fertig, fehler, lauf))
        except Exception as e:
            self.meldungen.put(("ENDE", 0, [("", w._klartext(e))], None))
        finally:
            if w.IST_WINDOWS:
                try:
                    ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)  # CONTINUOUS
                except Exception:
                    pass

    # -------------------------------------------------------------- Aktualisieren

    def _update_pruefen(self, von_hand=False):
        """Im Hintergrund nachsehen, ob es etwas Neueres gibt.

        Läuft in einem eigenen Thread, damit ein lahmes Netz das Fenster nicht
        blockiert. Das Ergebnis geht über die Warteschlange zurück, weil Tk nur
        aus dem Hauptthread bedient werden darf.
        """
        if self._update_laeuft:
            return
        self._update_laeuft = True
        if von_hand:
            self._streifen_zeigen("Suche nach Aktualisierungen ...")

        def arbeit():
            try:
                auskunft = akt.nachsehen(w.VERSION)
                self.update_meldungen.put(("GEFUNDEN", auskunft))
            except akt.KeinUpdate as e:
                self.update_meldungen.put(("NICHTS", str(e)))
            except Exception as e:                      # nie das Fenster mitreißen
                self.update_meldungen.put(("NICHTS", str(e)))

        threading.Thread(target=arbeit, daemon=True).start()

    def _update_holen(self, auskunft):
        """Das kleine Paket laden und für den nächsten Start bereitlegen."""
        if self._update_laeuft:
            return
        self._update_laeuft = True
        self._streifen_zeigen(f"Version {auskunft['version']} wird geladen ...")

        def arbeit():
            try:
                akt.herunterladen(auskunft, w.PROG_DIR)
                self.update_meldungen.put(("GELADEN", auskunft))
            except akt.KeinUpdate as e:
                self.update_meldungen.put(("FEHLGESCHLAGEN", str(e)))
            except Exception as e:
                self.update_meldungen.put(("FEHLGESCHLAGEN", str(e)))

        threading.Thread(target=arbeit, daemon=True).start()

    def _update_neu_starten(self):
        """Das Programm neu starten, damit start.py die neue Fassung einsetzt."""
        if self.laeuft:
            messagebox.showinfo(
                "Wasserzeichen",
                "Es läuft gerade eine Verarbeitung.\n\n"
                "Die neue Fassung wird beim nächsten Start von allein übernommen.")
            return
        try:
            w.einstellungen_speichern(self.einst)
        except OSError:
            pass
        if getattr(sys, "frozen", False):
            befehl = [sys.executable]
        else:
            befehl = [sys.executable, os.path.join(w.PROG_DIR, "start.py")]
        # Erst verschwinden, dann den Nachfolger starten: Sonst stehen für einige
        # Sekunden zwei Fenster nebeneinander, bis dieses hier zu ist. Die Sperre
        # wird vorher gelöst, damit der Nachfolger nicht auf sie warten muss.
        self.withdraw()
        _sperre_loesen()
        try:
            subprocess.Popen(befehl, close_fds=True)
        except OSError as e:
            self.deiconify()
            _sperre_holen(0)
            messagebox.showerror("Wasserzeichen",
                                 f"Neustart nicht möglich: {e}\n\n"
                                 "Bitte das Programm von Hand neu starten.")
            return
        self.destroy()

    def _update_meldung(self, art, inhalt):
        if art == "GEFUNDEN":
            if inhalt["paket"]:
                self._streifen_zeigen(
                    f"Version {inhalt['version']} ist verfügbar.",
                    "Jetzt aktualisieren", lambda: self._update_holen(inhalt))
            else:
                # Braucht eine neue Bibliothek: das kleine Paket reicht nicht.
                self._streifen_zeigen(
                    f"Version {inhalt['version']} ist verfügbar — als vollständige Installation.",
                    "Download öffnen", lambda: webbrowser.open(inhalt["seite"]))
        elif art == "GELADEN":
            self._streifen_zeigen(
                f"Version {inhalt['version']} ist bereit.",
                "Neu starten", self._update_neu_starten)
        elif art == "FEHLGESCHLAGEN":
            self._streifen_zeigen(f"Aktualisierung nicht möglich: {inhalt}")
            self.after(8000, self._streifen_verbergen)
        elif art == "NICHTS":
            if self._streifen_sichtbar:
                self._streifen_zeigen(inhalt)
                self.after(5000, self._streifen_verbergen)

    def _meldungen_abholen(self):
        """Meldungen aus dem Arbeits-Thread ins Fenster holen (Tk ist nicht thread-sicher)."""
        while True:
            try:
                art, inhalt = self.update_meldungen.get_nowait()
            except queue.Empty:
                break
            self._update_laeuft = False
            self._update_meldung(art, inhalt)

        while True:
            try:
                eintrag = self.meldungen.get_nowait()
            except queue.Empty:
                break
            if isinstance(eintrag, tuple) and eintrag[0] == "ENDE":
                self._beendet(*eintrag[1:])
                continue
            marke = "fehler" if "FEHLER" in eintrag else None
            self._schreibe(eintrag, marke)
            if eintrag.lstrip().startswith(("fertig", "FEHLER")):
                self.erledigt += 1
                self.balken.setzen(self.erledigt / max(1, self.gesamt))
                self.lbl_status.config(text=f"{self.erledigt} von {self.gesamt}")
        self.after(120, self._meldungen_abholen)

    def _beendet(self, fertig, fehler, lauf):
        self.laeuft = False
        self.knopf_start.freigeben(True)
        self.knopf_start.beschriften(gesperrt("STARTEN"))
        self.lbl_status.config(text=f"{fertig} fertig" + (f" · {len(fehler)} Fehler"
                                                          if fehler else ""))
        self._nach_dateiaenderung()
        ordner = os.path.basename(lauf) if lauf and fertig else None
        wo = f"\n\nOrdner: {ordner}" if ordner else ""
        if fehler:
            liste = "\n".join(f"• {name}: {grund}" for name, grund in fehler[:8])
            messagebox.showwarning(
                "Mit Fehlern beendet",
                f"{fertig} Datei(en) fertig, {len(fehler)} nicht verarbeitet:\n\n{liste}\n\n"
                f"Diese Dateien liegen weiterhin bereit.{wo}")
        elif fertig:
            messagebox.showinfo("Fertig",
                                f"{fertig} Datei(en) mit Wasserzeichen versehen.{wo}\n\n"
                                "Mit „Ergebnisse öffnen“ springst du direkt hinein.")

    def _schreibe(self, text, marke=None):
        self.protokoll.config(state="normal")
        if text == "":
            self.protokoll.delete("1.0", "end")
        else:
            self.protokoll.insert("end", text + "\n", marke or ())
            self.protokoll.see("end")
        self.protokoll.config(state="disabled")

    def _schliessen(self):
        if self.laeuft and not messagebox.askokcancel(
                "Läuft noch", "Die Verarbeitung läuft. Trotzdem schließen?"):
            return
        try:
            w.einstellungen_speichern(self.einst)
        except OSError:
            pass
        self.destroy()


def main(nach_start=None):
    """Einstiegspunkt — direkt aufgerufen oder aus start.py der fertigen exe.

    „nach_start“ wird aufgerufen, sobald das Fenster nachweislich steht. start.py
    verwirft daraufhin die vorherige Fassung: Ein Update gilt erst dann als
    gelungen, wenn wirklich ein Fenster zu sehen war.
    """
    if not _sperre_holen():
        # Es läuft schon eines. Kein zweites aufmachen, sondern das vorhandene
        # zeigen — sonst arbeitet man in zwei Fenstern an denselben Dateien.
        _vorhandenes_fenster_holen(w.beschriftung_laden()["fenstertitel"])
        return
    try:
        fenster = Fenster()
        if nach_start:
            fenster.after(2000, nach_start)
        fenster.mainloop()
    finally:
        _sperre_loesen()


if __name__ == "__main__":
    main()
