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

if exist "%INSTALL_DIR%\linkcatty.bat" (
    echo [WARNING] LinkCatty is already installed.
    set /p "OVERWRITE=Reinstall/update? (y/n): "
    if /i not "!OVERWRITE!"=="y" exit /b 0
    echo.
)

:: Clean temp
if exist "%TEMP_DIR%" rmdir /s /q "%TEMP_DIR%" 2>nul
mkdir "%TEMP_DIR%" 2>nul

echo Downloading files from GitHub...
echo.

:: Create directories
mkdir "%TEMP_DIR%\sources" 2>nul
mkdir "%TEMP_DIR%\sources\downloaders" 2>nul
mkdir "%TEMP_DIR%\sources\utils" 2>nul

:: List of files to download (local path and URL)
set "FILE_LIST[0]=run.cmd|https://raw.githubusercontent.com/maiz-an/LinkCatty/main/run.cmd"
set "FILE_LIST[1]=sources\LinkCatty.py|https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/LinkCatty.py"
set "FILE_LIST[2]=sources\downloaders\spotify_downloader.py|https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/downloaders/spotify_downloader.py"
set "FILE_LIST[3]=sources\downloaders\youtube_downloader.py|https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/downloaders/youtube_downloader.py"
set "FILE_LIST[4]=sources\downloaders\__init__.py|https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/downloaders/__init__.py"
set "FILE_LIST[5]=sources\utils\config.py|https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/utils/config.py"
set "FILE_LIST[6]=sources\utils\ffmpeg.py|https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/utils/ffmpeg.py"
set "FILE_LIST[7]=sources\utils\logger.py|https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/utils/logger.py"
set "FILE_LIST[8]=sources\utils\ui.py|https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/utils/ui.py"
set "FILE_LIST[9]=sources\utils\__init__.py|https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/utils/__init__.py"
set "FILE_LIST[10]=sources\requirements.txt|https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/requirements.txt"
set "FILE_LIST[11]=sources\version.txt|https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/version.txt"
set "FILE_LIST[12]=sources\PortablePython.zip|https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/PortablePython.zip"
set "FILE_LIST[13]=sources\__init__.py|https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/__init__.py"
set "FILE_LIST[14]=uninstall_linkcatty.cmd|https://raw.githubusercontent.com/maiz-an/LinkCatty/main/uninstall_linkcatty.cmd"
set "FILE_LIST[15]=uninstall_linkcatty.sh|https://raw.githubusercontent.com/maiz-an/LinkCatty/main/uninstall_linkcatty.sh"
set "TOTAL=16"

:: Download FFmpeg separately
set "FFMPEG_URL=https://github.com/maiz-an/LinkCatty/releases/download/FFmpeg/win-x64.zip"

set "DOWNLOADED=0"
for /l %%i in (0,1,15) do (
    set /a DOWNLOADED+=1
    set /a PERCENT=!DOWNLOADED! * 100 / !TOTAL!
    <nul set /p "=Progress: [!DOWNLOADED!/!TOTAL!] !PERCENT!%%  "
    set "entry=!FILE_LIST[%%i]!"
    for /f "tokens=1,2 delims=|" %%a in ("!entry!") do (
        set "FILE_PATH=%%a"
        set "FILE_URL=%%b"
    )
    for %%f in ("!FILE_PATH!") do set "FILE_DIR=%%~dpf"
    if not exist "%TEMP_DIR%\!FILE_DIR!" mkdir "%TEMP_DIR%\!FILE_DIR!" 2>nul
    powershell -command "& { $ProgressPreference = 'SilentlyContinue'; Invoke-WebRequest -Uri '!FILE_URL!' -OutFile '%TEMP_DIR%\!FILE_PATH!' }" >nul 2>&1
    echo Done
)

:: Download FFmpeg
set /a DOWNLOADED+=1
set /a PERCENT=!DOWNLOADED! * 100 / 17
<nul set /p "=Progress: [17/17] - Downloading FFmpeg... "
mkdir "%TEMP_DIR%\sources\FFmpeg\windows\ffmpeg\bin" 2>nul
set "FFMPEG_ZIP=%TEMP%\ffmpeg_win64.zip"
set "FFMPEG_EXTRACT=%TEMP%\ffmpeg_extract"
powershell -command "& {Invoke-WebRequest -Uri '%FFMPEG_URL%' -OutFile '%FFMPEG_ZIP%'}" >nul 2>&1
if errorlevel 1 (
    echo FAILED
) else (
    powershell -command "& {Add-Type -AssemblyName System.IO.Compression.FileSystem; [System.IO.Compression.ZipFile]::ExtractToDirectory('%FFMPEG_ZIP%', '%FFMPEG_EXTRACT%')}" >nul 2>&1
    if exist "%FFMPEG_EXTRACT%\ffmpeg.exe" (
        copy "%FFMPEG_EXTRACT%\ffmpeg.exe" "%TEMP_DIR%\sources\FFmpeg\windows\ffmpeg\bin\ffmpeg.exe" >nul
        echo OK
    ) else if exist "%FFMPEG_EXTRACT%\win-x64\ffmpeg.exe" (
        copy "%FFMPEG_EXTRACT%\win-x64\ffmpeg.exe" "%TEMP_DIR%\sources\FFmpeg\windows\ffmpeg\bin\ffmpeg.exe" >nul
        echo OK
    ) else (
        echo FAILED
    )
    rmdir /s /q "%FFMPEG_EXTRACT%" 2>nul
    del "%FFMPEG_ZIP%" 2>nul
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
if exist "%INSTALL_DIR%\run.cmd" move "%INSTALL_DIR%\run.cmd" "%INSTALL_DIR%\linkcatty.bat" >nul

:: Clean temp
rmdir /s /q "%TEMP_DIR%" 2>nul

:: Add to PATH
echo %PATH% | findstr /i "%INSTALL_DIR%" >nul
if errorlevel 1 setx PATH "%INSTALL_DIR%;%PATH%" >nul 2>&1

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
echo    Note: Close and reopen your terminal if 'linkcatty' is not recognized.
echo.
pause