; ARX Desktop x64 installer. Build through scripts/build-installer.ps1.

#ifndef MyAppVersion
  #define MyAppVersion "2.0.0"
#endif

#define MyAppName "ARX"
#define MyAppPublisher "chatgptopenaiagi"
#define MyAppURL "https://github.com/chatgptopenaiagi/ARX"
#define MyAppExeName "ARX.exe"
#define MyAppSourceDir "..\release\ARX-Desktop-win-x64"

[Setup]
AppId={{1BC9E705-070A-42B4-9378-45E2DD7C416A}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion} (Windows x64)
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={autopf}\ARX
DefaultGroupName=ARX
DisableProgramGroupPage=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
LicenseFile=..\LICENSE
OutputDir=..\release
OutputBaseFilename=ARX-Desktop-Setup-win-x64-v{#MyAppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName} {#MyAppVersion} (Windows x64)
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription=ARX Project-Aware Compatibility Intelligence installer
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "{#MyAppSourceDir}\ARX.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#MyAppSourceDir}\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#MyAppSourceDir}\README.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"; Flags: ignoreversion

[Icons]
Name: "{group}\ARX"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{group}\Uninstall ARX"; Filename: "{uninstallexe}"
Name: "{autodesktop}\ARX"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch ARX"; Flags: nowait postinstall skipifsilent
