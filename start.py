#!/usr/bin/env python3
"""Startknopf des fertigen Programms — hieraus baut PyInstaller die exe.

Der Trick dieser Datei: sie enthält selbst keine Logik, sondern lädt den
eigentlichen Code aus dem Ordner „app“ neben der exe. Dadurch zerfällt das
Programm in zwei Teile:

    Wasserzeichen.exe + _internal/ + ffmpeg.exe   ~200 MB, ändert sich fast nie
    app/*.py                                       ~50 KB, ändert sich ständig

Ein Update tauscht nur „app“ aus. Das ist ein kleiner Download, und weil dabei
keine ausführbare Datei ersetzt wird, prüft Windows sie auch nicht erneut.

Beim Entwickeln auf dem Mac wird diese Datei nicht gebraucht — dort startet man
oberflaeche.py direkt.
"""
import os
import sys


def _programmordner():
    """Der Ordner, in dem exe und app/ liegen — bei PyInstaller nicht _internal/."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def _abbruch(text):
    """Fehler zeigen. Die exe läuft ohne Konsole, also muss ein Fenster her."""
    try:
        import tkinter as tk
        from tkinter import messagebox
        wurzel = tk.Tk()
        wurzel.withdraw()
        messagebox.showerror("Wasserzeichen", text)
        wurzel.destroy()
    except Exception:
        print(text, file=sys.stderr)
    sys.exit(1)


def main():
    # Sammelimport der Bibliotheken: PyInstaller sieht den Code in app/ nicht und
    # wüsste sonst nicht, was es einpacken soll. Muss vor dem app/-Import stehen.
    import _bibliotheken  # noqa: F401

    app = os.path.join(_programmordner(), "app")
    if not os.path.isdir(app):
        _abbruch("Der Ordner „app“ fehlt neben dem Programm.\n\n"
                 "Das Programm ist unvollständig — bitte neu installieren.")

    # Vorn einfügen, damit app/ Vorrang vor allem hat, was PyInstaller mitgebracht hat.
    sys.path.insert(0, app)

    try:
        import oberflaeche
    except Exception as e:
        _abbruch("Das Programm lässt sich nicht starten.\n\n"
                 f"{type(e).__name__}: {e}\n\n"
                 "Falls gerade ein Update lief: bitte neu installieren.")

    oberflaeche.main()


if __name__ == "__main__":
    main()
