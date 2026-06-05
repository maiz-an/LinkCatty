@echo off
chcp 65001 >nul 2>&1
title LinkCatty
setlocal enabledelayedexpansion

:: Try to set console width (ignore errors)
mode con cols=62 lines=30 >nul 2>&1

:: -------------------------------------------------------------------
:: Check for updates
:: -------------------------------------------------------------------
echo Checking for updates...
set "REMOTE_VERSION_URL=https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/version.txt"
set "LOCAL_VERSION_FILE=%~dp0sources\version.txt"

if exist "%LOCAL_VERSION_FILE%" (
    for /f "usebackq delims=" %%i in ("%LOCAL_VERSION_FILE%") do set "LOCAL_VER=%%i"
) else (
    set "LOCAL_VER=0.0.0"
)

set "TEMP_FILE=%TEMP%\remote_version.txt"
powershell -command "& {Invoke-WebRequest -Uri '%REMOTE_VERSION_URL%' -OutFile '%TEMP_FILE%'}" >nul 2>&1

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
    echo Downloading updated files...

    :: Define all files to update
    set "FILE_LIST[0]=sources\downloaders\spotify_downloader.py|https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/downloaders/spotify_downloader.py"
    set "FILE_LIST[1]=sources\downloaders\youtube_downloader.py|https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/downloaders/youtube_downloader.py"
    set "FILE_LIST[2]=sources\utils\config.py|https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/utils/config.py"
    set "FILE_LIST[3]=sources\utils\ffmpeg.py|https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/utils/ffmpeg.py"
    set "FILE_LIST[4]=sources\utils\logger.py|https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/utils/logger.py"
    set "FILE_LIST[5]=sources\utils\ui.py|https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/utils/ui.py"
    set "FILE_LIST[6]=sources\requirements.txt|https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/requirements.txt"
    set "FILE_LIST[7]=sources\version.txt|https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/version.txt"

    :: Also update the launchers themselves
    set "FILE_LIST[8]=run.bat|https://raw.githubusercontent.com/maiz-an/LinkCatty/main/run.bat"
    set "FILE_LIST[9]=run.sh|https://raw.githubusercontent.com/maiz-an/LinkCatty/main/run.sh"

    :: Create backup of protected files
    if exist "%~dp0sources\settings.json" copy "%~dp0sources\settings.json" "%TEMP%\settings_backup.json" >nul
    if exist "%~dp0sources\download_history.json" copy "%~dp0sources\download_history.json" "%TEMP%\download_history_backup.json" >nul
    if exist "%~dp0sources\PortablePython.zip" copy "%~dp0sources\PortablePython.zip" "%TEMP%\PortablePython_backup.zip" >nul

    :: Download and update each file
    for /l %%i in (0,1,9) do (
        call :DownloadFile %%i
    )

    :: Restore protected files
    if exist "%TEMP%\settings_backup.json" copy "%TEMP%\settings_backup.json" "%~dp0sources\settings.json" >nul 2>&1
    if exist "%TEMP%\download_history_backup.json" copy "%TEMP%\download_history_backup.json" "%~dp0sources\download_history.json" >nul 2>&1
    if exist "%TEMP%\PortablePython_backup.zip" copy "%TEMP%\PortablePython_backup.zip" "%~dp0sources\PortablePython.zip" >nul 2>&1

    :: Cleanup backup
    del "%TEMP%\settings_backup.json" 2>nul
    del "%TEMP%\download_history_backup.json" 2>nul
    del "%TEMP%\PortablePython_backup.zip" 2>nul

    echo Update completed. Restarting...
    timeout /t 2 >nul
    start "" "%~f0"
    exit /b 0
)

:: -------------------------------------------------------------------
:: Continue with normal launch
:: -------------------------------------------------------------------
echo.
echo ============================================================
echo                    LinkCatty Setup
echo ============================================================
echo.

:: Extract Portable Python (if missing)
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

:: Locate python.exe
set "PYTHON_EXE="
if exist "%PORTABLE_DIR%\python.exe" (
    set "PYTHON_EXE=%PORTABLE_DIR%\python.exe"
) else if exist "%PORTABLE_DIR%\Scripts\python.exe" (
    set "PYTHON_EXE=%PORTABLE_DIR%\Scripts\python.exe"
) else (
    where python >nul 2>&1
    if not errorlevel 1 (
        set "PYTHON_EXE=python"
        echo Using system Python.
    ) else (
        echo ERROR: Python not found.
        pause
        exit /b 1
    )
)

:: Add Scripts/bin to PATH
set "SCRIPT_DIR=%PORTABLE_DIR%\Scripts"
if not exist "%SCRIPT_DIR%" set "SCRIPT_DIR=%PORTABLE_DIR%\bin"
if exist "%SCRIPT_DIR%" set "PATH=%SCRIPT_DIR%;%PATH%"

:: FFmpeg for Windows
set "FFMPEG_DIR=%~dp0sources\FFmpeg\windows\ffmpeg\bin"
if exist "%FFMPEG_DIR%\ffmpeg.exe" (
    set "PATH=%FFMPEG_DIR%;%PATH%"
) else (
    echo Warning: FFmpeg not found - video merging may fail.
)

:: Install packages if pip is available
"%PYTHON_EXE%" -m pip --version >nul 2>&1
if not errorlevel 1 (
    echo Installing/updating packages...
    "%PYTHON_EXE%" -m pip install --quiet --upgrade yt-dlp spotipy
) else (
    echo Warning: pip not available. Skipping package installation.
)

:: Launch
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

:: -------------------------------------------------------------------
:: Function to download a single file
:: -------------------------------------------------------------------
:DownloadFile
set "idx=%1"
set "entry=!FILE_LIST[%idx%]!"
for /f "tokens=1,2 delims=|" %%a in ("!entry!") do (
    set "FILE_PATH=%%a"
    set "FILE_URL=%%b"
)
:: Create directory if needed
for %%f in ("%FILE_PATH%") do set "FILE_DIR=%%~dpf"
if not exist "%~dp0!FILE_DIR!" mkdir "%~dp0!FILE_DIR!" 2>nul

:: Download file
powershell -command "& { $ProgressPreference = 'SilentlyContinue'; Invoke-WebRequest -Uri '!FILE_URL!' -OutFile '%~dp0!FILE_PATH!' }" >nul 2>&1
exit /b