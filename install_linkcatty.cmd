@echo off
chcp 65001 >nul 2>&1
title LinkCatty Installer
setlocal enabledelayedexpansion

cls
set "INSTALL_DIR=%LOCALAPPDATA%\LinkCatty"
set "TEMP_DIR=%TEMP%\LinkCatty_temp"
echo.
echo ============================================================
echo                    LinkCatty Installer
echo ============================================================
echo.

:: Check if already installed
if exist "%INSTALL_DIR%\linkcatty.bat" (
    echo [WARNING] LinkCatty is already installed.
    set /p "OVERWRITE=Reinstall/update? (y/n): "
    if /i not "!OVERWRITE!"=="y" exit /b 0
    echo.
)

:: Clean old temp
if exist "%TEMP_DIR%" rmdir /s /q "%TEMP_DIR%" 2>nul
mkdir "%TEMP_DIR%" 2>nul

echo Downloading files from GitHub...
echo.

:: Helper function to download a file and check success
set "FAILED=0"

:: Download run.cmd
echo [1/16] Downloading run.cmd...
powershell -command "& {Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/maiz-an/LinkCatty/main/run.cmd' -OutFile '%TEMP_DIR%\run.cmd'}" >nul 2>&1
if not exist "%TEMP_DIR%\run.cmd" set "FAILED=1" & echo   FAILED
if exist "%TEMP_DIR%\run.cmd" echo   OK

:: Create sources structure
mkdir "%TEMP_DIR%\sources" 2>nul
mkdir "%TEMP_DIR%\sources\downloaders" 2>nul
mkdir "%TEMP_DIR%\sources\utils" 2>nul

:: Download main LinkCatty.py
echo [2/16] Downloading sources\LinkCatty.py...
powershell -command "& {Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/LinkCatty.py' -OutFile '%TEMP_DIR%\sources\LinkCatty.py'}" >nul 2>&1
if not exist "%TEMP_DIR%\sources\LinkCatty.py" set "FAILED=1" & echo   FAILED
if exist "%TEMP_DIR%\sources\LinkCatty.py" echo   OK

:: Download spotify_downloader.py
echo [3/16] Downloading sources\downloaders\spotify_downloader.py...
powershell -command "& {Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/downloaders/spotify_downloader.py' -OutFile '%TEMP_DIR%\sources\downloaders\spotify_downloader.py'}" >nul 2>&1
if not exist "%TEMP_DIR%\sources\downloaders\spotify_downloader.py" set "FAILED=1" & echo   FAILED
if exist "%TEMP_DIR%\sources\downloaders\spotify_downloader.py" echo   OK

:: Download youtube_downloader.py
echo [4/16] Downloading sources\downloaders\youtube_downloader.py...
powershell -command "& {Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/downloaders/youtube_downloader.py' -OutFile '%TEMP_DIR%\sources\downloaders\youtube_downloader.py'}" >nul 2>&1
if not exist "%TEMP_DIR%\sources\downloaders\youtube_downloader.py" set "FAILED=1" & echo   FAILED
if exist "%TEMP_DIR%\sources\downloaders\youtube_downloader.py" echo   OK

:: Download downloaders/__init__.py
echo [5/16] Downloading sources\downloaders\__init__.py...
powershell -command "& {Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/downloaders/__init__.py' -OutFile '%TEMP_DIR%\sources\downloaders\__init__.py'}" >nul 2>&1
if not exist "%TEMP_DIR%\sources\downloaders\__init__.py" set "FAILED=1" & echo   FAILED
if exist "%TEMP_DIR%\sources\downloaders\__init__.py" echo   OK

:: Download config.py
echo [6/16] Downloading sources\utils\config.py...
powershell -command "& {Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/utils/config.py' -OutFile '%TEMP_DIR%\sources\utils\config.py'}" >nul 2>&1
if not exist "%TEMP_DIR%\sources\utils\config.py" set "FAILED=1" & echo   FAILED
if exist "%TEMP_DIR%\sources\utils\config.py" echo   OK

:: Download ffmpeg.py
echo [7/16] Downloading sources\utils\ffmpeg.py...
powershell -command "& {Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/utils/ffmpeg.py' -OutFile '%TEMP_DIR%\sources\utils\ffmpeg.py'}" >nul 2>&1
if not exist "%TEMP_DIR%\sources\utils\ffmpeg.py" set "FAILED=1" & echo   FAILED
if exist "%TEMP_DIR%\sources\utils\ffmpeg.py" echo   OK

:: Download logger.py
echo [8/16] Downloading sources\utils\logger.py...
powershell -command "& {Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/utils/logger.py' -OutFile '%TEMP_DIR%\sources\utils\logger.py'}" >nul 2>&1
if not exist "%TEMP_DIR%\sources\utils\logger.py" set "FAILED=1" & echo   FAILED
if exist "%TEMP_DIR%\sources\utils\logger.py" echo   OK

:: Download ui.py
echo [9/16] Downloading sources\utils\ui.py...
powershell -command "& {Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/utils/ui.py' -OutFile '%TEMP_DIR%\sources\utils\ui.py'}" >nul 2>&1
if not exist "%TEMP_DIR%\sources\utils\ui.py" set "FAILED=1" & echo   FAILED
if exist "%TEMP_DIR%\sources\utils\ui.py" echo   OK

:: Download utils/__init__.py
echo [10/16] Downloading sources\utils\__init__.py...
powershell -command "& {Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/utils/__init__.py' -OutFile '%TEMP_DIR%\sources\utils\__init__.py'}" >nul 2>&1
if not exist "%TEMP_DIR%\sources\utils\__init__.py" set "FAILED=1" & echo   FAILED
if exist "%TEMP_DIR%\sources\utils\__init__.py" echo   OK

