#!/bin/zsh
# Doppelklick-Start: öffnet das Wasserzeichen-Fenster.
# (Ohne Fenster, direkt alles aus input/ verarbeiten: python3 wasserzeichen.py alles)
cd "$(dirname "$0")"
/usr/bin/env python3 oberflaeche.py
