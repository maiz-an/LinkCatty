@echo off
chcp 65001 >nul 2>&1
title LinkCatty
setlocal enabledelayedexpansion

:: -------------------------------------------------------------------
:: Check for uninstall flag (unchanged)
:: -------------------------------------------------------------------
echo %* | findstr /i "\-\-uninstall" >nul
if not errorlevel 1 (
    if exist "%~dp0uninstall_linkcatty.cmd" (
        start "" "%~dp0uninstall_linkcatty.cmd"
    ) else if exist "%LOCALAPPDATA%\LinkCatty\uninstall_linkcatty.cmd" (
        start "" "%LOCALAPPDATA%\LinkCatty\uninstall_linkcatty.cmd"
    ) else (
        echo Uninstaller not found. Downloading now...
        set "UNINSTALL_URL=https://raw.githubusercontent.com/maiz-an/LinkCatty/main/uninstall_linkcatty.cmd"
        set "UNINSTALL_FILE=%TEMP%\uninstall_linkcatty.cmd"
        powershell -command "& {Invoke-WebRequest -Uri '!UNINSTALL_URL!' -OutFile '!UNINSTALL_FILE!'}" >nul 2>&1
        if exist "!UNINSTALL_FILE!" (
            start "" "!UNINSTALL_FILE!"
        ) else (
            echo Failed to download uninstaller. Please download manually from GitHub.
            pause
        )
    )
    exit /b 0
)

mode con cols=62 lines=30 >nul 2>&1

echo.
echo ============================================================
echo                    LinkCatty Launcher
echo ============================================================
echo.

:: -------------------------------------------------------------------
:: Check for updates (corrected)
:: -------------------------------------------------------------------
echo [1/3] Checking for updates...
set "REMOTE_VERSION_URL=https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/version.txt"
set "LOCAL_VERSION_FILE=%~dp0sources\version.txt"

:: Read local version, trim CR/LF and spaces
set "LOCAL_VER=0.0.0"
if exist "%LOCAL_VERSION_FILE%" (
    for /f "usebackq delims=" %%i in ("%LOCAL_VERSION_FILE%") do set "LOCAL_VER=%%i"
    for /f "delims=" %%a in ("!LOCAL_VER!") do set "LOCAL_VER=%%a"
)

:: Download remote version
set "TEMP_FILE=%TEMP%\remote_version.txt"
powershell -command "& {Invoke-WebRequest -Uri '%REMOTE_VERSION_URL%' -OutFile '%TEMP_FILE%'}" >nul 2>&1
set "REMOTE_VER=%LOCAL_VER%"
if exist "%TEMP_FILE%" (
    for /f "usebackq delims=" %%A in ("%TEMP_FILE%") do (
        for /f "delims=" %%B in ("%%A") do set "REMOTE_VER=%%B"
    )
    del "%TEMP_FILE%"
)

