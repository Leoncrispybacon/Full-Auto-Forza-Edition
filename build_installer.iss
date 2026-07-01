; build_installer.iss — Inno Setup script for Full Auto Forza Edition
; -----------------------------------------------------------------------------
; Why an installer: a downloaded ZIP carries "Mark of the Web" (MOTW), and .NET
; refuses to load a MOTW-flagged DLL — that's the "Failed to resolve
; Python.Runtime.Loader.Initialize" crash. Files written by an INSTALLER do NOT
; inherit MOTW, so the runtime DLLs load with no manual Unblock step.
;
; Build:
;   1. Run build_app.bat  (produces FAFE_dist\ next to this file).
;   2. Install Inno Setup (free): https://jrsoftware.org/isdl.php
;   3. Open this .iss in Inno Setup and click Build (or: ISCC.exe build_installer.iss)
;   -> produces Output\FAFE_Setup.exe
;
; Note: bump MyAppVersion each release to match version.py. SmartScreen may still
; show an "unknown publisher" prompt on first run (that needs code signing to
; remove) — but the DLL-load block is gone, which is the issue here.
; -----------------------------------------------------------------------------

#define MyAppName "Full Auto Forza Edition"
#define MyAppVersion "2.0.4"
#define MyAppExe "FAFE.exe"

[Setup]
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=Leonbacon
DefaultDirName={autopf}\FAFE
DefaultGroupName={#MyAppName}
; Version-less name so the website's releases/latest/download/FAFE_Setup.exe
; link stays valid every release (internal version shown via AppVersion).
OutputBaseFilename=FAFE_Setup
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; Install per-user so no admin/UAC prompt is needed (avoids AV friction too).
PrivilegesRequired=lowest
DisableProgramGroupPage=yes
WizardStyle=modern
SetupIconFile=FAFE_icon.ico
UninstallDisplayIcon={app}\{#MyAppExe}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
; To add a Traditional Chinese wizard, install the unofficial ChineseTraditional.isl
; into Inno Setup's Languages\ folder, then add:
;   Name: "chinesetrad"; MessagesFile: "compiler:Languages\ChineseTraditional.isl"
; (the APP itself is already bilingual; the wizard language is cosmetic.)

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; The whole built app folder. recursesubdirs keeps _internal\ etc.
Source: "FAFE_dist\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"; Tasks: desktopicon

[Run]
; Offer to launch after install. WebView2 runtime check happens inside FAFE.exe.
Filename: "{app}\{#MyAppExe}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent
