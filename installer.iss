; Optional Inno Setup script - turns dist\WorldSync.exe into a proper
; installer with Start Menu + Desktop shortcuts.
;
; 1. Install Inno Setup:  winget install JRSoftware.InnoSetup
; 2. Build the exe first:  .\build.ps1
; 3. Compile:  iscc installer.iss   ->  dist\WorldSync-Setup.exe

[Setup]
AppName=WorldSync
AppVersion=2.1.1
AppPublisher=AndorManu
DefaultDirName={autopf}\WorldSync
DefaultGroupName=WorldSync
DisableProgramGroupPage=yes
OutputDir=dist
OutputBaseFilename=WorldSync-Setup
SetupIconFile=app\assets\icon.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest

[Files]
Source: "dist\WorldSync.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\WorldSync"; Filename: "{app}\WorldSync.exe"
Name: "{autodesktop}\WorldSync"; Filename: "{app}\WorldSync.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Run]
Filename: "{app}\WorldSync.exe"; Description: "Launch WorldSync"; Flags: nowait postinstall skipifsilent
