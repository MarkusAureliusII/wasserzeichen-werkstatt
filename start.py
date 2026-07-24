#!/usr/bin/env python3
"""Startknopf des fertigen Programms — hieraus baut PyInstaller die exe.

Der Trick dieser Datei: sie enthält selbst keine Logik, sondern lädt den
eigentlichen Code aus dem Ordner „app“ neben der exe. Dadurch zerfällt das
Programm in zwei Teile:

    Wasserzeichen.exe + _internal/ + ffmpeg.exe   ~200 MB, ändert sich fast nie
    app/*.py                                       ~50 KB, ändert sich ständig

Ein Update tauscht nur „app“ aus. Das ist ein kleiner Download, und weil dabei
keine ausführbare Datei ersetzt wird, prüft Windows sie auch nicht erneut.

Der Tausch passiert HIER und nicht im laufenden Programm: Der Updater legt die
neue Fassung nur als „app.neu“ bereit: beim nächsten Start wird sie eingesetzt,
solange noch keine Datei daraus in Benutzung ist. Die bisherige Fassung bleibt
als „app.alt“ liegen, bis das Fenster nachweislich stand — startet die neue
nicht, schaltet dieser Starter von allein zurück.

ACHTUNG: Diese Datei steckt in der exe und lässt sich nicht per Update
nachbessern. Änderungen hier brauchen immer ein neues Setup.

Beim Entwickeln auf dem Mac wird sie nicht gebraucht — dort startet man
oberflaeche.py direkt.
"""
import os
import shutil
import subprocess
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


def _hinweis(text):
    """Kurze Mitteilung, die den Start nicht abbricht."""
    try:
        import tkinter as tk
        from tkinter import messagebox
        wurzel = tk.Tk()
        wurzel.withdraw()
        messagebox.showinfo("Wasserzeichen", text)
        wurzel.destroy()
    except Exception:
        print(text, file=sys.stderr)


def _weg(pfad):
    """Ordner entfernen, ohne bei Kleinigkeiten zu stolpern."""
    shutil.rmtree(pfad, ignore_errors=True)


def _update_einsetzen(app, neu, alt):
    """Eine bereitgelegte neue Fassung übernehmen. Läuft vor jedem Import."""
    if not os.path.isdir(neu):
        return False
    try:
        _weg(alt)
        if os.path.isdir(app):
            os.rename(app, alt)
        os.rename(neu, app)
        return True
    except OSError:
        # Tausch misslungen: alles so lassen, wie es war, und weiterlaufen.
        if not os.path.isdir(app) and os.path.isdir(alt):
            try:
                os.rename(alt, app)
            except OSError:
                pass
        _weg(neu)
        return False


def _zuruecknehmen(app, alt):
    """Auf die vorherige Fassung zurückschalten, wenn die neue nicht startet."""
    try:
        _weg(app + ".kaputt")
        if os.path.isdir(app):
            os.rename(app, app + ".kaputt")
        os.rename(alt, app)
        return True
    except OSError:
        return False


def _neu_starten():
    """Sich selbst noch einmal starten und den alten Vorgang beenden."""
    if getattr(sys, "frozen", False):
        befehl = [sys.executable]
    else:
        befehl = [sys.executable, os.path.abspath(__file__)]
    subprocess.Popen(befehl, close_fds=True)
    sys.exit(0)


def main():
    # Sammelimport der Bibliotheken: PyInstaller sieht den Code in app/ nicht und
    # wüsste sonst nicht, was es einpacken soll. Muss vor dem app/-Import stehen.
    import _bibliotheken  # noqa: F401

    prog = _programmordner()
    app = os.path.join(prog, "app")
    neu = os.path.join(prog, "app.neu")
    alt = os.path.join(prog, "app.alt")

    frisch_eingesetzt = _update_einsetzen(app, neu, alt)

    if not os.path.isdir(app):
        _abbruch("Der Ordner „app“ fehlt neben dem Programm.\n\n"
                 "Das Programm ist unvollständig — bitte neu installieren.")

    # Vorn einfügen, damit app/ Vorrang vor allem hat, was PyInstaller mitgebracht hat.
    sys.path.insert(0, app)

    try:
        import oberflaeche
        # Der Rückfall wird erst verworfen, wenn das Fenster wirklich stand.
        oberflaeche.main(nach_start=lambda: _weg(alt))
    except Exception as e:
        if os.path.isdir(alt) and _zuruecknehmen(app, alt):
            _hinweis("Die neue Fassung ließ sich nicht starten.\n\n"
                     "Die vorherige wird wiederhergestellt, das Programm startet neu.")
            _neu_starten()
        _abbruch("Das Programm lässt sich nicht starten.\n\n"
                 f"{type(e).__name__}: {e}\n\n"
                 + ("Das Update ist fehlgeschlagen — bitte neu installieren."
                    if frisch_eingesetzt else
                    "Bitte das Programm neu installieren."))


if __name__ == "__main__":
    main()
