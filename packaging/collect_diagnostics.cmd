@echo off
rem =====================================================================
rem  Elixir - Collect Diagnostics  (V0.6.66)
rem
rem  Installed into the Start menu alongside Elixir. When the app
rem  "doesn't open", double-click THIS instead: it gathers every piece
rem  of evidence support needs into ONE folder on your Desktop - no
rem  reading, no typing, nothing to configure. Every step is
rem  best-effort: a failing step is skipped, nothing is ever deleted
rem  or changed on your machine.
rem =====================================================================
setlocal EnableExtensions
set "OUT=%USERPROFILE%\Desktop\Elixir-diagnostics"
mkdir "%OUT%" 2>nul
if not exist "%OUT%" set "OUT=%LOCALAPPDATA%\Elixir\diagnostics"
mkdir "%OUT%" 2>nul

echo Collecting Elixir diagnostics into:
echo   %OUT%
echo.

rem ---- 1) the app's own startup logs (the first thing support reads) --
copy /y "%LOCALAPPDATA%\Elixir\*.log" "%OUT%\" >nul 2>&1
copy /y "%LOCALAPPDATA%\Elixir\*.txt" "%OUT%\" >nul 2>&1
set "APPPRG=%LOCALAPPDATA%\Programs\Elixir"
copy /y "%APPPRG%\Elixir-startup-crash.txt" "%OUT%\" >nul 2>&1

rem ---- 2) Windows version + build (reg query: fast, no admin needed) --
> "%OUT%\windows-version.txt" (
  reg query "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion" /v ProductName
  reg query "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion" /v DisplayVersion
  reg query "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion" /v CurrentBuildNumber
  reg query "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion" /v UBR
  ver
)

rem ---- 3) any Elixir process still running (zombie lock holder) -------
tasklist | findstr /I "Elixir" > "%OUT%\elixir-processes.txt" 2>&1
if errorlevel 1 echo no Elixir process was running > "%OUT%\elixir-processes.txt"

rem ---- 4) antivirus / Defender: the classic silent killer -------------
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { Get-MpThreatDetection | Select-Object InitialDetectionTime, ProcessName, @{n='Resources';e={$_.Resources -join '; '}} | Format-List | Out-File -FilePath '%OUT%\defender-detections.txt' -Width 300 } catch { $_ | Out-File -FilePath '%OUT%\defender-detections.txt' }" >nul 2>&1
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { Get-MpComputerStatus | Select-Object AMServiceEnabled, RealTimeProtectionEnabled, AntivirusSignatureLastUpdated | Format-List | Out-File -FilePath '%OUT%\defender-status.txt' } catch { $_ | Out-File -FilePath '%OUT%\defender-status.txt' }" >nul 2>&1

rem ---- 5) the install folder: exe + Qt plugin + runtime DLL presence --
> "%OUT%\install-folder.txt" (
  if exist "%APPPRG%\Elixir.exe" (echo Elixir.exe: PRESENT) else (echo Elixir.exe: MISSING)
  if exist "%APPPRG%\_internal" (echo _internal folder: PRESENT) else (echo _internal folder: MISSING)
  if exist "%APPPRG%\_internal\PySide6\plugins\platforms\qwindows.dll" (echo qwindows.dll: PRESENT) else (echo qwindows.dll: MISSING - an antivirus may have removed it)
  if exist "%APPPRG%\_internal\python312.dll" (echo python312.dll: PRESENT) else (echo python312.dll: MISSING)
  if exist "%APPPRG%\_internal\vcruntime140.dll" (echo vcruntime140.dll: PRESENT) else (echo vcruntime140.dll: not found in bundle)
  if exist "%APPPRG%\_internal\vcruntime140_1.dll" (echo vcruntime140_1.dll: PRESENT) else (echo vcruntime140_1.dll: not found in bundle)
)
dir /a "%APPPRG%" > "%OUT%\install-dir-listing.txt" 2>&1

rem ---- 6) disk free space + the list of everything collected ----------
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-PSDrive C | Select-Object Used,Free | Format-List | Out-File -FilePath '%OUT%\disk-space.txt'" >nul 2>&1
dir /b /a "%OUT%" > "%OUT%\_contents.txt" 2>&1

echo.
echo Done. Everything support needs is now in this folder:
echo   %OUT%
echo.
echo Please ZIP that folder (right-click it, then "Send to" and
echo "Compressed (zipped) folder") and attach the ZIP to your reply.
echo.
start "" "%OUT%"
pause
