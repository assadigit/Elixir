@echo off
setlocal EnableExtensions
chcp 65001 >nul
title Transcribe a video or audio file

REM ================= CONFIGURATION =================
REM Edit only these 3 lines.
set "CLI=C:\transcribe.cpp\build\bin\Release\transcribe-cli.exe"
set "MODEL=C:\transcribe.cpp\models\whisper-large-v3-Q8_0.gguf"
set "FFMPEG=ffmpeg"
REM =================================================

if "%~1"=="" goto nofile
if not exist "%CLI%" goto badpaths
if not exist "%MODEL%" goto badpaths

set "WAV=%~dpn1_16k.wav"
set "OUT=%~dpn1_transcript.txt"

echo Converting audio...
"%FFMPEG%" -y -loglevel error -i "%~1" -vn -ar 16000 -ac 1 "%WAV%"
if errorlevel 1 goto failed

echo Transcribing. Long videos take a while, please wait...
"%CLI%" -m "%MODEL%" "%WAV%" > "%OUT%"
if errorlevel 1 goto failed

del "%WAV%"
echo.
echo Done. Transcript saved to:
echo %OUT%
goto end

:nofile
echo Drag a video or audio file onto this file.
goto end

:badpaths
echo I cannot find the program or the model file.
echo Right-click this file, choose Edit, and fix the paths at the top.
goto end

:failed
echo Something went wrong. Check the three paths at the top of this file.

:end
echo.
pause
endlocal
