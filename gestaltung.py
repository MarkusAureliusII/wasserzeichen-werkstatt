#!/usr/bin/env python3
"""Bausteine für die Oberfläche — Farben, Schrift und selbstgezeichnete Bedienelemente.

Die Standard-Widgets von Tk lassen sich plattformübergreifend kaum einfärben
(macOS ignoriert Farbangaben im Aqua-Stil). Darum sind Knopf, Schieber und
Eckenwahl hier auf einer Leinwand selbst gezeichnet — dadurch sieht das Fenster
unter macOS und Windows identisch aus und folgt exakt der Gestaltungsvorgabe:
near-black, warmes Off-White, Monospace, viel Negativraum, keine bunten Farben.
"""
import tkinter as tk
import tkinter.font as tkfont

# Light Mode: warmes Off-White, tiefes Anthrazit, keine bunten Farben.
FARBE = {
    "grund": "#f5f4f0",        # Fensterhintergrund, warm, nicht stechend weiß
    "karte": "#fbfaf7",        # Flächen
    "karte_hell": "#f0eee8",   # Flächen beim Überfahren
    "feld": "#f2f0ea",         # vertiefte Bereiche (Vorschau, Protokoll)
    "linie": "#e3e0d9",        # feine Trennlinien und Rahmen
    "linie_hell": "#c6c2b9",
    "text": "#1a1a1a",         # tiefes Anthrazit
    "text_leise": "#6b6560",   # warmes Mittelgrau
    "text_still": "#9d968e",
    "akzent": "#1a1a1a",       # Fläche der Hauptaktion
    "akzent_hell": "#333130",
    "invers": "#f5f4f0",       # Text auf dunkler Fläche
    "warnung": "#9c4a33",      # gedecktes Rot für Fehlerzeilen
}

# Monospace nach Marken-Vorgabe; die erste vorhandene Schrift gewinnt.
MONO_KANDIDATEN = ["Anca Coder", "JetBrains Mono", "SF Mono", "Menlo",
                   "Consolas", "DejaVu Sans Mono", "Courier New"]

_familie = None


def mono(groesse=11, fett=False):
    """Monospace-Schrift der Marke in der gewünschten Größe."""
    global _familie
    if _familie is None:
        vorhanden = set(tkfont.families())
        _familie = next((f for f in MONO_KANDIDATEN if f in vorhanden), "Courier")
    return tkfont.Font(family=_familie, size=groesse, weight="bold" if fett else "normal")


def gesperrt(text):
    """Buchstaben sperren — ersetzt das fehlende letter-spacing von Tk."""
    return " ".join(text)


def rundes_rechteck(leinwand, x1, y1, x2, y2, radius=6, **kw):
    """Abgerundetes Rechteck als Polygon (Tk kennt keine runden Ecken)."""
    punkte = [
        x1 + radius, y1, x2 - radius, y1, x2, y1, x2, y1 + radius,
        x2, y2 - radius, x2, y2, x2 - radius, y2, x1 + radius, y2,
        x1, y2, x1, y2 - radius, x1, y1 + radius, x1, y1,
    ]
    return leinwand.create_polygon(punkte, smooth=True, **kw)


class Karte(tk.Frame):
    """Fläche mit feinem Rahmen — trägt die einzelnen Bereiche des Fensters."""

    def __init__(self, eltern, **kw):
        super().__init__(eltern, bg=FARBE["karte"], highlightthickness=1,
                         highlightbackground=FARBE["linie"],
                         highlightcolor=FARBE["linie"], **kw)


class Titel(tk.Label):
    """Kleine gesperrte Überschrift über einem Abschnitt."""

    def __init__(self, eltern, text, **kw):
        super().__init__(eltern, text=gesperrt(text.upper()), font=mono(8),
                         fg=FARBE["text_still"], bg=kw.pop("bg", FARBE["karte"]),
                         anchor="w", **kw)


