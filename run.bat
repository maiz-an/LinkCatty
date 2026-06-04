@echo off
chcp 65001 >nul
title LinkCaty Downloader
setlocal enabledelayedexpansion

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

:: -------------------------------------------------------------------
:: Extract Portable Python (silent, no progress bars)
:: -------------------------------------------------------------------
set "PORTABLE_DIR=%~dp0sources\portable_python"
if not exist "%PORTABLE_DIR%\*" (
    echo 📦 Extracting Portable Python...
    if not exist "%~dp0sources\PortablePython.zip" (
        echo ❌ Error: sources\PortablePython.zip not found!
        pause
        exit /b 1
    )
    :: Create target directory
    mkdir "%PORTABLE_DIR%" 2>nul
    :: Use .NET ZipFile (silent) instead of Expand-Archive
    powershell -command "& { Add-Type -AssemblyName System.IO.Compression.FileSystem; [System.IO.Compression.ZipFile]::ExtractToDirectory('%~dp0sources\PortablePython.zip', '%PORTABLE_DIR%') }" >nul 2>&1
    if errorlevel 1 (
        echo ❌ Extraction failed. The zip may be corrupted.
        pause
        exit /b 1
    )
    :: If the zip contains a single root folder, move its contents up
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
:: Locate python.exe (recursive)
:: -------------------------------------------------------------------
set "PYTHON_EXE="
for /r "%PORTABLE_DIR%" %%f in (python.exe) do if exist "%%f" set "PYTHON_EXE=%%f" & goto :found_python
:found_python

if not defined PYTHON_EXE (
    echo ❌ Python not found in extracted folder.
    echo.
    echo Contents of %PORTABLE_DIR%:
    if exist "%PORTABLE_DIR%" (
        dir /s /b "%PORTABLE_DIR%"
    ) else (
        echo Directory does not exist.
    )
    pause
    exit /b 1
)

echo ✅ Found Python at: %PYTHON_EXE%

:: -------------------------------------------------------------------
:: Add Scripts/bin folder to PATH
:: -------------------------------------------------------------------
set "SCRIPT_DIR=%PORTABLE_DIR%\Scripts"
if not exist "%SCRIPT_DIR%" set "SCRIPT_DIR=%PORTABLE_DIR%\bin"
if exist "%SCRIPT_DIR%" (
    set "PATH=%SCRIPT_DIR%;%PATH%"
)

:: -------------------------------------------------------------------
:: FFmpeg (Windows)
:: -------------------------------------------------------------------
set "FFMPEG_DIR=%~dp0sources\FFmpeg\windows\ffmpeg\bin"
if exist "%FFMPEG_DIR%\ffmpeg.exe" (
    echo ✅ FFmpeg found.
    set "PATH=%FFMPEG_DIR%;%PATH%"
) else (
    echo ⚠️ FFmpeg not found - video merging may fail.
)

:: -------------------------------------------------------------------
:: Launch LinkCaty
:: -------------------------------------------------------------------
echo.
echo 🚀 Launching LinkCaty...
echo.

"%PYTHON_EXE%" "%~dp0LinkCaty.py"
set EXIT_CODE=%errorlevel%

if %EXIT_CODE% neq 0 (
    echo.
    echo ❌ Application exited with error code %EXIT_CODE%
)
pause
exit /b %EXIT_CODE%