:: Download requirements.txt
echo [11/16] Downloading sources\requirements.txt...
powershell -command "& {Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/requirements.txt' -OutFile '%TEMP_DIR%\sources\requirements.txt'}" >nul 2>&1
if not exist "%TEMP_DIR%\sources\requirements.txt" set "FAILED=1" & echo   FAILED
if exist "%TEMP_DIR%\sources\requirements.txt" echo   OK

:: Download version.txt
echo [12/16] Downloading sources\version.txt...
powershell -command "& {Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/version.txt' -OutFile '%TEMP_DIR%\sources\version.txt'}" >nul 2>&1
if not exist "%TEMP_DIR%\sources\version.txt" set "FAILED=1" & echo   FAILED
if exist "%TEMP_DIR%\sources\version.txt" echo   OK

:: Download PortablePython.zip
echo [13/16] Downloading sources\PortablePython.zip...
powershell -command "& {Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/PortablePython.zip' -OutFile '%TEMP_DIR%\sources\PortablePython.zip'}" >nul 2>&1
if not exist "%TEMP_DIR%\sources\PortablePython.zip" set "FAILED=1" & echo   FAILED
if exist "%TEMP_DIR%\sources\PortablePython.zip" echo   OK

:: Download FFmpeg from a reliable source
echo [14/16] Downloading sources\FFmpeg\windows\ffmpeg\bin\ffmpeg.exe...
mkdir "%TEMP_DIR%\sources\FFmpeg\windows\ffmpeg\bin" 2>nul
powershell -command "& {Invoke-WebRequest -Uri 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip' -OutFile '%TEMP_DIR%\ffmpeg.zip'}" >nul 2>&1
if errorlevel 1 (
    echo   FAILED
    set "FAILED=1"
) else (
    :: Extract the ffmpeg.exe from the zip
    powershell -command "& {Add-Type -AssemblyName System.IO.Compression.FileSystem; [System.IO.Compression.ZipFile]::ExtractToDirectory('%TEMP_DIR%\ffmpeg.zip', '%TEMP_DIR%\ffmpeg_extract')}" >nul 2>&1
    if exist "%TEMP_DIR%\ffmpeg_extract\bin\ffmpeg.exe" (
        copy "%TEMP_DIR%\ffmpeg_extract\bin\ffmpeg.exe" "%TEMP_DIR%\sources\FFmpeg\windows\ffmpeg\bin\ffmpeg.exe" >nul
        echo   OK
    ) else (
        echo   FAILED
        set "FAILED=1"
    )
    :: Cleanup
    rmdir /s /q "%TEMP_DIR%\ffmpeg_extract" 2>nul
    del "%TEMP_DIR%\ffmpeg.zip" 2>nul
)

:: Download sources\__init__.py (main sources package init)
echo [15/16] Downloading sources\__init__.py...
type nul > "%TEMP_DIR%\sources\__init__.py" 2>nul
if exist "%TEMP_DIR%\sources\__init__.py" echo   OK

:: Download root-level __init__.py (optional, for package structure)
echo [16/16] Downloading __init__.py (root-level)...
type nul > "%TEMP_DIR%\__init__.py" 2>nul
if exist "%TEMP_DIR%\__init__.py" echo   OK

if "%FAILED%"=="1" (
    echo.
    echo [WARNING] Some files failed to download. Installation may be incomplete.
    echo Check your internet connection and try again.
    pause
)

echo.
echo Installing LinkCatty...

:: Remove old installation
if exist "%INSTALL_DIR%" rmdir /s /q "%INSTALL_DIR%" 2>nul
mkdir "%INSTALL_DIR%" 2>nul

:: Copy files
xcopy "%TEMP_DIR%\*" "%INSTALL_DIR%\" /E /I /Y /Q >nul
if errorlevel 1 (
    echo [ERROR] Failed to copy files.
    rmdir /s /q "%TEMP_DIR%" 2>nul
    pause
    exit /b 1
)

:: Rename run.cmd to linkcatty.bat
if exist "%INSTALL_DIR%\run.cmd" (
    move "%INSTALL_DIR%\run.cmd" "%INSTALL_DIR%\linkcatty.bat" >nul
)

:: Clean temp
rmdir /s /q "%TEMP_DIR%" 2>nul

:: Add to PATH
echo %PATH% | findstr /i "%INSTALL_DIR%" >nul
if errorlevel 1 (
    setx PATH "%INSTALL_DIR%;%PATH%" >nul 2>&1
)

:: Create shortcut
set "SHORTCUT_PATH=%APPDATA%\Microsoft\Windows\Start Menu\Programs\LinkCatty.lnk"
if not exist "%SHORTCUT_PATH%" (
    powershell -command "$WS = New-Object -ComObject WScript.Shell; $SC = $WS.CreateShortcut('%SHORTCUT_PATH%'); $SC.TargetPath = '%INSTALL_DIR%\linkcatty.bat'; $SC.Save()" >nul 2>&1
)

cls
echo.
echo ============================================================
echo               INSTALLATION SUCCESSFUL!
echo ============================================================
echo.
echo    LinkCatty has been installed to:
echo    %INSTALL_DIR%
echo.
echo    Run 'linkcatty' from any command prompt to start.
echo.
echo    Note:
echo      Close and reopen your terminal if 'linkcatty' is not recognized.
echo.
pause