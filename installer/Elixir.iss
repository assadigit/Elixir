; Elixir — Inno Setup script (V0.6.63 refresh)
; ============================================================================
; Compiled by build_installer.py, which passes the version:
;
;     ISCC.exe /DAppVersion="0.6.63" installer\Elixir.iss
;
; Output: dist_installer\Elixir-Setup-<version>.exe
; The app itself comes from the PyInstaller onedir build (dist_app\Elixir\*).
;
; V0.6.63 changes vs the V13.26.0 script:
;   - AppVersion arrives as a /D define (the VERSION file stays the single
;     source of truth — no more stale "0.4.25" hand-edits)
;   - stable AppId (upgrades now find the previous install)
;   - SetupIconFile = installer\elixir.ico (generated, guarded)
;   - user-data pre-creation moved to {localappdata}\Elixir (the frozen app's
;     user_data_dir; the old script pre-created {userappdata}\.elixir)
;   - per-user install (PrivilegesRequired=lowest, {autopf} -> the per-user
;     Programs dir) — double-click install, no UAC prompt
; ============================================================================

#ifndef AppVersion
#define AppVersion "0.0.0"
#endif

[Setup]
AppId={{8F4A2C31-9B7D-4E5A-A6C8-2E1F0D3B9A47}
AppName=Elixir
AppVersion={#AppVersion}
VersionInfoVersion={#AppVersion}
AppPublisher=Elixir
DefaultDirName={autopf}\Elixir
DefaultGroupName=Elixir
DisableProgramGroupPage=yes
OutputDir=..\dist_installer
OutputBaseFilename=Elixir-Setup-{#AppVersion}
Compression=lzma2/ultra
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\Elixir.exe
#if FileExists(SourcePath + "elixir.ico")
SetupIconFile={#SourcePath}elixir.ico
#endif

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
; Desktop icon defaults to CHECKED (V13.26.0 behaviour kept)
Name: "desktopicon"; Description: "Create a &desktop icon"; GroupDescription: "Additional icons:"

[Files]
Source: "..\dist_app\Elixir\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

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
  UserDir: String;
begin
  Result := True;

  // Check both HKLM (admin install) and HKCU (user-mode) for Ollama, plus
  // PATH (portable installs). Elixir needs Ollama for local LLM work (the
  // cloud providers work without it).
  OllamaFound := RegKeyExists(HKLM, 'SOFTWARE\Ollama') or
                 RegKeyExists(HKCU, 'SOFTWARE\Ollama');
  if not OllamaFound then
  begin
    try
      if Exec(ExpandConstant('{cmd}'), '/C ollama --version > nul 2>&1', '',
              SW_HIDE, ewWaitUntilTerminated, ResultCode) then
        OllamaFound := (ResultCode = 0);
    except
      // Ignore exec errors — fall through to the download prompt
    end;
  end;

  if not OllamaFound then
  begin
    if MsgBox('Ollama is not detected. Elixir uses Ollama for local LLM ' +
        'summarization.' + #13#10 + #13#10 +
        'Would you like to download it now?', mbConfirmation, MB_YESNO) = IDYES then
    begin
      ShellExec('open', 'https://ollama.com/download', '', '', SW_SHOW, ewNoWait, ResultCode);
    end;
  end;

  // Pre-create the frozen app's user-data dir (%LOCALAPPDATA%\Elixir) so the
  // first launch can write settings.json without a creation race.
  UserDir := ExpandConstant('{localappdata}') + '\Elixir';
  if not DirExists(UserDir) then
  begin
    CreateDir(UserDir);
    CreateDir(UserDir + '\prompts');
    CreateDir(UserDir + '\crash_reports');
  end;
end;
