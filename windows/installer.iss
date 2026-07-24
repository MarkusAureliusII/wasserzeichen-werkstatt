; Inno Setup 6 — baut aus dem fertigen dist\Wasserzeichen\ eine Setup-Datei.
; Wird von bauen.bat aufgerufen, lässt sich aber auch direkt in Inno Setup öffnen.
;
; Zwei Festlegungen sind hier wichtig und kein Zufall:
;
;   1. Installation nach LocalAppData statt "Programme". Damit braucht weder die
;      Installation noch ein späteres Update Administratorrechte — ein Update,
;      das nach einem Passwort fragt, scheitert beim Endnutzer schlicht.
;   2. Fotos, Logo und Einstellungen liegen NICHT im Programmordner, sondern
;      unter "Dokumente\Wasserzeichen". Eine Neuinstallation kann sie damit
;      nicht versehentlich mitlöschen.

#define Name      "Wasserzeichen"
#define Exe       "Wasserzeichen.exe"

; Versionsnummer aus version.txt — damit sie nur an einer Stelle gepflegt wird.
#define VersionDatei FileOpen("..\version.txt")
#define Version Trim(FileRead(VersionDatei))
#expr FileClose(VersionDatei)

[Setup]
AppId={{8F3C1A62-4D77-4C0E-9E21-5B7A2F9D4E10}
AppName={#Name}
AppVersion={#Version}
AppVerName={#Name} {#Version}
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
Source: "daten\wasserzeichen.png"; DestDir: "{userdocs}\Wasserzeichen"; \
    Flags: onlyifdoesntexist uninsneveruninstall skipifsourcedoesntexist
Source: "daten\beschriftung.json"; DestDir: "{userdocs}\Wasserzeichen"; \
    Flags: onlyifdoesntexist uninsneveruninstall skipifsourcedoesntexist
Source: "ANLEITUNG.txt"; DestDir: "{userdocs}\Wasserzeichen"; \
    Flags: ignoreversion uninsneveruninstall

[Dirs]
; Ablageordner vorab anlegen, damit sie nach der Installation schon sichtbar sind.
Name: "{userdocs}\Wasserzeichen"; Flags: uninsneveruninstall
Name: "{userdocs}\Wasserzeichen\input"; Flags: uninsneveruninstall
Name: "{userdocs}\Wasserzeichen\input\erledigt"; Flags: uninsneveruninstall
Name: "{userdocs}\Wasserzeichen\output"; Flags: uninsneveruninstall

[Icons]
Name: "{group}\{#Name}"; Filename: "{app}\{#Exe}"
Name: "{group}\Ablageordner öffnen"; Filename: "{userdocs}\Wasserzeichen"
Name: "{group}\{#Name} deinstallieren"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#Name}"; Filename: "{app}\{#Exe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#Exe}"; Description: "{#Name} jetzt starten"; \
    Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Beim Deinstallieren nur Programmreste entfernen — Dokumente bleiben unberührt.
Type: filesandordirs; Name: "{app}\app"
Type: filesandordirs; Name: "{app}\_internal"
