@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
title Wasserzeichen bauen

rem ---------------------------------------------------------------------------
rem  Baut aus dem Quelltext eine fertige Windows-Anwendung.
rem  Laeuft in der Windows-VM. Doppelklick genuegt.
rem
rem  Voraussetzungen (einmalig, siehe windows\LIESMICH.md):
rem    - Python 3.11+ aus dem Microsoft Store oder von python.org
rem    - ffmpeg.exe und ffprobe.exe in windows\werkzeuge\
rem    - optional: Inno Setup 6, wenn ein Installer entstehen soll
rem ---------------------------------------------------------------------------

cd /d "%~dp0.."
set "WURZEL=%CD%"
set "BAU=%WURZEL%\windows"
set "ZIEL=%WURZEL%\dist\Wasserzeichen"

echo.
echo ===============================================
echo   Wasserzeichen — Windows-Anwendung bauen
echo ===============================================
echo Projektordner: %WURZEL%
echo.

rem --- 1. Python finden ------------------------------------------------------
where py >nul 2>&1
if %errorlevel%==0 (
    set "PY=py -3"
) else (
    where python >nul 2>&1
    if !errorlevel!==0 (
        set "PY=python"
    ) else (
        echo FEHLER: Python wurde nicht gefunden.
        echo Bitte Python 3.11 oder neuer installieren und beim Setup
        echo "Add python.exe to PATH" ankreuzen.
        pause
        exit /b 1
    )
)
echo [1/6] Python gefunden.

rem --- 2. Virtuelle Umgebung -------------------------------------------------
if not exist "%BAU%\.venv" (
    echo [2/6] Virtuelle Umgebung wird angelegt ...
    %PY% -m venv "%BAU%\.venv"
    if errorlevel 1 goto :fehler
) else (
    echo [2/6] Virtuelle Umgebung vorhanden.
)
call "%BAU%\.venv\Scripts\activate.bat"

rem --- 3. Bibliotheken -------------------------------------------------------
echo [3/6] Bibliotheken werden installiert (dauert beim ersten Mal einige Minuten) ...
python -m pip install --upgrade pip --quiet
python -m pip install --quiet --requirement "%BAU%\anforderungen.txt"
if errorlevel 1 goto :fehler

rem --- 4. PyInstaller --------------------------------------------------------
echo [4/6] Anwendung wird gepackt ...
if exist "%WURZEL%\build" rmdir /s /q "%WURZEL%\build"
if exist "%ZIEL%" rmdir /s /q "%ZIEL%"
pyinstaller --noconfirm --clean ^
    --distpath "%WURZEL%\dist" --workpath "%WURZEL%\build" ^
    "%BAU%\wasserzeichen.spec"
if errorlevel 1 goto :fehler
if not exist "%ZIEL%\Wasserzeichen.exe" (
    echo FEHLER: Wasserzeichen.exe wurde nicht erzeugt.
    goto :fehler
)

rem --- 5. Anwendungscode und Werkzeuge danebenlegen --------------------------
echo [5/6] Anwendungscode und ffmpeg werden abgelegt ...
mkdir "%ZIEL%\app" 2>nul
copy /y "%WURZEL%\oberflaeche.py"   "%ZIEL%\app\" >nul
copy /y "%WURZEL%\wasserzeichen.py" "%ZIEL%\app\" >nul
copy /y "%WURZEL%\gestaltung.py"    "%ZIEL%\app\" >nul
copy /y "%WURZEL%\version.txt"      "%ZIEL%\app\" >nul

set "FEHLT="
if not exist "%BAU%\werkzeuge\ffmpeg.exe"  set "FEHLT=1"
if not exist "%BAU%\werkzeuge\ffprobe.exe" set "FEHLT=1"
if defined FEHLT (
    echo.
    echo WARNUNG: ffmpeg.exe / ffprobe.exe fehlen in windows\werkzeuge\.
    echo Fotos funktionieren, Videos NICHT. Siehe windows\LIESMICH.md.
    echo.
) else (
    copy /y "%BAU%\werkzeuge\ffmpeg.exe"  "%ZIEL%\" >nul
    copy /y "%BAU%\werkzeuge\ffprobe.exe" "%ZIEL%\" >nul
)

rem --- 6. Installer ----------------------------------------------------------
echo [6/6] Installer ...
set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe"      set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"

if defined ISCC (
    "%ISCC%" "%BAU%\installer.iss"
    if errorlevel 1 goto :fehler
    echo Installer liegt in: %WURZEL%\dist\installer\
) else (
    echo Inno Setup 6 nicht gefunden — Installer uebersprungen.
    echo Die fertige Anwendung liegt trotzdem in: %ZIEL%
)

echo.
echo ===============================================
echo   Fertig.
echo ===============================================
echo Anwendung: %ZIEL%\Wasserzeichen.exe
echo.
echo Zum Testen einfach dort doppelklicken.
pause
exit /b 0

:fehler
echo.
echo ===============================================
echo   ABGEBROCHEN — siehe Meldung oben.
echo ===============================================
pause
exit /b 1