class Knopf(tk.Canvas):
    """Selbstgezeichneter Knopf. stil='primaer' = helle Fläche, sonst nur Kontur."""

    def __init__(self, eltern, text, befehl, stil="sekundaer", breite=None, hoehe=34,
                 hintergrund=None):
        self.stil = stil
        self.befehl = befehl
        self.aktiv = True
        self._text = text
        schrift = mono(11, fett=(stil == "primaer"))
        breite = breite or schrift.measure(text) + 44
        self.grund = hintergrund or FARBE["karte"]
        super().__init__(eltern, width=breite, height=hoehe, bg=self.grund,
                         highlightthickness=0, cursor="hand2")
        self._zeichne()
        self.bind("<Enter>", lambda _: self._zeichne(ueber=True))
        self.bind("<Leave>", lambda _: self._zeichne())
        self.bind("<Button-1>", self._geklickt)

    def _zeichne(self, ueber=False):
        self.delete("all")
        b, h = int(self["width"]), int(self["height"])
        if not self.aktiv:
            rundes_rechteck(self, 1, 1, b - 1, h - 1, 6,
                            fill=self.grund, outline=FARBE["linie"])
            self.create_text(b / 2, h / 2, text=self._text, font=mono(11),
                             fill=FARBE["text_still"])
            return
        if self.stil == "primaer":
            flaeche = FARBE["akzent_hell"] if ueber else FARBE["akzent"]
            rundes_rechteck(self, 1, 1, b - 1, h - 1, 6, fill=flaeche, outline=flaeche)
            self.create_text(b / 2, h / 2, text=self._text, font=mono(11, fett=True),
                             fill=FARBE["invers"])
        else:
            rand = FARBE["linie_hell"] if ueber else FARBE["linie"]
            fuell = FARBE["karte_hell"] if ueber else self.grund
            rundes_rechteck(self, 1, 1, b - 1, h - 1, 6, fill=fuell, outline=rand)
            self.create_text(b / 2, h / 2, text=self._text, font=mono(11),
                             fill=FARBE["text"] if ueber else FARBE["text_leise"])

    def _geklickt(self, _):
        if self.aktiv:
            self.befehl()

    def beschriften(self, text):
        self._text = text
        self._zeichne()

    def freigeben(self, an=True):
        self.aktiv = an
        self.config(cursor="hand2" if an else "arrow")
        self._zeichne()


class Schieber(tk.Frame):
    """Beschrifteter Regler: Titel und Wert oben, darunter die Bahn zum Ziehen."""

    BAHN_HOEHE = 26

    def __init__(self, eltern, beschriftung, von, bis, wert, einheit="%",
                 nachkomma=0, bei_aenderung=None, breite=250):
        super().__init__(eltern, bg=FARBE["karte"])
        self.von, self.bis = von, bis
        self.wert = wert
        self.nachkomma = nachkomma
        self.einheit = einheit
        self.bei_aenderung = bei_aenderung
        self.breite = breite

        kopf = tk.Frame(self, bg=FARBE["karte"])
        kopf.pack(fill="x")
        tk.Label(kopf, text=gesperrt(beschriftung.upper()), font=mono(8),
                 fg=FARBE["text_still"], bg=FARBE["karte"]).pack(side="left")
        self.wert_label = tk.Label(kopf, font=mono(10), fg=FARBE["text"],
                                   bg=FARBE["karte"])
        self.wert_label.pack(side="right")

        self.bahn = tk.Canvas(self, width=breite, height=self.BAHN_HOEHE,
                              bg=FARBE["karte"], highlightthickness=0, cursor="hand2")
        self.bahn.pack(fill="x", pady=(2, 0))
        self.bahn.bind("<Button-1>", self._gezogen)
        self.bahn.bind("<B1-Motion>", self._gezogen)
        self.bahn.bind("<Configure>", lambda e: self._zeichne(e.width))
        self._zeichne()

    def _zeichne(self, breite=None):
        self.breite = breite or self.breite
        b, mitte = self.breite, self.BAHN_HOEHE / 2
        anteil = (self.wert - self.von) / (self.bis - self.von)
        x = 8 + anteil * (b - 16)
        self.bahn.delete("all")
        self.bahn.create_line(8, mitte, b - 8, mitte, fill=FARBE["linie"], width=2)
        self.bahn.create_line(8, mitte, x, mitte, fill=FARBE["akzent"], width=2)
        self.bahn.create_oval(x - 6, mitte - 6, x + 6, mitte + 6,
                              fill=FARBE["akzent"], outline=FARBE["karte"], width=2)
        self.wert_label.config(text=f"{self.wert:.{self.nachkomma}f} {self.einheit}")

    def _gezogen(self, e):
        b = self.bahn.winfo_width() or self.breite
        anteil = min(1.0, max(0.0, (e.x - 8) / max(1, b - 16)))
        self.wert = self.von + anteil * (self.bis - self.von)
        self._zeichne(b)
        if self.bei_aenderung:
            self.bei_aenderung(self.wert)

    def setzen(self, wert):
        self.wert = min(self.bis, max(self.von, wert))
        self._zeichne()


