; Inno Setup script. Build: ISCC /DAppVersion=1.2.3 packaging\windows\soloslot.iss
[Setup]
AppId={{e1dfbeda-7f50-404e-8fa7-5ca0b392a2ba}
AppName=soloslot
AppVersion={#AppVersion}
AppPublisher=Sebastian Wallat
AppPublisherURL=https://github.com/swallat/soloslot
DefaultDirName={autopf}\soloslot
DefaultGroupName=soloslot
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\icons\soloslot.ico
WizardImageFile=..\icons\wizard.bmp,..\icons\wizard@2x.bmp
WizardSmallImageFile=..\icons\wizard-small.bmp,..\icons\wizard-small@2x.bmp
UninstallDisplayIcon={app}\soloslot.exe
LicenseFile=..\..\LICENSE
OutputDir=..\..\installers
OutputBaseFilename=soloslot-{#AppVersion}-windows-setup
UninstallDisplayName=soloslot

[Files]
Source: "..\..\dist\soloslot\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion
Source: "..\..\LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"; Flags: ignoreversion
Source: "..\..\src\soloslot\gui\assets\THIRD_PARTY_NOTICES.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\soloslot"; Filename: "{app}\soloslot.exe"
Name: "{autodesktop}\soloslot"; Filename: "{app}\soloslot.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Run]
Filename: "{app}\soloslot.exe"; Description: "Start soloslot"; Flags: nowait postinstall skipifsilent
