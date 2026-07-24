# Windows-Anwendung bauen

Diese Anleitung gilt für die Windows-VM (UTM). PyInstaller kann nicht über
Plattformgrenzen bauen — eine Windows-exe muss auf Windows entstehen.

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
