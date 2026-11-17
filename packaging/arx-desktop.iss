; ARX Desktop x64 installer. Build through scripts/build-installer.ps1.

#ifndef MyAppVersion
  #define MyAppVersion "4.0.1b1"
#endif
#ifndef MyAppFileVersion
  #define MyAppFileVersion "4.0.1.1"
#endif
#ifndef MyArtifactVersion
  #define MyArtifactVersion "4.0.1-beta.1"
#endif

#define MyAppName "ARX"
#ifndef MyAppProductName
  #define MyAppProductName "ARX 4"
#endif
#ifndef MyAppDisplayName
  #define MyAppDisplayName "ARX 4.0.1 Beta 1"
#endif
#define MyAppPublisher "chatgptopenaiagi"
#define MyAppURL "https://github.com/chatgptopenaiagi/ARX"
#define MyAppExeName "ARX.exe"
#ifndef MyAppSourceDir
  #define MyAppSourceDir "..\release\ARX-Desktop-win-x64"
#endif

[Setup]
AppId=ARX-{#MyArtifactVersion}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppDisplayName} (Windows x64)
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={autopf}\ARX-{#MyArtifactVersion}
DefaultGroupName={#MyAppDisplayName}
UsePreviousAppDir=no
UsePreviousGroup=no
UsePreviousTasks=no
DisableProgramGroupPage=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
LicenseFile=..\LICENSE
OutputDir=..\release
OutputBaseFilename=ARX-{#MyArtifactVersion}-Setup-Windows-x64
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
CloseApplications=no
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "{#MyAppSourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\ARX"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{group}\Uninstall ARX"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppDisplayName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch ARX"; Flags: nowait postinstall skipifsilent

[Code]
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Entry: TFindRec;
  Destination: String;
begin
  Result := '';
  { A second registration must not replace the uninstall entry of this version. }
  if RegKeyExists(HKLM64, 'Software\Microsoft\Windows\CurrentVersion\Uninstall\ARX-{#MyArtifactVersion}_is1') then
  begin
    Result := 'This ARX version is already installed. Uninstall that version explicitly before reinstalling it. Other ARX versions are preserved.';
    Exit;
  end;
  Destination := ExpandConstant('{app}');
  if FileExists(Destination) then
  begin
    Result := 'Choose a new empty directory. The selected destination is a file.';
    Exit;
  end;
  if DirExists(Destination) then
  begin
    if FindFirst(AddBackslash(Destination) + '*', Entry) then
    begin
      try
        repeat
          if (Entry.Name <> '.') and (Entry.Name <> '..') then
          begin
            Result := 'Choose a new empty directory. This installer preserves existing application and user files and does not perform in-place upgrades.';
            Exit;
          end;
        until not FindNext(Entry);
      finally
        FindClose(Entry);
      end;
    end;
  end;
end;
