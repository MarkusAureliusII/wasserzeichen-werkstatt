#!/usr/bin/env python3
"""Sammelimport für den Bau der exe — hier steht keine Logik.

PyInstaller findet die benötigten Bibliotheken, indem es den Quelltext liest.
Der eigentliche Code liegt aber in app/ und wird erst zur Laufzeit geladen, ist
für PyInstaller also unsichtbar. Diese Datei nennt darum alles beim Namen, was
mitgepackt werden muss.

Absichtlich großzügig: Es stehen auch Bibliotheken darin, die heute noch nichts
tun (Netzzugriff, Datenbank, Zeitzonen). Sie kosten wenige Megabyte, ersparen
aber später ein Vollupdate — denn ein Update tauscht nur app/ aus und kann
keine fehlende Bibliothek nachliefern.

Neue Bibliothek nötig? Dann hier eintragen UND eine neue Vollversion ausliefern.
"""

# --- Oberfläche
import tkinter                    # noqa: F401
import tkinter.font               # noqa: F401
import tkinter.filedialog         # noqa: F401
import tkinter.messagebox         # noqa: F401

# --- Bildverarbeitung
import PIL.Image                  # noqa: F401
import PIL.ImageDraw              # noqa: F401
import PIL.ImageFont              # noqa: F401
import PIL.ImageOps               # noqa: F401
import PIL.ImageTk                # noqa: F401

try:
    import pillow_heif            # noqa: F401  — HEIC vom iPhone
    pillow_heif.register_heif_opener()
except ImportError:
    pass

try:
    import rawpy                  # noqa: F401  — RAW unter Windows (Sony .arw)
except ImportError:
    pass

# --- Standardbibliothek, die PyInstaller sonst wegoptimiert
import json                       # noqa: F401
import queue                      # noqa: F401
import shutil                     # noqa: F401
import subprocess                 # noqa: F401
import threading                  # noqa: F401
import zoneinfo                   # noqa: F401  — deutsche Ortszeit für Lauf-Ordner

# --- Auf Vorrat: Netzzugriff für Update-Prüfung und spätere Schnittstellen
import http.client                # noqa: F401
import ssl                        # noqa: F401
import urllib.request             # noqa: F401
import urllib.error               # noqa: F401
import urllib.parse               # noqa: F401
import webbrowser                 # noqa: F401  — Anmeldungen im Browser
import zipfile                    # noqa: F401  — Update-Pakete entpacken
import hashlib                    # noqa: F401  — Prüfsumme heruntergeladener Pakete
import tempfile                   # noqa: F401
import sqlite3                    # noqa: F401  — Warteschlange, Verlauf

try:
    import certifi                # noqa: F401  — Zertifikate für HTTPS unter Windows
except ImportError:
    pass
