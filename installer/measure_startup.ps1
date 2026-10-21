# V0.6.63: startup measurement for the installer build (Windows CI).
# Polls the launched process for a visible main-window handle and records
# the time from launch to window (or, in headless CI sessions where window
# handles never materialize, time-to-alive as an honest fallback).

param(
    [Parameter(Mandatory = $true)][string]$Exe,
    [string]$ExeArgs = "",
    [Parameter(Mandatory = $true)][string]$Label,
    [Parameter(Mandatory = $true)][string]$OutFile,
    [switch]$Append
)

$proc = Start-Process -FilePath $Exe -ArgumentList $ExeArgs -PassThru
$sw = [System.Diagnostics.Stopwatch]::StartNew()
$windowSecs = $null
$maxSecs = 90

while ($sw.Elapsed.TotalSeconds -lt $maxSecs) {
    Start-Sleep -Milliseconds 250
    if ($proc.HasExited) { break }
    $proc.Refresh()
    if ($proc.MainWindowHandle -ne 0) {
        $windowSecs = $sw.Elapsed.TotalSeconds
        break
    }
}

$aliveSecs = $sw.Elapsed.TotalSeconds
$line = if ($null -ne $windowSecs) {
    "{0}: {1:N2}s from launch to main window (pid {2})" -f $Label, $windowSecs, $proc.Id
}
elseif ($proc.HasExited) {
    "{0}: PROCESS EXITED after {1:N2}s (exit code {2}) — no window" -f $Label, $aliveSecs, $proc.ExitCode
}
else {
    "{0}: no visible window handle in {1:N1}s (headless session) — process stayed alive (pid {2})" -f $Label, $aliveSecs, $proc.Id
}

if (-not $proc.HasExited) {
    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
}

if ($Append) {
    Add-Content -Path $OutFile -Value $line
} else {
    Set-Content -Path $OutFile -Value $line
}
Write-Host $line
