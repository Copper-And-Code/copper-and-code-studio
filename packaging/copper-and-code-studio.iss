#ifndef MyAppVersion
#define MyAppVersion "0.6.0"
#endif

[Setup]
LicenseFile=..\LICENSE
AppId={{7D653C2E-4AF5-4D5B-9C49-8C2AC98A3E10}
AppName=Copper and Code Studio
AppVersion={#MyAppVersion}
AppPublisher=Nunzio Raciti
DefaultDirName={localappdata}\Programs\Copper and Code Studio
DefaultGroupName=Copper and Code Studio
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=Copper_and_Code_Studio-{#MyAppVersion}-Setup-win64
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\copper_and_code_studio\icon.ico
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\Copper_and_Code_Studio.exe

[Files]
Source: "..\dist\Copper_and_Code_Studio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; Same AppId as LVGL MPY Studio: this installer upgrades that installation, in its folder.
; The program and the shortcuts under the old name are removed, so that only one is left.
[InstallDelete]
Type: files; Name: "{app}\LVGL_MPY_STUDIO.exe"
Type: files; Name: "{group}\LVGL MPY Studio.lnk"
Type: files; Name: "{group}\Disinstalla LVGL MPY Studio.lnk"

[Icons]
Name: "{group}\Copper and Code Studio"; Filename: "{app}\Copper_and_Code_Studio.exe"
Name: "{group}\Uninstall Copper and Code Studio"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\Copper_and_Code_Studio.exe"; Description: "Start Copper and Code Studio"; Flags: nowait postinstall skipifsilent
