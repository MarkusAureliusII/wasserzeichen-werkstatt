# Wasserzeichen-Werkstatt

Kleines Desktop-Werkzeug, das ein Logo als Wasserzeichen in Fotos und Videos einbrennt —
stapelweise, über ein Fenster bedienbar, ohne Kommandozeile.

## Funktionen

- **Fotos:** JPG, PNG, HEIC, WebP, TIFF sowie RAW (u. a. Sony ARW)
- **Videos:** MP4, MOV, M4V, MTS, M2TS, MKV, WebM u. a. über ffmpeg, hardwarebeschleunigt
- Platzierung in einer der vier Ecken, Größe, Rand und Deckkraft über Schieberegler
- Live-Vorschau, bevor der Stapel losläuft
- Jeder Durchlauf landet in einem eigenen, datierten Ordner
- Originale werden nie verändert; verarbeitete Dateien wandern nach `input/erledigt/`
- Fehlerhafte Dateien stoppen den Stapel nicht, sondern werden am Ende aufgelistet
- Läuft unter macOS und Windows aus derselben Codebasis

## Aufbau

| Datei | Zweck |
| --- | --- |
| `oberflaeche.py` | Fenster, Bedienung, Vorschau — Einstiegspunkt |
| `wasserzeichen.py` | Bild- und Videoverarbeitung, Einstellungen, Läufe |
| `gestaltung.py` | Selbst gezeichnete Bedienelemente und Farbschema |

Die Bedienelemente sind bewusst selbst gezeichnet, weil macOS Farbangaben an
Standard-Widgets ignoriert — so sieht die Oberfläche auf beiden Systemen gleich aus.

## Voraussetzungen

- Python 3.11 oder neuer
- `pillow`, `pillow-heif`
- `ffmpeg` und `ffprobe` für Videos (im PATH oder neben den Skripten)
- `rawpy` für RAW-Dateien unter Windows (unter macOS übernimmt das `sips`)

## Start

```bash
python3 oberflaeche.py
```

Das Logo wird als `wasserzeichen.png` neben den Skripten erwartet und ist in diesem
Repository nicht enthalten.
