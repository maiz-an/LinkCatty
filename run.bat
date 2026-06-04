@echo off
chcp 65001 >nul
title LinkCaty Downloader
setlocal enabledelayedexpansion

echo ════════════════════════════════════════════════════════════════
echo                    LinkCaty Setup
echo ════════════════════════════════════════════════════════════════
echo.

:: ----- Extract Portable Python if not present -----
if not exist "portable_python\python.exe" (
    echo 📦 Extracting Portable Python...
    if not exist "sources\PortablePython.zip" (
        echo ❌ Error: sources\PortablePython.zip not found!
        pause
        exit /b 1
    )
    powershell -command "Expand-Archive -Force -Path 'sources\PortablePython.zip' -DestinationPath 'portable_python'" >nul 2>&1
    if errorlevel 1 (
        echo ❌ Failed to extract Portable Python.
        pause
        exit /b 1
    )
    echo ✅ Portable Python extracted.
)

:: ----- Set FFmpeg path (already provided) -----
set FFMPEG_DIR=%CD%\sources\FFmpeg\windows\ffmpeg\bin
if exist "%FFMPEG_DIR%\ffmpeg.exe" (
    echo ✅ FFmpeg found.
    set "PATH=%FFMPEG_DIR%;%PATH%"
) else (
    echo ⚠️ FFmpeg not found at %FFMPEG_DIR%
    echo    Video merging and MP3 conversion may fail.
)

:: ----- Run the application using portable Python -----
echo.
echo 🚀 Launching LinkCaty...
echo.

"portable_python\python.exe" LinkCaty.py
set EXIT_CODE=%errorlevel%

if %EXIT_CODE% neq 0 (
    echo.
    echo ❌ Application exited with error code %EXIT_CODE%
    pause
)
exit /b %EXIT_CODE%