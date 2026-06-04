@echo off
chcp 65001 >nul
title LinkCaty Downloader
setlocal enabledelayedexpansion

:: Check for Update
echo Checking for updates...
set "REMOTE_VERSION_FILE=https://raw.githubusercontent.com/maiz-an/LinkCatty/refs/heads/main/sources/version.txt"
set "LOCAL_VERSION_FILE=%~dp0sources\version.txt"

if exist "%LOCAL_VERSION_FILE%" (
    for /f "usebackq delims=" %%i in ("%LOCAL_VERSION_FILE%") do set "LOCAL_VER=%%i"
) else (
    set "LOCAL_VER=0.0.0"
)

:: Download remote version file
set "TEMP_FILE=%TEMP%\remote_version.txt"
powershell -command "& {Invoke-WebRequest -Uri '%REMOTE_VERSION_FILE%' -OutFile '%TEMP_FILE%'}" >nul 2>&1

if exist "%TEMP_FILE%" (
    set /p REMOTE_VER=<"%TEMP_FILE%"
    del "%TEMP_FILE%"
) else (
    echo Warning: Could not check for updates.
    set "REMOTE_VER=%LOCAL_VER%"
)

if not "%LOCAL_VER%"=="%REMOTE_VER%" (
    echo.
    echo ════════════════════════════════════════════════════════════════
    echo                     UPDATE AVAILABLE!
    echo ════════════════════════════════════════════════════════════════
    echo Current Version: %LOCAL_VER%
    echo Latest Version:  %REMOTE_VER%
    echo.
    echo Please download the latest version from:
    echo https://github.com/maiz-an/LinkCatty
    echo.
    pause
    exit /b 0
)

echo.
echo ════════════════════════════════════════════════════════════════
echo                    LinkCaty Setup
echo ════════════════════════════════════════════════════════════════
echo.

:: ----- Extract Portable Python into sources\portable_python -----
set "PORTABLE_PYTHON_DIR=%~dp0sources\portable_python"
if not exist "%PORTABLE_PYTHON_DIR%\python.exe" (
    echo 📦 Extracting Portable Python into sources\portable_python...
    if not exist "%~dp0sources\PortablePython.zip" (
        echo ❌ Error: sources\PortablePython.zip not found!
        pause
        exit /b 1
    )
    powershell -command "Expand-Archive -Force -Path '%~dp0sources\PortablePython.zip' -DestinationPath '%PORTABLE_PYTHON_DIR%'" >nul 2>&1
    if errorlevel 1 (
        echo ❌ Failed to extract Portable Python.
        pause
        exit /b 1
    )
    echo ✅ Portable Python extracted.
)

set PYTHON_EXE=%PORTABLE_PYTHON_DIR%\python.exe
if not exist "%PYTHON_EXE%" (
    echo ❌ python.exe not found in %PORTABLE_PYTHON_DIR%
    pause
    exit /b 1
)

:: ---- Fix Embeddable Python Configuration ----
set "PTH_FILE=%PORTABLE_PYTHON_DIR%\python._pth"
if exist "%PTH_FILE%" (
    :: Check if line is commented
    findstr /C:"#import site" "%PTH_FILE%" >nul
    if not errorlevel 1 (
        powershell -command "(Get-Content '%PTH_FILE%') -replace '#import site', 'import site' | Set-Content '%PTH_FILE%'" >nul
        echo ✅ Python configuration fixed (uncommented import site).
    ) else (
        findstr /C:"import site" "%PTH_FILE%" >nul
        if errorlevel 1 (
            echo import site>>"%PTH_FILE%"
            echo ✅ Added import site to python._pth.
        )
    )
)

:: Create site-packages directory if missing
if not exist "%PORTABLE_PYTHON_DIR%\Lib\site-packages" (
    mkdir "%PORTABLE_PYTHON_DIR%\Lib\site-packages" >nul 2>&1
    echo ✅ Created site-packages directory.
)

:: Add Scripts folder to PATH temporarily
set "PATH=%PORTABLE_PYTHON_DIR%\Scripts;%PATH%"

:: ---- Install pip using ensurepip ----
%PYTHON_EXE% -c "import pip" >nul 2>&1
if errorlevel 1 (
    echo 📦 Installing pip...
    %PYTHON_EXE% -m ensurepip --upgrade >nul 2>&1
    if errorlevel 1 (
        curl -sS https://bootstrap.pypa.io/get-pip.py -o "%PORTABLE_PYTHON_DIR%\get-pip.py"
        if errorlevel 1 (
            echo ❌ Failed to download get-pip.py. Please check your internet connection.
            pause
            exit /b 1
        )
        %PYTHON_EXE% "%PORTABLE_PYTHON_DIR%\get-pip.py" --quiet --no-warn-script-location
        del "%PORTABLE_PYTHON_DIR%\get-pip.py"
    )
    echo ✅ pip installed.
)

:: Verify pip is functional
%PYTHON_EXE% -m pip --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Pip installation failed. Trying alternative method...
    %PYTHON_EXE% -m ensurepip --upgrade --default-pip >nul 2>&1
    if errorlevel 1 (
        echo ❌ Could not install pip. Please check your internet connection and try again.
        pause
        exit /b 1
    )
)

:: ---- Install required packages ----
echo 📦 Installing required packages from sources\requirements.txt...
if not exist "%~dp0sources\requirements.txt" (
    echo yt-dlp > "%~dp0sources\requirements.txt"
    echo spotipy >> "%~dp0sources\requirements.txt"
)
%PYTHON_EXE% -m pip install -r "%~dp0sources\requirements.txt" --quiet --upgrade --no-warn-script-location
if errorlevel 1 (
    echo ❌ Failed to install required packages. Please check your internet connection.
    pause
    exit /b 1
)
echo ✅ Packages ready.

:: ---- Setup FFmpeg (Windows) ----
set FFMPEG_DIR=%~dp0sources\FFmpeg\windows\ffmpeg\bin
if exist "%FFMPEG_DIR%\ffmpeg.exe" (
    echo ✅ FFmpeg found.
    set "PATH=%FFMPEG_DIR%;%PATH%"
) else (
    echo ⚠️ FFmpeg not found at %FFMPEG_DIR%
    echo    Video merging and MP3 conversion may fail.
)

:: ---- Launch the application ----
echo.
echo 🚀 Launching LinkCaty...
echo.

cd /d "%~dp0"
%PYTHON_EXE% LinkCaty.py
set EXIT_CODE=%errorlevel%

if %EXIT_CODE% neq 0 (
    echo.
    echo ❌ Application exited with error code %EXIT_CODE%
    pause
)
exit /b %EXIT_CODE%