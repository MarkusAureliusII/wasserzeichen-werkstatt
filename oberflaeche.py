#!/usr/bin/env python3
"""Fenster für die Wasserzeichen-Werkstatt — die Bedienoberfläche.

Start: Doppelklick auf „Wasserzeichen verarbeiten.command" (Mac) bzw.
„Wasserzeichen.exe" (Windows), oder  python3 oberflaeche.py

Der Motor steckt in wasserzeichen.py, die Optik in gestaltung.py.
Hier liegt nur der Ablauf: Dateien hinzufügen, Aussehen einstellen, verarbeiten.

Die Aufschriften im Kopf kommen aus beschriftung.json (siehe wasserzeichen.py);
fehlt die Datei, zeigt das Fenster neutrale Standardtexte.
"""
import os, queue, shutil, subprocess, sys, threading
import tkinter as tk
from tkinter import filedialog, messagebox

from PIL import Image, ImageDraw, ImageOps, ImageTk

import webbrowser

import aktualisierung as akt
import wasserzeichen as w
from gestaltung import (FARBE, EckenWahl, Fortschritt, Karte, Knopf, Schieber, Titel,
                        gesperrt, mono)

VORSCHAU_B, VORSCHAU_H = 660, 440


def _ordner_oeffnen(pfad):
    os.makedirs(pfad, exist_ok=True)
    if w.IST_WINDOWS:
        os.startfile(pfad)  # noqa: S606 — Windows-eigener Öffnen-Aufruf
    else:
        subprocess.run(["open", pfad])


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