class EckenWahl(tk.Frame):
    """Vier Kacheln, die je ein Bild mit dem Logo in der jeweiligen Ecke andeuten.

    Die Kacheln teilen sich die verfügbare Breite und wachsen mit dem Fenster.
    Gezeichnet wird deshalb erst, wenn die Leinwand ihre Größe kennt, und danach
    bei jeder Änderung neu — die Maße stehen nicht fest, sondern werden aus der
    tatsächlichen Kachelgröße abgeleitet.
    """

    ORDNUNG = [("oben-links", 0, 0), ("oben-rechts", 0, 1),
               ("unten-links", 1, 0), ("unten-rechts", 1, 1)]
    KACHEL_H = 56
    ABSTAND = 8

    def __init__(self, eltern, wert, bei_aenderung=None):
        super().__init__(eltern, bg=FARBE["karte"])
        self.wert = wert
        self.bei_aenderung = bei_aenderung
        self.kacheln = {}
        # uniform sorgt dafür, dass beide Spalten immer gleich breit bleiben
        self.columnconfigure(0, weight=1, uniform="ecke")
        self.columnconfigure(1, weight=1, uniform="ecke")
        for ecke, zeile, spalte in self.ORDNUNG:
            leinwand = tk.Canvas(self, height=self.KACHEL_H, bg=FARBE["karte"],
                                 highlightthickness=0, cursor="hand2")
            # Abstand auf beide Spalten gleich verteilen, sonst wird die linke
            # Kachel um die Lücke schmaler als die rechte.
            halb = self.ABSTAND // 2
            leinwand.grid(row=zeile, column=spalte, sticky="nsew",
                          padx=(0, halb) if spalte == 0 else (halb, 0),
                          pady=(0, self.ABSTAND) if zeile == 0 else 0)
            leinwand.bind("<Button-1>", lambda _, e=ecke: self._waehlen(e))
            leinwand.bind("<Enter>", lambda _, e=ecke: self._zeichne(e, ueber=True))
            leinwand.bind("<Leave>", lambda _, e=ecke: self._zeichne(e))
            leinwand.bind("<Configure>", lambda _, e=ecke: self._zeichne(e))
            self.kacheln[ecke] = leinwand

    def _zeichne(self, ecke, ueber=False):
        leinwand = self.kacheln[ecke]
        b, h = leinwand.winfo_width(), leinwand.winfo_height()
        if b <= 1 or h <= 1:
            return  # Größe steht noch nicht fest; <Configure> holt das nach
        gewaehlt = ecke == self.wert
        leinwand.delete("all")
        rand = FARBE["akzent"] if gewaehlt else (FARBE["linie_hell"] if ueber
                                                else FARBE["linie"])
        rundes_rechteck(leinwand, 2, 2, b - 2, h - 2, 4,
                        fill=FARBE["karte_hell"] if gewaehlt else FARBE["feld"],
                        outline=rand)
        # angedeutetes Logo, in denselben Verhältnissen wie im echten Bild
        lb, lh = max(14, int(b * 0.34)), max(6, int(h * 0.17))
        abstand_x, abstand_y = max(5, int(b * 0.10)), max(5, int(h * 0.15))
        x = abstand_x if ecke.endswith("links") else b - abstand_x - lb
        y = abstand_y if ecke.startswith("oben") else h - abstand_y - lh
        leinwand.create_rectangle(x, y, x + lb, y + lh,
                                  fill=FARBE["akzent"] if gewaehlt else FARBE["text_still"],
                                  outline="")

    def _waehlen(self, ecke):
        alt, self.wert = self.wert, ecke
        self._zeichne(alt)
        self._zeichne(ecke)
        if self.bei_aenderung:
            self.bei_aenderung(ecke)

    def setzen(self, ecke):
        self._waehlen(ecke)


class Fortschritt(tk.Canvas):
    """Schlichter Balken — eine helle Linie auf dunkler Bahn."""

    def __init__(self, eltern, hoehe=4):
        super().__init__(eltern, height=hoehe, bg=FARBE["karte"], highlightthickness=0)
        self.anteil = 0.0
        self.bind("<Configure>", lambda _: self._zeichne())

    def setzen(self, anteil):
        self.anteil = min(1.0, max(0.0, anteil))
        self._zeichne()

    def _zeichne(self):
        b = self.winfo_width()
        h = int(self["height"])
        self.delete("all")
        self.create_rectangle(0, 0, b, h, fill=FARBE["linie"], outline="")
        if self.anteil > 0:
            self.create_rectangle(0, 0, b * self.anteil, h, fill=FARBE["akzent"], outline="")
