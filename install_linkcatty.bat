@echo off
chcp 65001 >nul 2>&1
title LinkCatty Installer
setlocal enabledelayedexpansion

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

:: Download files
echo Downloading files from GitHub...

:: Download run.bat
echo   - Downloading run.bat...
powershell -command "& {Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/maiz-an/LinkCatty/main/run.bat' -OutFile '%TEMP_DIR%\run.bat'}" >nul 2>&1

:: Download sources structure
echo   - Downloading sources\LinkCatty.py...
powershell -command "& {Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/LinkCatty.py' -OutFile '%TEMP_DIR%\sources\LinkCatty.py'}" >nul 2>&1

echo   - Downloading sources\downloaders\spotify_downloader.py...
powershell -command "& {Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/downloaders/spotify_downloader.py' -OutFile '%TEMP_DIR%\sources\downloaders\spotify_downloader.py'}" >nul 2>&1

echo   - Downloading sources\downloaders\youtube_downloader.py...
powershell -command "& {Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/downloaders/youtube_downloader.py' -OutFile '%TEMP_DIR%\sources\downloaders\youtube_downloader.py'}" >nul 2>&1

echo   - Downloading sources\downloaders\__init__.py...
powershell -command "& {Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/downloaders/__init__.py' -OutFile '%TEMP_DIR%\sources\downloaders\__init__.py'}" >nul 2>&1

echo   - Downloading sources\utils\config.py...
powershell -command "& {Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/utils/config.py' -OutFile '%TEMP_DIR%\sources\utils\config.py'}" >nul 2>&1

echo   - Downloading sources\utils\ffmpeg.py...
powershell -command "& {Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/utils/ffmpeg.py' -OutFile '%TEMP_DIR%\sources\utils\ffmpeg.py'}" >nul 2>&1

echo   - Downloading sources\utils\logger.py...
powershell -command "& {Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/utils/logger.py' -OutFile '%TEMP_DIR%\sources\utils\logger.py'}" >nul 2>&1

echo   - Downloading sources\utils\ui.py...
powershell -command "& {Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/utils/ui.py' -OutFile '%TEMP_DIR%\sources\utils\ui.py'}" >nul 2>&1

echo   - Downloading sources\utils\__init__.py...
powershell -command "& {Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/utils/__init__.py' -OutFile '%TEMP_DIR%\sources\utils\__init__.py'}" >nul 2>&1

echo   - Downloading sources\requirements.txt...
powershell -command "& {Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/requirements.txt' -OutFile '%TEMP_DIR%\sources\requirements.txt'}" >nul 2>&1

echo   - Downloading sources\version.txt...
powershell -command "& {Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/version.txt' -OutFile '%TEMP_DIR%\sources\version.txt'}" >nul 2>&1

:: Optional: PortablePython.zip and FFmpeg (if they exist on GitHub releases)
echo   - Downloading sources\PortablePython.zip...
powershell -command "& {Invoke-WebRequest -Uri 'https://github.com/maiz-an/LinkCatty/releases/download/v1.0/PortablePython.zip' -OutFile '%TEMP_DIR%\sources\PortablePython.zip'}" >nul 2>&1

echo   - Downloading sources\FFmpeg\windows\ffmpeg\bin\ffmpeg.exe...
powershell -command "& {mkdir '%TEMP_DIR%\sources\FFmpeg\windows\ffmpeg\bin' -Force >nul 2>&1; Invoke-WebRequest -Uri 'https://github.com/maiz-an/LinkCatty/releases/download/v1.0/ffmpeg.exe' -OutFile '%TEMP_DIR%\sources\FFmpeg\windows\ffmpeg\bin\ffmpeg.exe'}" >nul 2>&1

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

:: Rename run.bat to linkcatty.bat
if exist "%INSTALL_DIR%\run.bat" (
    move "%INSTALL_DIR%\run.bat" "%INSTALL_DIR%\linkcatty.bat" >nul
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
echo Note:
echo Close and reopen your terminal if 'linkcatty' is not recognized.
echo.
pause