@echo off
chcp 65001 >nul 2>&1
title LinkCatty
setlocal enabledelayedexpansion

:: Try to set console width (ignore errors)
mode con cols=62 lines=30 >nul 2>&1

:: -------------------------------------------------------------------
:: Update Check
:: -------------------------------------------------------------------
echo Checking for updates...
set "REMOTE_VERSION_FILE=https://raw.githubusercontent.com/maiz-an/LinkCatty/refs/heads/main/sources/version.txt"
set "LOCAL_VERSION_FILE=%~dp0sources\version.txt"

if exist "%LOCAL_VERSION_FILE%" (
    for /f "usebackq delims=" %%i in ("%LOCAL_VERSION_FILE%") do set "LOCAL_VER=%%i"
) else (
    set "LOCAL_VER=0.0.0"
)

set "TEMP_FILE=%TEMP%\remote_version.txt"
powershell -command "& {Invoke-WebRequest -Uri '%REMOTE_VERSION_FILE%' -OutFile '%TEMP_FILE%'}" >nul 2>&1

if exist "%TEMP_FILE%" (
    for /f "usebackq delims=" %%A in ("%TEMP_FILE%") do (
        for /f "delims=" %%B in ("%%A") do set "REMOTE_VER=%%B"
    )
    del "%TEMP_FILE%"
) else (
    echo Warning: Could not check for updates.
    set "REMOTE_VER=%LOCAL_VER%"
)

if not "%LOCAL_VER%"=="%REMOTE_VER%" (
    echo.
    echo ============================================================
    echo                     UPDATE AVAILABLE!
    echo ============================================================
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
echo ============================================================
echo                    LinkCatty Setup
echo ============================================================
echo.

:: -------------------------------------------------------------------
:: Extract Portable Python (if missing)
:: -------------------------------------------------------------------
set "PORTABLE_DIR=%~dp0sources\portable_python"
if not exist "%PORTABLE_DIR%\python.exe" (
    if not exist "%PORTABLE_DIR%\Scripts\python.exe" (
        echo Extracting Portable Python...
        if not exist "%~dp0sources\PortablePython.zip" (
            echo ERROR: sources\PortablePython.zip not found!
            pause
            exit /b 1
        )
        mkdir "%PORTABLE_DIR%" 2>nul
        powershell -command "& { Add-Type -AssemblyName System.IO.Compression.FileSystem; [System.IO.Compression.ZipFile]::ExtractToDirectory('%~dp0sources\PortablePython.zip', '%PORTABLE_DIR%') }" >nul 2>&1
        if errorlevel 1 (
            echo Extraction failed.
            pause
            exit /b 1
        )
        :: Move contents up if there is a single subfolder
        pushd "%PORTABLE_DIR%"
        for /d %%d in (*) do (
            if exist "%%d\python.exe" (
                move "%%d\*" . >nul 2>&1
                rmdir "%%d" 2>nul
            )
        )
        popd
        echo Portable Python ready.
    )
)

:: -------------------------------------------------------------------
:: Locate python.exe
:: -------------------------------------------------------------------
set "PYTHON_EXE="
if exist "%PORTABLE_DIR%\python.exe" (
    set "PYTHON_EXE=%PORTABLE_DIR%\python.exe"
) else if exist "%PORTABLE_DIR%\Scripts\python.exe" (
    set "PYTHON_EXE=%PORTABLE_DIR%\Scripts\python.exe"
) else (
    :: Fallback to system Python
    where python >nul 2>&1
    if not errorlevel 1 (
        set "PYTHON_EXE=python"
        echo Using system Python.
    ) else (
        echo ERROR: Python not found. Please install Python or ensure PortablePython.zip is present.
        pause
        exit /b 1
    )
)

:: -------------------------------------------------------------------
:: Add Scripts/bin to PATH
:: -------------------------------------------------------------------
set "SCRIPT_DIR=%PORTABLE_DIR%\Scripts"
if not exist "%SCRIPT_DIR%" set "SCRIPT_DIR=%PORTABLE_DIR%\bin"
if exist "%SCRIPT_DIR%" set "PATH=%SCRIPT_DIR%;%PATH%"

:: -------------------------------------------------------------------
:: FFmpeg for Windows (optional)
:: -------------------------------------------------------------------
set "FFMPEG_DIR=%~dp0sources\FFmpeg\windows\ffmpeg\bin"
if exist "%FFMPEG_DIR%\ffmpeg.exe" (
    set "PATH=%FFMPEG_DIR%;%PATH%"
) else (
    echo Warning: FFmpeg not found - video merging may fail.
)

:: -------------------------------------------------------------------
:: Install required packages (if pip exists)
:: -------------------------------------------------------------------
:: Check if pip is available in portable environment
"%PYTHON_EXE%" -m pip --version >nul 2>&1
if not errorlevel 1 (
    echo Installing/updating packages...
    "%PYTHON_EXE%" -m pip install --quiet --upgrade yt-dlp spotipy
) else (
    echo Warning: pip not available. Skipping package installation.
)

:: -------------------------------------------------------------------
:: Launch LinkCatty
:: -------------------------------------------------------------------
echo.
echo Launching LinkCatty...
echo.

"%PYTHON_EXE%" "%~dp0sources\LinkCatty.py"
set EXIT_CODE=%errorlevel%

if %EXIT_CODE% neq 0 (
    echo.
    echo Application exited with error code %EXIT_CODE%
)
pause
exit /b %EXIT_CODE%