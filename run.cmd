@echo off
chcp 65001 >nul 2>&1
title LinkCatty
setlocal enabledelayedexpansion

:: -------------------------------------------------------------------
:: Check for uninstall flag
:: -------------------------------------------------------------------
echo %* | findstr /i "\-\-uninstall" >nul
if not errorlevel 1 (
    if exist "%~dp0uninstall_linkcatty.cmd" (
        start "" "%~dp0uninstall_linkcatty.cmd"
    ) else if exist "%LOCALAPPDATA%\LinkCatty\uninstall_linkcatty.cmd" (
        start "" "%LOCALAPPDATA%\LinkCatty\uninstall_linkcatty.cmd"
    ) else (
        echo Uninstaller not found. Downloading...
        set "UNINSTALL_URL=https://raw.githubusercontent.com/maiz-an/LinkCatty/main/uninstall_linkcatty.cmd"
        set "UNINSTALL_FILE=%TEMP%\uninstall_linkcatty.cmd"
        powershell -command "& {Invoke-WebRequest -Uri '!UNINSTALL_URL!' -OutFile '!UNINSTALL_FILE!'}" >nul 2>&1
        if exist "!UNINSTALL_FILE!" (
            start "" "!UNINSTALL_FILE!"
        ) else (
            echo Failed to download uninstaller.
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
:: [1/3] Check for updates
:: -------------------------------------------------------------------
echo [1/3] Checking for updates...
set "REMOTE_VERSION_URL=https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/version.txt"
set "LOCAL_VERSION_FILE=%~dp0sources\version.txt"

set "LOCAL_VER=0.0.0"
if exist "%LOCAL_VERSION_FILE%" (
    for /f "usebackq delims=" %%i in ("%LOCAL_VERSION_FILE%") do set "LOCAL_VER=%%i"
)

set "TEMP_FILE=%TEMP%\remote_version.txt"
powershell -command "& {Invoke-WebRequest -Uri '%REMOTE_VERSION_URL%' -OutFile '%TEMP_FILE%'}" >nul 2>&1
set "REMOTE_VER=%LOCAL_VER%"
if exist "%TEMP_FILE%" (
    for /f "usebackq delims=" %%A in ("%TEMP_FILE%") do set "REMOTE_VER=%%A"
    del "%TEMP_FILE%"
)

if not "%LOCAL_VER%"=="%REMOTE_VER%" (
    echo.
    echo ============================================================
    echo                      UPDATE AVAILABLE!
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

    if exist "%~dp0sources\settings.json" copy "%~dp0sources\settings.json" "%TEMP%\settings_backup.json" >nul
    if exist "%~dp0sources\download_history.json" copy "%~dp0sources\download_history.json" "%TEMP%\download_history_backup.json" >nul

    set "DOWNLOADED=0"
    for /l %%i in (0,1,11) do (
        set /a DOWNLOADED+=1
        set /a PERCENT=!DOWNLOADED! * 100 / !TOTAL_FILES!
        <nul set /p "=Progress: [!DOWNLOADED!/!TOTAL_FILES!] !PERCENT!%%  "
        call :DownloadFile %%i
        echo.
    )

    if exist "%TEMP%\settings_backup.json" copy "%TEMP%\settings_backup.json" "%~dp0sources\settings.json" >nul 2>&1
    if exist "%TEMP%\download_history_backup.json" copy "%TEMP%\download_history_backup.json" "%~dp0sources\download_history.json" >nul 2>&1
    del "%TEMP%\settings_backup.json" "%TEMP%\download_history_backup.json" 2>nul

    powershell -command "& { [System.IO.File]::WriteAllText('%~dp0sources\version.txt', '%REMOTE_VER%', [System.Text.UTF8Encoding]::new($false)) }" >nul 2>&1

    echo.
    echo [3/3] Update completed. Restarting...
    timeout /t 2 >nul
    start "" "%~f0"
    exit /b 0
)

:: -------------------------------------------------------------------
:: [2/3] Python setup - find or install Python ONCE
:: -------------------------------------------------------------------
echo [2/3] Setting up Python...

set "PORTABLE_DIR=%~dp0sources\portable_python"
set "PYTHON_EXE="
set "PYTHON_SCRIPTS="
set "DEPS_MARKER=%~dp0sources\.deps_installed"

:: ── Check if portable python already extracted and working
if exist "%PORTABLE_DIR%\python.exe" (
    set "PYTHON_EXE=%PORTABLE_DIR%\python.exe"
    set "PYTHON_SCRIPTS=%PORTABLE_DIR%\Scripts"
    echo Using portable Python.
    goto :SetupDeps
)
if exist "%PORTABLE_DIR%\Scripts\python.exe" (
    set "PYTHON_EXE=%PORTABLE_DIR%\Scripts\python.exe"
    set "PYTHON_SCRIPTS=%PORTABLE_DIR%\Scripts"
    echo Using portable Python.
    goto :SetupDeps
)

:: ── Try to extract portable python if zip present
if exist "%~dp0sources\PortablePython.zip" (
    echo Extracting portable Python...
    if not exist "%PORTABLE_DIR%" mkdir "%PORTABLE_DIR%"
    powershell -command "& { Add-Type -AssemblyName System.IO.Compression.FileSystem; [System.IO.Compression.ZipFile]::ExtractToDirectory('%~dp0sources\PortablePython.zip', '%PORTABLE_DIR%') }" >nul 2>&1
    :: Flatten subdirectory if needed
    pushd "%PORTABLE_DIR%"
    for /d %%d in (*) do (
        if exist "%%d\python.exe" (
            move "%%d\*" . >nul 2>&1
            rmdir "%%d" 2>nul
        ) else if exist "%%d\Scripts\python.exe" (
            move "%%d\*" . >nul 2>&1
            rmdir "%%d" 2>nul
        )
    )
    popd
    :: Re-check after extraction
    if exist "%PORTABLE_DIR%\python.exe" (
        set "PYTHON_EXE=%PORTABLE_DIR%\python.exe"
        set "PYTHON_SCRIPTS=%PORTABLE_DIR%\Scripts"
        echo Portable Python ready.
        :: Delete deps marker so deps get installed fresh with this python
        del "%DEPS_MARKER%" 2>nul
        goto :SetupDeps
    )
    if exist "%PORTABLE_DIR%\Scripts\python.exe" (
        set "PYTHON_EXE=%PORTABLE_DIR%\Scripts\python.exe"
        set "PYTHON_SCRIPTS=%PORTABLE_DIR%\Scripts"
        echo Portable Python ready.
        del "%DEPS_MARKER%" 2>nul
        goto :SetupDeps
    )
)

:: ── Fall back to system Python
:: Try python, python3, py launcher in order
for %%p in (python python3) do (
    if not defined PYTHON_EXE (
        %%p --version >nul 2>&1
        if not errorlevel 1 (
            set "PYTHON_EXE=%%p"
        )
    )
)
if not defined PYTHON_EXE (
    py --version >nul 2>&1
    if not errorlevel 1 set "PYTHON_EXE=py"
)

if not defined PYTHON_EXE (
    echo.
    echo ERROR: Python not found!
    echo.
    echo Please install Python from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)
echo Using system Python.

:: ── Get system Python's Scripts directory and add to PATH
for /f "usebackq delims=" %%s in (`%PYTHON_EXE% -c "import sysconfig; print(sysconfig.get_path('scripts'))" 2^>nul`) do (
    set "PYTHON_SCRIPTS=%%s"
)

:SetupDeps
:: Add Python scripts dir to PATH so installed tools are accessible
if defined PYTHON_SCRIPTS (
    if exist "!PYTHON_SCRIPTS!" (
        set "PATH=!PYTHON_SCRIPTS!;%PATH%"
    )
)

:: ── FFmpeg
set "FFMPEG_DIR=%~dp0sources\FFmpeg\windows\ffmpeg\bin"
if exist "%FFMPEG_DIR%\ffmpeg.exe" (
    set "PATH=%FFMPEG_DIR%;%PATH%"
) else (
    echo Warning: FFmpeg not found in sources. Some features may not work.
)

:: -------------------------------------------------------------------
:: [3/3] Install dependencies (only if not already done)
:: -------------------------------------------------------------------
echo [3/3] Checking dependencies...

if exist "%DEPS_MARKER%" (
    echo Dependencies already installed. Skipping.
) else (
    echo Installing packages ^(first run or update^)...
    "%PYTHON_EXE%" -m pip --version >nul 2>&1
    if errorlevel 1 (
        echo WARNING: pip not available. Trying to bootstrap...
        "%PYTHON_EXE%" -m ensurepip --upgrade >nul 2>&1
    )
    :: Upgrade pip silently, suppressing PATH warnings
    "%PYTHON_EXE%" -m pip install --quiet --upgrade pip --no-warn-script-location >nul 2>&1
    :: Install deps, suppress PATH/cache warnings
    "%PYTHON_EXE%" -m pip install --quiet --upgrade yt-dlp spotipy spotdl --no-warn-script-location --no-cache-dir
    if errorlevel 1 (
        echo ERROR: Failed to install some packages. Check your internet connection.
        pause
        exit /b 1
    )
    :: Write marker so we skip install next time
    echo %REMOTE_VER%> "%DEPS_MARKER%"
    echo Packages installed successfully.
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