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

:: ----- Ensure pip is available in portable Python -----
set PYTHON_EXE=portable_python\python.exe
if not exist "%PYTHON_EXE%" (
    echo ❌ python.exe not found in portable_python folder.
    pause
    exit /b 1
)

:: Check if pip is present
%PYTHON_EXE% -m pip --version >nul 2>&1
if errorlevel 1 (
    echo 📦 Installing pip...
    curl -sS https://bootstrap.pypa.io/get-pip.py -o portable_python\get-pip.py
    if errorlevel 1 (
        echo ❌ Failed to download get-pip.py. Please check your internet connection.
        pause
        exit /b 1
    )
    %PYTHON_EXE% portable_python\get-pip.py --quiet
    del portable_python\get-pip.py
    echo ✅ pip installed.
)

:: ----- Install required Python packages from requirements.txt -----
echo 📦 Installing required packages from sources\requirements.txt...
if not exist "sources\requirements.txt" (
    echo ⚠️ sources\requirements.txt not found. Creating default.
    echo yt-dlp > sources\requirements.txt
    echo spotipy >> sources\requirements.txt
)
%PYTHON_EXE% -m pip install -r sources\requirements.txt --quiet --upgrade
if errorlevel 1 (
    echo ❌ Failed to install required packages. Please check your internet connection.
    pause
    exit /b 1
)
echo ✅ Packages ready.

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

%PYTHON_EXE% LinkCaty.py
set EXIT_CODE=%errorlevel%

if %EXIT_CODE% neq 0 (
    echo.
    echo ❌ Application exited with error code %EXIT_CODE%
    pause
)
exit /b %EXIT_CODE%