:: Compare versions (case‑insensitive, trimmed)
if /i not "%LOCAL_VER%"=="%REMOTE_VER%" (
    echo.
    echo ============================================================
    echo                     UPDATE AVAILABLE!
    echo ============================================================
    echo   Current version : %LOCAL_VER%
    echo   Latest version  : %REMOTE_VER%
    echo.
    echo [2/3] Downloading update...

    set "FILE_LIST[0]=sources\downloaders\spotify_downloader.py|https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/downloaders/spotify_downloader.py"
    set "FILE_LIST[1]=sources\downloaders\youtube_downloader.py|https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/downloaders/youtube_downloader.py"
    set "FILE_LIST[2]=sources\utils\config.py|https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/utils/config.py"
    set "FILE_LIST[3]=sources\utils\ffmpeg.py|https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/utils/ffmpeg.py"
    set "FILE_LIST[4]=sources\utils\logger.py|https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/utils/logger.py"
    set "FILE_LIST[5]=sources\utils\ui.py|https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/utils/ui.py"
    set "FILE_LIST[6]=sources\requirements.txt|https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/requirements.txt"
    set "FILE_LIST[7]=sources\version.txt|https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/version.txt"
    set "FILE_LIST[8]=run.cmd|https://raw.githubusercontent.com/maiz-an/LinkCatty/main/run.cmd"
    set "FILE_LIST[9]=run.sh|https://raw.githubusercontent.com/maiz-an/LinkCatty/main/run.sh"
    set "FILE_LIST[10]=uninstall_linkcatty.cmd|https://raw.githubusercontent.com/maiz-an/LinkCatty/main/uninstall_linkcatty.cmd"
    set "FILE_LIST[11]=uninstall_linkcatty.sh|https://raw.githubusercontent.com/maiz-an/LinkCatty/main/uninstall_linkcatty.sh"
    set "TOTAL_FILES=12"

    :: Backup user data
    if exist "%~dp0sources\settings.json" copy "%~dp0sources\settings.json" "%TEMP%\settings_backup.json" >nul
    if exist "%~dp0sources\download_history.json" copy "%~dp0sources\download_history.json" "%TEMP%\download_history_backup.json" >nul
    if exist "%~dp0sources\PortablePython.zip" copy "%~dp0sources\PortablePython.zip" "%TEMP%\PortablePython_backup.zip" >nul

    :: Download all files
    set "DOWNLOADED=0"
    for /l %%i in (0,1,11) do (
        set /a DOWNLOADED+=1
        set /a PERCENT=!DOWNLOADED! * 100 / !TOTAL_FILES!
        <nul set /p "=Progress: [!DOWNLOADED!/!TOTAL_FILES!] !PERCENT!%%  "
        call :DownloadFile %%i
        echo.
    )

    :: Restore user data
    if exist "%TEMP%\settings_backup.json" copy "%TEMP%\settings_backup.json" "%~dp0sources\settings.json" >nul 2>&1
    if exist "%TEMP%\download_history_backup.json" copy "%TEMP%\download_history_backup.json" "%~dp0sources\download_history.json" >nul 2>&1
    if exist "%TEMP%\PortablePython_backup.zip" copy "%TEMP%\PortablePython_backup.zip" "%~dp0sources\PortablePython.zip" >nul 2>&1
    del "%TEMP%\settings_backup.json" "%TEMP%\download_history_backup.json" "%TEMP%\PortablePython_backup.zip" 2>nul

    :: ----- Write the new version file correctly -----
    :: Use PowerShell to write UTF‑8 without BOM and without extra spaces/newlines
    powershell -command "& { [System.IO.File]::WriteAllText('%~dp0sources\version.txt', '%REMOTE_VER%', [System.Text.UTF8Encoding]::new($false)) }" >nul 2>&1

    :: Verify it was written correctly
    set "VERIFY_VER=0.0.0"
    if exist "%~dp0sources\version.txt" (
        for /f "usebackq delims=" %%v in ("%~dp0sources\version.txt") do set "VERIFY_VER=%%v"
        for /f "delims=" %%a in ("!VERIFY_VER!") do set "VERIFY_VER=%%a"
    )
    if not "!VERIFY_VER!"=="%REMOTE_VER%" (
        :: If still wrong, force delete and try simple echo
        del "%~dp0sources\version.txt" 2>nul
        (echo %REMOTE_VER%) > "%~dp0sources\version.txt"
    )

    echo.
    echo [3/3] Update completed. Restarting...
    timeout /t 2 >nul
    start "" "%~f0"
    exit /b 0
)

:: -------------------------------------------------------------------
:: Normal launch (unchanged)
:: -------------------------------------------------------------------
echo [2/3] Extracting Portable Python...
set "PORTABLE_DIR=%~dp0sources\portable_python"
if not exist "%PORTABLE_DIR%\python.exe" (
    if not exist "%PORTABLE_DIR%\Scripts\python.exe" (
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
    )
)
echo Portable Python ready.

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

set "SCRIPT_DIR=%PORTABLE_DIR%\Scripts"
if not exist "%SCRIPT_DIR%" set "SCRIPT_DIR=%PORTABLE_DIR%\bin"
if exist "%SCRIPT_DIR%" set "PATH=%SCRIPT_DIR%;%PATH%"

set "FFMPEG_DIR=%~dp0sources\FFmpeg\windows\ffmpeg\bin"
if exist "%FFMPEG_DIR%\ffmpeg.exe" (
    set "PATH=%FFMPEG_DIR%;%PATH%"
) else (
    echo Warning: FFmpeg not found.
)

echo [3/3] Installing packages...
"%PYTHON_EXE%" -m pip --version >nul 2>&1
if not errorlevel 1 (
    "%PYTHON_EXE%" -m pip install --quiet --upgrade pip
    "%PYTHON_EXE%" -m pip install --quiet --upgrade yt-dlp spotipy
)

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

:DownloadFile
set "idx=%1"
set "entry=!FILE_LIST[%idx%]!"
for /f "tokens=1,2 delims=|" %%a in ("!entry!") do (
    set "FILE_PATH=%%a"
    set "FILE_URL=%%b"
)
for %%f in ("%FILE_PATH%") do set "FILE_DIR=%%~dpf"
if not exist "%~dp0!FILE_DIR!" mkdir "%~dp0!FILE_DIR!" 2>nul
powershell -command "& { $ProgressPreference = 'SilentlyContinue'; Invoke-WebRequest -Uri '!FILE_URL!' -OutFile '%~dp0!FILE_PATH!' }" >nul 2>&1
exit /b