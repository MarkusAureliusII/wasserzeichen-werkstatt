# Windows-Anwendung bauen

## Der normale Weg: GitHub Actions

Gebaut wird in der Cloud, nicht von Hand. Ein Tag genügt:

```
# version.txt auf die neue Nummer setzen, dann:
git commit -am "Version 1.1.0"
git tag v1.1.0
git push && git push --tags
```

Der Workflow `.github/workflows/windows-bauen.yml` baut daraufhin auf einem
Windows-x64-Rechner und hängt Setup-Datei und Update-Paket an ein Release unter
<https://github.com/MarkusAureliusII/wasserzeichen-werkstatt/releases>.

Ohne Tag lässt sich der Bau auch von Hand unter „Actions" auslösen — dann
entsteht kein Release, die Dateien liegen 30 Tage als Artefakt bereit.

**Warum nicht in der VM?** Eine Apple-Silicon-VM läuft auf aarch64, und eine dort
gebaute exe startet auf einem gewöhnlichen Windows-PC nicht. x64 dagegen läuft
überall, auch auf Windows-on-ARM. Die VM ist zum *Ausprobieren* der fertigen
Setup-Datei gut, zum Bauen nicht.

**Die Versionsnummer muss zum Tag passen** — der Workflow bricht sonst ab.

---

## Der Ausweichweg: von Hand in einer Windows-VM

Nur nötig, wenn GitHub Actions einmal nicht verfügbar ist. Achtung: Das Ergebnis
passt zur Architektur der VM — auf Apple Silicon also ARM64, nicht x64.

## Einmalig einrichten

**1. Python installieren**

Aus dem Microsoft Store („Python 3.12") oder von python.org. Bei der
Installation von python.org unbedingt *„Add python.exe to PATH"* ankreuzen.

**2. Git installieren und das Projekt holen**

```
winget install Git.Git
git clone https://github.com/MarkusAureliusII/wasserzeichen-werkstatt.git
```

**3. ffmpeg besorgen**

Von https://www.gyan.dev/ffmpeg/builds/ das Paket *„release essentials"*
herunterladen, entpacken, und aus dessen `bin`-Ordner diese zwei Dateien
hierher nach `windows\werkzeuge\` kopieren:

```
ffmpeg.exe
ffprobe.exe
```

Ohne sie funktionieren Fotos, aber keine Videos.

**4. Logo und Beschriftung ablegen**

Nach `windows\daten\` gehören:

```
wasserzeichen.png    das freigestellte Logo
beschriftung.json    die Aufschriften im Fensterkopf
```

Beide stehen bewusst nicht im Repository — sie enthalten Kundendaten. Einmal in
die VM kopieren genügt, sie bleiben dort liegen.

**5. Inno Setup 6 installieren** (optional, nur für die Setup-Datei)

```
winget install JRSoftware.InnoSetup
```

Ohne Inno Setup entsteht trotzdem eine lauffähige Anwendung in `dist\Wasserzeichen\`
— nur eben keine Setup-Datei zum Weitergeben.

## Bauen

Doppelklick auf `bauen.bat`. Der erste Durchlauf dauert einige Minuten (die
virtuelle Umgebung wird angelegt und die Bibliotheken geladen), spätere nur noch
etwa eine Minute.

Ergebnis:

```
dist\Wasserzeichen\Wasserzeichen.exe      zum Testen direkt startbar
dist\installer\Wasserzeichen-1.0.0-Setup.exe   zum Weitergeben
```

## Was wohin gehört

Der Aufbau ist bewusst zweigeteilt, damit Updates klein bleiben:

```
Wasserzeichen.exe    Startknopf                 ~2 MB    ändert sich nie
_internal\           Python samt Bibliotheken   ~180 MB  ändert sich fast nie
ffmpeg.exe           Videoverarbeitung          ~80 MB   ändert sich fast nie
app\                 der eigentliche Programmcode ~50 KB ändert sich ständig
```

Ein Update tauscht nur `app\` aus. Deshalb liegt der Code dort als lose
`.py`-Dateien und nicht in der exe.

Nutzdaten liegen getrennt davon in `Dokumente\Wasserzeichen\` und überleben
jede Neuinstallation.

## Neue Bibliothek nötig?

Dann reicht ein kleines Update **nicht** aus. In dem Fall:

1. Paket in `anforderungen.txt` eintragen
2. Import in `..\_bibliotheken.py` ergänzen
3. Neu bauen und eine vollständige Setup-Datei ausliefern

Alles, was ohne neue Bibliothek auskommt — Oberfläche, Texte, Abläufe,
Schnittstellen über HTTPS — geht als kleines Update.

## Version erhöhen

Nur in `..\version.txt`. Von dort lesen sowohl das Programm als auch der
Installer.
