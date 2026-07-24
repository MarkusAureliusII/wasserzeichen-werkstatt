; Inno Setup 6 — baut aus dem fertigen dist\Wasserzeichen\ eine Setup-Datei.
; Wird von bauen.bat aufgerufen, lässt sich aber auch direkt in Inno Setup öffnen.
;
; Drei Festlegungen sind hier wichtig und kein Zufall:
;
;   1. Installation nach LocalAppData statt "Programme". Damit braucht weder die
;      Installation noch ein späteres Update Administratorrechte — ein Update,
;      das nach einem Passwort fragt, scheitert beim Endnutzer schlicht.
;   2. Fotos, Logo und Einstellungen liegen NICHT im Programmordner, sondern
;      unter "%USERPROFILE%\Wasserzeichen". Eine Neuinstallation kann sie damit
;      nicht versehentlich mitlöschen.
;   3. Bewusst dort und nicht unter "Dokumente": OneDrive übernimmt Desktop,
;      Dokumente und Bilder und würde jedes verarbeitete Foto und Video in die
;      Cloud schieben — bei Veranstaltungsaufnahmen schnell mehrere Gigabyte.
;      Das Benutzerverzeichnis selbst rührt OneDrive nicht an.

#define Name      "Wasserzeichen"
#define Exe       "Wasserzeichen.exe"

; Versionsnummer aus version.txt — damit sie nur an einer Stelle gepflegt wird.
#define VersionDatei FileOpen("..\version.txt")
#define Version Trim(FileRead(VersionDatei))
#expr FileClose(VersionDatei)

; Windows-Dateiversionen müssen rein numerisch sein. Bei einer Vorabversion wie
; "1.0.0-beta.1" wird der Zusatz dafür abgeschnitten; angezeigt wird weiter die
; vollständige Bezeichnung.
#define VersionNum Version
#if Pos("-", Version) > 0
  #define VersionNum Copy(Version, 1, Pos("-", Version) - 1)
#endif

[Setup]
AppId={{8F3C1A62-4D77-4C0E-9E21-5B7A2F9D4E10}
AppName={#Name}
AppVersion={#Version}
AppVerName={#Name} {#Version}
VersionInfoVersion={#VersionNum}
DefaultDirName={localappdata}\Programs\Wasserzeichen
DefaultGroupName={#Name}
DisableProgramGroupPage=yes
DisableDirPage=yes
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist\installer
OutputBaseFilename=Wasserzeichen-{#Version}-Setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName={#Name}
UninstallDisplayIcon={app}\{#Exe}
; Kein Neustart, keine Systemänderung — das Programm ist reine Anwendung.
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "deutsch"; MessagesFile: "compiler:Languages\German.isl"

[Tasks]
Name: "desktopicon"; Description: "Verknüpfung auf dem Desktop anlegen"; \
    GroupDescription: "Zusätzliche Verknüpfungen:"

[Files]
; Programm samt Laufzeit und app\ — wird bei jeder Installation ersetzt.
Source: "..\dist\Wasserzeichen\*"; DestDir: "{app}"; \
    Flags: ignoreversion recursesubdirs createallsubdirs

; Nutzdaten: nur anlegen, wenn noch nicht vorhanden. "onlyifdoesntexist"
; schützt das eingerichtete Logo und die Einstellungen bei einer Neuinstallation.
Source: "daten\wasserzeichen.png"; DestDir: "{%USERPROFILE}\Wasserzeichen"; \
    Flags: onlyifdoesntexist uninsneveruninstall skipifsourcedoesntexist
Source: "daten\beschriftung.json"; DestDir: "{%USERPROFILE}\Wasserzeichen"; \
    Flags: onlyifdoesntexist uninsneveruninstall skipifsourcedoesntexist
Source: "ANLEITUNG.txt"; DestDir: "{%USERPROFILE}\Wasserzeichen"; \
    Flags: ignoreversion uninsneveruninstall

[Dirs]
; Ablageordner vorab anlegen, damit sie nach der Installation schon sichtbar sind.
Name: "{%USERPROFILE}\Wasserzeichen"; Flags: uninsneveruninstall
Name: "{%USERPROFILE}\Wasserzeichen\input"; Flags: uninsneveruninstall
Name: "{%USERPROFILE}\Wasserzeichen\input\erledigt"; Flags: uninsneveruninstall
Name: "{%USERPROFILE}\Wasserzeichen\output"; Flags: uninsneveruninstall

[Icons]
Name: "{group}\{#Name}"; Filename: "{app}\{#Exe}"
Name: "{group}\Ablageordner öffnen"; Filename: "{%USERPROFILE}\Wasserzeichen"
Name: "{group}\{#Name} deinstallieren"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#Name}"; Filename: "{app}\{#Exe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#Exe}"; Description: "{#Name} jetzt starten"; \
    Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Beim Deinstallieren nur Programmreste entfernen — Nutzdaten bleiben unberührt.
; app.alt und app.neu entstehen beim Aktualisieren und koennen ebenfalls weg.
Type: filesandordirs; Name: "{app}\app"
Type: filesandordirs; Name: "{app}\app.alt"
Type: filesandordirs; Name: "{app}\app.neu"
Type: filesandordirs; Name: "{app}\app.kaputt"
Type: filesandordirs; Name: "{app}\_internal"
