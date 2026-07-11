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
#define MyAppVersion "2.1.3"
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
; Silent auto-update: close the running FAFE via Restart Manager so the locked
; files can be replaced (`FAFE_Setup.exe /VERYSILENT`, no wizard). Restart is
; done explicitly by the [Run] "Check: WizardSilent" entry below, NOT by the
; Restart Manager — RestartApplications is unreliable in /VERYSILENT (it often
; doesn't relaunch), and leaving it on would risk a double launch.
CloseApplications=yes
RestartApplications=no
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

[InstallDelete]
; Run BEFORE the new files are copied. Clears the packaged runtime and the
; shipped built-in template sets so files removed/renamed between versions don't
; linger as orphans (e.g. a deleted template, a renamed _internal DLL).
; User data is PRESERVED: config.json is never shipped, and the per-function
; custom\ folders (user recaptures — load_template prefers them over built-in)
; are deliberately NOT listed here, so an upgrade refreshes built-in without
; destroying a user's recaptured templates.
Type: filesandordirs; Name: "{app}\_internal"
Type: filesandordirs; Name: "{app}\templates\cht\buy\built-in"
Type: filesandordirs; Name: "{app}\templates\cht\delete\built-in"
Type: filesandordirs; Name: "{app}\templates\cht\full_auto\built-in"
Type: filesandordirs; Name: "{app}\templates\cht\mastery_full\built-in"
Type: filesandordirs; Name: "{app}\templates\cht\race\built-in"
Type: filesandordirs; Name: "{app}\templates\cht\relaunch\built-in"
Type: filesandordirs; Name: "{app}\templates\cht\wheelspin\built-in"
Type: filesandordirs; Name: "{app}\templates\en\buy\built-in"
Type: filesandordirs; Name: "{app}\templates\en\delete\built-in"
Type: filesandordirs; Name: "{app}\templates\en\full_auto\built-in"
Type: filesandordirs; Name: "{app}\templates\en\mastery_full\built-in"
Type: filesandordirs; Name: "{app}\templates\en\race\built-in"
Type: filesandordirs; Name: "{app}\templates\en\relaunch\built-in"
Type: filesandordirs; Name: "{app}\templates\en\wheelspin\built-in"

[Files]
; The whole built app folder. recursesubdirs keeps _internal\ etc.
Source: "FAFE_dist\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"; Tasks: desktopicon

[Run]
; Interactive install: offer to launch after install (the "Launch FAFE" checkbox).
Filename: "{app}\{#MyAppExe}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent
; Silent auto-update: relaunch FAFE explicitly (the checkbox above is skipped when
; silent). Gated to silent installs so an interactive install doesn't double-launch.
Filename: "{app}\{#MyAppExe}"; Flags: nowait; Check: WizardSilent
