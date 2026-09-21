; V13.26.0: One-click installer — Inno Setup script
; Bundles Python + app + config into a single .exe installer.
; User supplies Ollama/Tesseract/Poppler paths (or installer offers to install them).
;
; V13.26.0 changes:
;   - Version bumped from 10.35.0 → 13.26.0
;   - Added scripts/ to PyInstaller data list
;   - Fixed Ollama detection: now checks HKCU (user-mode) in addition to HKLM
;   - Desktop icon defaults to CHECKED (was unchecked)
;   - Creates ~/.elixir/ directory on install
;   - Updated build instructions with all required --add-data flags
;
; Build instructions:
;   1. pip install pyinstaller
;   2. pyinstaller --noconfirm --onedir --windowed --name "Elixir" ^
;        --add-data "core;core" --add-data "utils;utils" --add-data "ui_qt;ui_qt" ^
;        --add-data "config;config" --add-data "prompts;prompts" --add-data "assets;assets" ^
;        --add-data "scripts;scripts" ^
;        --hidden-import "PySide6.QtCore" --hidden-import "PySide6.QtWidgets" --hidden-import "PySide6.QtGui" ^
;        main.py
;   3. Compile this .iss file with Inno Setup Compiler (iscc.exe)
;   4. The output is dist/Elixir_Setup_V0.02.exe (V0.01+: tracks the VERSION file)

[Setup]
AppName=Elixir
AppVersion=0.4.6  ; V0.20.10: KEEP IN SYNC with the VERSION file (single source of truth)
AppPublisher=Elixir
DefaultDirName={autopf}\Elixir
DefaultGroupName=Elixir
DisableProgramGroupPage=yes
OutputDir=dist
OutputBaseFilename=Elixir_Setup_V0.06
Compression=lzma2/ultra
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\Elixir.exe

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
; V13.26.0: desktop icon defaults to CHECKED (was unchecked)
Name: "desktopicon"; Description: "Create a &desktop icon"; GroupDescription: "Additional icons:"

[Files]
Source: "dist\Elixir\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Elixir"; Filename: "{app}\Elixir.exe"
Name: "{group}\Uninstall Elixir"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Elixir"; Filename: "{app}\Elixir.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Elixir.exe"; Description: "Launch Elixir"; Flags: nowait postinstall skipifsilent

[Code]
function InitializeSetup(): Boolean;
var
  ResultCode: Integer;
  OllamaFound: Boolean;
  UserConfigDir: String;
begin
  Result := True;

  // V13.26.0: Check both HKLM (admin install) and HKCU (user-mode install)
  // for Ollama. Previously only checked HKLM, which missed user-mode installs
  // (the recommended way for non-admin users).
  OllamaFound := RegKeyExists(HKLM, 'SOFTWARE\Ollama') or
                 RegKeyExists(HKCU, 'SOFTWARE\Ollama');

  // Also check if ollama.exe is on PATH (covers portable installs)
  if not OllamaFound then
  begin
    try
      if Exec(ExpandConstant('{cmd}'), '/C ollama --version > nul 2>&1', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
        OllamaFound := (ResultCode = 0);
    except
      // Ignore exec errors — fall through to the download prompt
    end;
  end;

  if not OllamaFound then
  begin
    if MsgBox('Ollama is not detected. Elixir requires Ollama for local LLM summarization.' + #13#10 + #13#10 + 'Would you like to download it now?', mbConfirmation, MB_YESNO) = IDYES then
    begin
      ShellExec('open', 'https://ollama.com/download', '', '', SW_SHOW, ewNoWait, ResultCode);
    end;
  end;

  // V13.26.0: Pre-create the user config directory so the app can write
  // settings.json on first launch without directory-creation race conditions.
  UserConfigDir := ExpandConstant('{userappdata}\.elixir');
  if not DirExists(UserConfigDir) then
  begin
    CreateDir(UserConfigDir);
    // Also create subdirectories the app expects
    CreateDir(UserConfigDir + '\prompts');
    CreateDir(UserConfigDir + '\crash_reports');
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  UserConfigDir: String;
begin
  // V13.26.0: Ensure config dirs exist after installation too (in case
  // InitializeSetup's CreateDir didn't persist for some reason).
  if CurStep = ssPostInstall then
  begin
    UserConfigDir := ExpandConstant('{userappdata}\.elixir');
    if not DirExists(UserConfigDir) then
    begin
      CreateDir(UserConfigDir);
      CreateDir(UserConfigDir + '\prompts');
      CreateDir(UserConfigDir + '\crash_reports');
    end;
  end;
end;
