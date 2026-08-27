; ARX Desktop x64 installer. Build through scripts/build-installer.ps1.

#ifndef MyAppVersion
  #define MyAppVersion "3.0.0rc1"
#endif
#ifndef MyAppFileVersion
  #define MyAppFileVersion "3.0.0.1"
#endif
#ifndef MyArtifactVersion
  #define MyArtifactVersion "3.0.0-rc1"
#endif

#define MyAppName "ARX"
#ifndef MyAppProductName
  #define MyAppProductName "ARX 3"
#endif
#ifndef MyAppDisplayName
  #define MyAppDisplayName "ARX 3.0 Release Candidate 1"
#endif
#define MyAppPublisher "chatgptopenaiagi"
#define MyAppURL "https://github.com/chatgptopenaiagi/ARX"
#define MyAppExeName "ARX.exe"
#define MyAppSourceDir "..\release\ARX-Desktop-win-x64"

[Setup]
AppId={{1BC9E705-070A-42B4-9378-45E2DD7C416A}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppDisplayName} (Windows x64)
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
OutputBaseFilename=ARX-Desktop-Setup-win-x64-v{#MyArtifactVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppDisplayName} (Windows x64)
VersionInfoVersion={#MyAppFileVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppDisplayName} installer
VersionInfoProductName={#MyAppProductName}
VersionInfoProductVersion={#MyAppFileVersion}
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
