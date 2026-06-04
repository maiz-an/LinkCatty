@echo off
chcp 65001 >nul
title LinkCatty Downloader
setlocal enabledelayedexpansion

:: -------------------------------------------------------------------
:: Update Check (reads version.txt from sources folder)
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
echo                    LinkCatty Setup
echo ════════════════════════════════════════════════════════════════
echo.

:: -------------------------------------------------------------------
:: Extract Portable Python into sources/portable_python
:: -------------------------------------------------------------------
set "PORTABLE_DIR=%~dp0sources\portable_python"
if not exist "%PORTABLE_DIR%\*" (
    echo 📦 Extracting Portable Python...
    if not exist "%~dp0sources\PortablePython.zip" (
        echo ❌ Error: sources\PortablePython.zip not found!
        pause
        exit /b 1
    )
    mkdir "%PORTABLE_DIR%" 2>nul
    :: Silent extraction using .NET
    powershell -command "& { Add-Type -AssemblyName System.IO.Compression.FileSystem; [System.IO.Compression.ZipFile]::ExtractToDirectory('%~dp0sources\PortablePython.zip', '%PORTABLE_DIR%') }" >nul 2>&1
    if errorlevel 1 (
        echo ❌ Extraction failed.
        pause
        exit /b 1
    )
    :: If zip contains a single subfolder, move contents up
    pushd "%PORTABLE_DIR%"
    for /d %%d in (*) do (
        if exist "%%d\python.exe" (
            move "%%d\*" . >nul 2>&1
            rmdir "%%d" 2>nul
        )
    )
    popd
    echo ✅ Portable Python ready.
)

:: -------------------------------------------------------------------
:: Locate python.exe recursively
:: -------------------------------------------------------------------
set "PYTHON_EXE="
for /r "%PORTABLE_DIR%" %%f in (python.exe) do if exist "%%f" set "PYTHON_EXE=%%f" & goto :found_python
:found_python

if not defined PYTHON_EXE (
    echo ❌ Python not found in extracted folder.
    pause
    exit /b 1
)

:: -------------------------------------------------------------------
:: Add Scripts/bin to PATH
:: -------------------------------------------------------------------
set "SCRIPT_DIR=%PORTABLE_DIR%\Scripts"
if not exist "%SCRIPT_DIR%" set "SCRIPT_DIR=%PORTABLE_DIR%\bin"
if exist "%SCRIPT_DIR%" set "PATH=%SCRIPT_DIR%;%PATH%"

:: -------------------------------------------------------------------
:: FFmpeg for Windows
:: -------------------------------------------------------------------
set "FFMPEG_DIR=%~dp0sources\FFmpeg\windows\ffmpeg\bin"
if exist "%FFMPEG_DIR%\ffmpeg.exe" (
    set "PATH=%FFMPEG_DIR%;%PATH%"
) else (
    echo ⚠️ FFmpeg not found - video merging may fail.
)

:: -------------------------------------------------------------------
:: Launch LinkCatty.py (inside sources folder)
:: -------------------------------------------------------------------
echo.
echo 🚀 Launching LinkCatty...
echo.

"%PYTHON_EXE%" "%~dp0sources\LinkCatty.py"
set EXIT_CODE=%errorlevel%

if %EXIT_CODE% neq 0 (
    echo.
    echo ❌ Application exited with error code %EXIT_CODE%
)
pause
exit /b %EXIT_CODE%