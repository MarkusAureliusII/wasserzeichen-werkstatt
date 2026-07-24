# -*- mode: python ; coding: utf-8 -*-
"""Bauplan für PyInstaller — erzeugt Wasserzeichen.exe samt Laufzeit.

Aufruf nicht direkt, sondern über bauen.bat (setzt die Umgebung auf).

Absicht: onedir statt onefile. Eine onefile-exe entpackt sich bei jedem Start in
einen Temp-Ordner — das dauert bei ~200 MB spürbar und lässt sie gegenüber
Windows Defender verdächtiger aussehen. onedir startet sofort.

Der Anwendungscode wird hier bewusst NICHT eingebettet; bauen.bat legt ihn
danach als app/ neben die exe. Nur so bleiben Updates klein.
"""
import os

from PyInstaller.utils.hooks import collect_all

# Relative Pfade in einer Spec löst PyInstaller gegen das Arbeitsverzeichnis auf,
# nicht gegen den Ort der Spec. Da sie mal aus der Wurzel (bauen.bat) und mal aus
# der Cloud aufgerufen wird, alles ausdrücklich von SPECPATH aus rechnen.
WURZEL = os.path.abspath(os.path.join(SPECPATH, ".."))  # noqa: F821 — von PyInstaller gesetzt

datas, binaries, hiddenimports = [], [], []

# Pakete, die Daten oder DLLs mitbringen und die PyInstaller nicht von allein
# vollständig findet. Fehlt eines, ist das kein Abbruchgrund — rawpy etwa wird
# nur für RAW gebraucht.
for paket in ("rawpy", "pillow_heif", "certifi", "tzdata"):
    try:
        d, b, h = collect_all(paket)
        datas += d
        binaries += b
        hiddenimports += h
        print(f"[spec] {paket} eingesammelt")
    except Exception as e:
        print(f"[spec] {paket} übersprungen: {e}")

a = Analysis(
    [os.path.join(WURZEL, "start.py")],
    pathex=[WURZEL],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    # Nichts davon wird gebraucht und alles davon ist groß:
    excludes=["numpy.distutils", "matplotlib", "scipy", "pandas",
              "pytest", "setuptools", "pip", "test", "unittest"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Wasserzeichen",
    debug=False,
    strip=False,
    upx=False,          # UPX-gepackte Dateien schlagen bei Virenscannern öfter an
    console=False,      # sonst öffnet Windows ein schwarzes Konsolenfenster mit
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="Wasserzeichen",
)