class Fenster(tk.Tk):
    def __init__(self):
        super().__init__()
        self.beschr = w.beschriftung_laden()
        self.title(self.beschr["fenstertitel"])
        self.configure(bg=FARBE["grund"])
        self.minsize(1080, 860)
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
        self.rowconfigure(1, weight=1)

        self._kopf()
        self._mitte()
        self._fuss()

    def _kopf(self):
        kopf = tk.Frame(self, bg=FARBE["grund"])
        kopf.grid(row=0, column=0, sticky="ew", padx=28, pady=(26, 18))
        kopf.columnconfigure(1, weight=1)

        links = tk.Frame(kopf, bg=FARBE["grund"])
        links.grid(row=0, column=0, sticky="w")
        tk.Label(links, text=gesperrt("WASSERZEICHEN"), font=mono(17, fett=True),
                 fg=FARBE["text"], bg=FARBE["grund"]).pack(anchor="w")
        if self.beschr["untertitel"]:
            tk.Label(links, text=self.beschr["untertitel"],
                     font=mono(10), fg=FARBE["text_leise"], bg=FARBE["grund"]).pack(
                anchor="w", pady=(6, 0))

        if self.beschr["marke"]:
            tk.Label(kopf, text=self.beschr["marke"], font=mono(9),
                     fg=FARBE["text_still"], bg=FARBE["grund"]).grid(row=0, column=2, sticky="e")

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

    def _mitte(self):
        mitte = tk.Frame(self, bg=FARBE["grund"])
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
        Titel(links, "Vorschau").grid(row=0, column=0, sticky="w", padx=20, pady=(16, 10))
        self.leinwand = tk.Canvas(links, width=VORSCHAU_B, height=VORSCHAU_H,
                                  bg=FARBE["feld"], highlightthickness=0)
        self.leinwand.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))
        self.leinwand.bind("<Configure>", lambda _: self._geaendert())

        # --- Einstellungen
        rechts = Karte(mitte)
        rechts.grid(row=0, column=1, sticky="nsew", padx=(18, 0))
        innen = tk.Frame(rechts, bg=FARBE["karte"])
        innen.pack(fill="both", expand=True, padx=22, pady=20)

        Titel(innen, "Position des Logos").pack(anchor="w", pady=(0, 12))
        self.ecken = EckenWahl(innen, self.einst["ecke"],
                               bei_aenderung=lambda _: self._geaendert())
        self.ecken.pack(fill="x", pady=(0, 14))

        self.s_breite = Schieber(innen, "Größe", 8, 45, self.einst["breite_prozent"],
                                 bei_aenderung=lambda _: self._geaendert())
        self.s_breite.pack(fill="x", pady=(0, 16))
        self.s_rand = Schieber(innen, "Abstand zum Rand", 0, 10, self.einst["rand_prozent"],
                               nachkomma=1, bei_aenderung=lambda _: self._geaendert())
        self.s_rand.pack(fill="x", pady=(0, 16))
        self.s_deckkraft = Schieber(innen, "Deckkraft", 20, 100,
                                    self.einst["deckkraft_prozent"],
                                    bei_aenderung=lambda _: self._geaendert())
        self.s_deckkraft.pack(fill="x", pady=(0, 22))

        tk.Frame(innen, bg=FARBE["linie"], height=1).pack(fill="x", pady=(0, 18))
        Knopf(innen, "Anderes Vorschaubild", self._vorschaubild_waehlen,
              breite=250).pack(anchor="w", pady=(0, 8))
        Knopf(innen, "Auf Standard zurücksetzen", self._zuruecksetzen,
              breite=250).pack(anchor="w")

    def _fuss(self):
        fuss = tk.Frame(self, bg=FARBE["grund"])
        fuss.grid(row=2, column=0, sticky="ew", padx=28, pady=(18, 24))
        fuss.columnconfigure(0, weight=1)

        karte = Karte(fuss)
        karte.grid(row=0, column=0, sticky="ew")
        innen = tk.Frame(karte, bg=FARBE["karte"])
        innen.pack(fill="x", padx=22, pady=18)
        innen.columnconfigure(1, weight=1)

        # Zeile 1 — Dateien
        zeile1 = tk.Frame(innen, bg=FARBE["karte"])
        zeile1.grid(row=0, column=0, columnspan=3, sticky="ew")
        zeile1.columnconfigure(2, weight=1)
        Titel(zeile1, "Dateien").grid(row=0, column=0, columnspan=3, sticky="w",
                                      pady=(0, 10))
        Knopf(zeile1, "Fotos und Videos wählen", self._dateien_waehlen,
              breite=240).grid(row=1, column=0)
        Knopf(zeile1, "Ordner öffnen", self._input_oeffnen,
              breite=150).grid(row=1, column=1, padx=10)
        self.lbl_input = tk.Label(zeile1, font=mono(10), fg=FARBE["text_leise"],
                                  bg=FARBE["karte"], anchor="e")
        self.lbl_input.grid(row=1, column=2, sticky="e")

        tk.Frame(innen, bg=FARBE["linie"], height=1).grid(
            row=1, column=0, columnspan=3, sticky="ew", pady=18)

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
        self.protokoll = tk.Text(innen, height=6, wrap="word", state="disabled",
                                 bg=FARBE["feld"], fg=FARBE["text_leise"],
                                 font=mono(9), relief="flat", padx=14, pady=12,
                                 highlightthickness=1, highlightbackground=FARBE["linie"],
                                 insertbackground=FARBE["text"])
        self.protokoll.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(18, 0))
        self.protokoll.tag_configure("hell", foreground=FARBE["text"])
        self.protokoll.tag_configure("fehler", foreground=FARBE["warnung"])

        # Fußzeile: Version und die Möglichkeit, selbst nachzusehen — falls beim
        # Start kein Netz da war.
        fusszeile = tk.Frame(innen, bg=FARBE["karte"])
        fusszeile.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(12, 0))
        fusszeile.columnconfigure(0, weight=1)
        tk.Label(fusszeile, text=f"Version {w.VERSION}", font=mono(9),
                 fg=FARBE["text_still"], bg=FARBE["karte"], anchor="w").grid(
            row=0, column=0, sticky="w")
        Knopf(fusszeile, "Nach Updates suchen", lambda: self._update_pruefen(von_hand=True),
              breite=190, hoehe=28).grid(row=0, column=1, sticky="e")

    # ------------------------------------------------------------ Einstellungen

    def _aktuelle_einstellungen(self):
        return {
            "ecke": self.ecken.wert,
            "breite_prozent": round(self.s_breite.wert, 1),
            "rand_prozent": round(self.s_rand.wert, 1),
            "deckkraft_prozent": round(self.s_deckkraft.wert, 1),
            "jpeg_qualitaet": self.einst["jpeg_qualitaet"],
        }

    def _geaendert(self):
        """Regler bewegt: Vorschau gebündelt nachzeichnen, nicht bei jedem Pixel."""
        self.einst = self._aktuelle_einstellungen()
        if self._nachzeichnen_job:
            self.after_cancel(self._nachzeichnen_job)
        self._nachzeichnen_job = self.after(50, self._zeichne_vorschau)

    def _zuruecksetzen(self):
        self.ecken.setzen(w.STANDARD["ecke"])
        self.s_breite.setzen(w.STANDARD["breite_prozent"])
        self.s_rand.setzen(w.STANDARD["rand_prozent"])
        self.s_deckkraft.setzen(w.STANDARD["deckkraft_prozent"])
        self._geaendert()

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
        try:
            fertig, fehler, lauf = w.alles_verarbeiten(
                einst, melden=self.meldungen.put, abbruch=lambda: self.abbruch_gewuenscht)
            self.meldungen.put(("ENDE", fertig, fehler, lauf))
        except Exception as e:
            self.meldungen.put(("ENDE", 0, [("", w._klartext(e))], None))

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
        try:
            subprocess.Popen(befehl, close_fds=True)
        except OSError as e:
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
    fenster = Fenster()
    if nach_start:
        fenster.after(2000, nach_start)
    fenster.mainloop()


if __name__ == "__main__":
    main()
