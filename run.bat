@echo off
chcp 65001 >nul
title LinkCaty Downloader
setlocal

:: Check for update (optional)
echo Checking for updates...
set "REMOTE_VERSION=https://raw.githubusercontent.com/maiz-an/LinkCatty/refs/heads/main/sources/version.txt"
set "LOCAL_VERSION=%~dp0sources\version.txt"
set "UPDATE_AVAILABLE=0"

if exist "%LOCAL_VERSION%" (
    for /f "usebackq delims=" %%v in ("%LOCAL_VERSION%") do set "LOCAL_VER=%%v"
    >nul 2>&1 powershell -command "& {Invoke-WebRequest -Uri '%REMOTE_VERSION%' -OutFile '%TEMP%\remote_ver.txt'}"
    if exist "%TEMP%\remote_ver.txt" (
        set /p REMOTE_VER=<"%TEMP%\remote_ver.txt"
        del "%TEMP%\remote_ver.txt"
        if not "!LOCAL_VER!"=="!REMOTE_VER!" set "UPDATE_AVAILABLE=1"
    )
)

if "%UPDATE_AVAILABLE%"=="1" (
    echo.
    echo ════════════════════════════════════════════════════════════════
    echo                     UPDATE AVAILABLE!
    echo ════════════════════════════════════════════════════════════════
    echo Current version: %LOCAL_VER%
    echo Latest version:  %REMOTE_VER%
    echo Please download from: https://github.com/maiz-an/LinkCatty
    echo.
    pause
    exit /b 0
)

echo.
echo ════════════════════════════════════════════════════════════════
echo                    LinkCaty Setup
echo ════════════════════════════════════════════════════════════════
echo.

:: Extract portable Python
set "PORTABLE_DIR=%~dp0sources\portable_python"
if not exist "%PORTABLE_DIR%\python.exe" (
    echo 📦 Extracting Portable Python...
    if not exist "%~dp0sources\PortablePython.zip" (
        echo ❌ Error: sources\PortablePython.zip not found!
        pause
        exit /b 1
    )
    powershell -command "Expand-Archive -Force -Path '%~dp0sources\PortablePython.zip' -DestinationPath '%~dp0sources'" >nul 2>&1
    if errorlevel 1 (
        echo ❌ Extraction failed.
        pause
        exit /b 1
    )
    echo ✅ Portable Python ready.
)

:: Find python executable
set "PYTHON_EXE=%PORTABLE_DIR%\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=%PORTABLE_DIR%\Scripts\python.exe"
if not exist "%PYTHON_EXE%" (
    echo ❌ Python not found in extracted folder.
    pause
    exit /b 1
)

:: Add Scripts to PATH (for any executables)
set "PATH=%PORTABLE_DIR%\Scripts;%PORTABLE_DIR%\bin;%PATH%"

:: Setup FFmpeg (Windows)
set "FFMPEG_DIR=%~dp0sources\FFmpeg\windows\ffmpeg\bin"
if exist "%FFMPEG_DIR%\ffmpeg.exe" (
    set "PATH=%FFMPEG_DIR%;%PATH%"
) else (
    echo ⚠️ FFmpeg not found - video merging may fail.
)

:: Launch
echo.
echo 🚀 Launching LinkCaty...
echo.
"%PYTHON_EXE%" "%~dp0LinkCaty.py"
set EXIT_CODE=%errorlevel%
if %EXIT_CODE% neq 0 echo ❌ Exit code: %EXIT_CODE%
pause
exit /b %EXIT_CODE%