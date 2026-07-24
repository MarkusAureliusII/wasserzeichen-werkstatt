@echo off
setlocal enabledelayedexpansion
title Wasserzeichen bauen

rem ---------------------------------------------------------------------------
rem  AUSWEICHWEG. Der normale Weg ist GitHub Actions: Tag "vX.Y.Z" pushen, dann
rem  entsteht die fertige Setup-Datei am Release. Siehe LIESMICH.md.
rem
rem  Dieses Skript baut nur fuer die Architektur des Rechners, auf dem es
rem  laeuft. Auf einer Apple-Silicon-VM entsteht also eine ARM64-Datei, die auf
rem  einem gewoehnlichen Windows-PC NICHT startet.
rem
rem  ACHTUNG BEIM BEARBEITEN: Diese Datei muss reines ASCII bleiben. cmd.exe
rem  liest Batch-Dateien byteweise; ein Umlaut oder Gedankenstrich verschiebt
rem  die Leseposition und zersaegt die folgenden Zeilen. Deshalb hier keine
rem  Sonderzeichen und kein chcp.
rem ---------------------------------------------------------------------------

cd /d "%~dp0.."
set "WURZEL=%CD%"
set "BAU=%WURZEL%\windows"
set "ZIEL=%WURZEL%\dist\Wasserzeichen"

echo.
echo ===============================================
echo   Wasserzeichen - Windows-Anwendung bauen
echo ===============================================
echo Projektordner: %WURZEL%
echo.

rem --- 1. Python finden -------------------------------------------------------
rem Nicht mit "where" pruefen: Windows legt einen Platzhalter namens python.exe
rem ab, der nur auf den Microsoft Store verweist. Nur ein echter Aufruf zeigt,
rem ob Python wirklich da ist.
set "PY="

py -3 --version >nul 2>&1
if not errorlevel 1 set "PY=py -3"

if not defined PY (
    python --version >nul 2>&1
    if not errorlevel 1 set "PY=python"
)

if not defined PY (
    echo FEHLER: Es ist kein funktionierendes Python installiert.
    echo.
    echo Falls eine Meldung wie "Python was not found" erschien, ist nur der
    echo Platzhalter des Microsoft Store vorhanden, nicht Python selbst.
    echo.
    echo Abhilfe:  winget install Python.Python.3.12
    echo Danach dieses Fenster schliessen und das Skript neu starten.
    pause
    exit /b 1
)

for /f "tokens=*" %%v in ('%PY% --version 2^>^&1') do set "PYVER=%%v"
echo [1/6] Python gefunden: !PYVER!

rem --- 2. Virtuelle Umgebung --------------------------------------------------
if not exist "%BAU%\.venv\Scripts\python.exe" (
    echo [2/6] Virtuelle Umgebung wird angelegt ...
    if exist "%BAU%\.venv" rmdir /s /q "%BAU%\.venv"
    %PY% -m venv "%BAU%\.venv"
    if errorlevel 1 goto :fehler
) else (
    echo [2/6] Virtuelle Umgebung vorhanden.
)
call "%BAU%\.venv\Scripts\activate.bat"
if errorlevel 1 goto :fehler

rem --- 3. Bibliotheken --------------------------------------------------------
echo [3/6] Bibliotheken werden installiert. Beim ersten Mal dauert das etwas.
python -m pip install --upgrade pip --quiet
python -m pip install --quiet --requirement "%BAU%\anforderungen.txt"
if errorlevel 1 goto :fehler

rem --- 4. PyInstaller ---------------------------------------------------------
echo [4/6] Anwendung wird gepackt ...
if exist "%WURZEL%\build" rmdir /s /q "%WURZEL%\build"
if exist "%ZIEL%" rmdir /s /q "%ZIEL%"
pyinstaller --noconfirm --clean --distpath "%WURZEL%\dist" --workpath "%WURZEL%\build" "%BAU%\wasserzeichen.spec"
if errorlevel 1 goto :fehler
if not exist "%ZIEL%\Wasserzeichen.exe" (
    echo FEHLER: Wasserzeichen.exe wurde nicht erzeugt.
    goto :fehler
)

rem --- 5. Anwendungscode und Werkzeuge danebenlegen ---------------------------
echo [5/6] Anwendungscode und ffmpeg werden abgelegt ...
if not exist "%ZIEL%\app" mkdir "%ZIEL%\app"
copy /y "%WURZEL%\oberflaeche.py"   "%ZIEL%\app\" >nul
copy /y "%WURZEL%\wasserzeichen.py" "%ZIEL%\app\" >nul
copy /y "%WURZEL%\gestaltung.py"    "%ZIEL%\app\" >nul
copy /y "%WURZEL%\version.txt"      "%ZIEL%\app\" >nul
copy /y "%BAU%\ANLEITUNG.txt"       "%ZIEL%\"    >nul

set "FEHLT="
if not exist "%BAU%\werkzeuge\ffmpeg.exe"  set "FEHLT=1"
if not exist "%BAU%\werkzeuge\ffprobe.exe" set "FEHLT=1"
if defined FEHLT (
    echo.
    echo HINWEIS: ffmpeg.exe und ffprobe.exe fehlen in windows\werkzeuge\.
    echo Fotos funktionieren, Videos nicht. Siehe LIESMICH.md.
    echo.
) else (
    copy /y "%BAU%\werkzeuge\ffmpeg.exe"  "%ZIEL%\" >nul
    copy /y "%BAU%\werkzeuge\ffprobe.exe" "%ZIEL%\" >nul
)

rem --- 6. Installer -----------------------------------------------------------
echo [6/6] Installer ...
set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe"      set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"

if defined ISCC (
    "%ISCC%" "%BAU%\installer.iss"
    if errorlevel 1 goto :fehler
    echo Installer liegt in: %WURZEL%\dist\installer\
) else (
    echo Inno Setup 6 nicht gefunden, Installer wird weggelassen.
    echo Die fertige Anwendung liegt trotzdem in: %ZIEL%
)

echo.
echo ===============================================
echo   Fertig.
echo ===============================================
echo Anwendung: %ZIEL%\Wasserzeichen.exe
echo.
pause
exit /b 0

:fehler
echo.
echo ===============================================
echo   ABGEBROCHEN - siehe Meldung oben.
echo ===============================================
pause
exit /b 1
