; Optional Inno Setup script — turns dist\DragonwildsSync.exe into a proper
; installer with Start Menu + Desktop shortcuts.
;
; 1. Install Inno Setup:  winget install JRSoftware.InnoSetup
; 2. Build the exe first:  .\build.ps1
; 3. Compile:  iscc installer.iss   ->  dist\DragonwildsSync-Setup.exe

[Setup]
AppName=Dragonwilds Sync
AppVersion=1.3.1
AppPublisher=Andor & friends
DefaultDirName={autopf}\Dragonwilds Sync
DefaultGroupName=Dragonwilds Sync
DisableProgramGroupPage=yes
OutputDir=dist
OutputBaseFilename=DragonwildsSync-Setup
SetupIconFile=app\assets\icon.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest

[Files]
Source: "dist\DragonwildsSync.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Dragonwilds Sync"; Filename: "{app}\DragonwildsSync.exe"
Name: "{autodesktop}\Dragonwilds Sync"; Filename: "{app}\DragonwildsSync.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Run]
Filename: "{app}\DragonwildsSync.exe"; Description: "Launch Dragonwilds Sync"; Flags: nowait postinstall skipifsilent
