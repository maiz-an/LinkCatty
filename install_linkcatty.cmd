@echo off
chcp 65001 >nul 2>&1
title LinkCatty Setup
setlocal enabledelayedexpansion

rem LinkCatty Installer (Windows)
rem NOTE: this file must stay pure ASCII with CRLF line endings (see .gitattributes).

set "INSTALL_DIR=%LOCALAPPDATA%\LinkCatty"
set "TEMP_DIR=%TEMP%\LinkCatty_temp"

call :ui_init
cls
set "SHOW_VER=Setup"
call :ui_header

if exist "%INSTALL_DIR%\linkcatty.bat" (
    set "MSG=LinkCatty is already installed"
    set "DET="
    call :ui_warn
    set /p "OVERWRITE=    Reinstall / update? (y/n): "
    if /i not "!OVERWRITE!"=="y" exit /b 0
    echo.
)

rem raw.githubusercontent.com caches "main" for ~5 minutes. Ask git (never cached) for
rem the latest commit and download every file from that exact commit, so a fresh
rem install can never mix files of two versions. Falls back to "main".
set "REF=main"
set "REF_FILE=%TEMP%\linkcatty_ref.txt"
del "%REF_FILE%" 2>nul
powershell -NoProfile -Command "& { try { $r = Invoke-WebRequest -UseBasicParsing -TimeoutSec 8 -Uri 'https://github.com/maiz-an/LinkCatty.git/info/refs?service=git-upload-pack'; $t = if ($r.Content -is [byte[]]) { [Text.Encoding]::ASCII.GetString($r.Content) } else { [string]$r.Content }; if ($t -match '([0-9a-f]{40}) refs/heads/main') { $matches[1] | Set-Content -Encoding ascii '%REF_FILE%' } } catch {} }" >nul 2>&1
if exist "%REF_FILE%" (
    for /f "usebackq delims=" %%R in ("%REF_FILE%") do set "REF=%%R"
    del "%REF_FILE%" 2>nul
)

if exist "%TEMP_DIR%" rmdir /s /q "%TEMP_DIR%" 2>nul
mkdir "%TEMP_DIR%" 2>nul

rem List of files to download (local path | URL)
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
set "FILE_LIST[13]=uninstall_linkcatty.cmd|https://raw.githubusercontent.com/maiz-an/LinkCatty/main/uninstall_linkcatty.cmd"
set "FILE_LIST[14]=uninstall_linkcatty.sh|https://raw.githubusercontent.com/maiz-an/LinkCatty/main/uninstall_linkcatty.sh"
set "FILE_LIST[15]=sources\downloaders\other_downloader.py|https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/downloaders/other_downloader.py"
set "FILE_LIST[16]=sources\downloaders\universal.py|https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/downloaders/universal.py"
set "FILE_LIST[17]=run.sh|https://raw.githubusercontent.com/maiz-an/LinkCatty/main/run.sh"
set "TOTAL=18"
set /a STEPS=TOTAL+1

set "FFMPEG_URL=https://github.com/maiz-an/LinkCatty/releases/download/FFmpeg/win-x64.zip"

set "DL_FAILED=0"
set "BAR_LABEL=Downloading"
set "BAR_TOTAL=%STEPS%"
for /l %%i in (0,1,17) do (
    set /a BAR_DONE=%%i
    call :ui_bar
    call :GetFile %%i
)

if "!DL_FAILED!"=="1" (
    echo.
    echo.
    set "MSG=Could not download !FAILED_FILE!"
    set "DET="
    call :ui_fail
    call :ui_note "Check your internet connection and run the installer again."
    call :ui_note "Nothing was changed on your computer."
    rmdir /s /q "%TEMP_DIR%" 2>nul
    echo.
    pause
    exit /b 1
)

rem FFmpeg (a failure here is not fatal: audio downloads still work)
set /a BAR_DONE=TOTAL
call :ui_bar
mkdir "%TEMP_DIR%\sources\FFmpeg\windows\ffmpeg\bin" 2>nul
set "FFMPEG_ZIP=%TEMP%\ffmpeg_win64.zip"
set "FFMPEG_EXTRACT=%TEMP%\ffmpeg_extract"
set "FFMPEG_OK=0"
if exist "%FFMPEG_EXTRACT%" rmdir /s /q "%FFMPEG_EXTRACT%" 2>nul
del "%FFMPEG_ZIP%" 2>nul
powershell -NoProfile -Command "& { $ProgressPreference = 'SilentlyContinue'; try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 180 -Uri '%FFMPEG_URL%' -OutFile '%FFMPEG_ZIP%'; exit 0 } catch { exit 1 } }" >nul 2>&1
if not errorlevel 1 (
    powershell -NoProfile -Command "& { Add-Type -AssemblyName System.IO.Compression.FileSystem; [System.IO.Compression.ZipFile]::ExtractToDirectory('%FFMPEG_ZIP%', '%FFMPEG_EXTRACT%') }" >nul 2>&1
    if exist "%FFMPEG_EXTRACT%\ffmpeg.exe" (
        copy "%FFMPEG_EXTRACT%\ffmpeg.exe" "%TEMP_DIR%\sources\FFmpeg\windows\ffmpeg\bin\ffmpeg.exe" >nul
        set "FFMPEG_OK=1"
    ) else if exist "%FFMPEG_EXTRACT%\win-x64\ffmpeg.exe" (
        copy "%FFMPEG_EXTRACT%\win-x64\ffmpeg.exe" "%TEMP_DIR%\sources\FFmpeg\windows\ffmpeg\bin\ffmpeg.exe" >nul
        set "FFMPEG_OK=1"
    )
)
rmdir /s /q "%FFMPEG_EXTRACT%" 2>nul
del "%FFMPEG_ZIP%" 2>nul
set "BAR_DONE=!STEPS!"
call :ui_bar
echo.
echo.

rem ---- install ---------------------------------------------------------
set "MSG=Installing"
set "DET="
call :ui_arrow

rem keep the user's settings and history when reinstalling
if exist "%INSTALL_DIR%\sources\settings.json" copy /y "%INSTALL_DIR%\sources\settings.json" "%TEMP%\linkcatty_settings.keep" >nul
if exist "%INSTALL_DIR%\sources\download_history.json" copy /y "%INSTALL_DIR%\sources\download_history.json" "%TEMP%\linkcatty_history.keep" >nul

if exist "%INSTALL_DIR%" rmdir /s /q "%INSTALL_DIR%" 2>nul
mkdir "%INSTALL_DIR%" 2>nul

xcopy "%TEMP_DIR%\*" "%INSTALL_DIR%\" /E /I /Y /Q >nul
if errorlevel 1 (
    set "MSG=Could not copy the files"
    set "DET="
    call :ui_fail
    rmdir /s /q "%TEMP_DIR%" 2>nul
    echo.
    pause
    exit /b 1
)

if exist "%INSTALL_DIR%\run.cmd" move /y "%INSTALL_DIR%\run.cmd" "%INSTALL_DIR%\linkcatty.bat" >nul

if exist "%TEMP%\linkcatty_settings.keep" (
    copy /y "%TEMP%\linkcatty_settings.keep" "%INSTALL_DIR%\sources\settings.json" >nul
    del "%TEMP%\linkcatty_settings.keep" 2>nul
)
if exist "%TEMP%\linkcatty_history.keep" (
    copy /y "%TEMP%\linkcatty_history.keep" "%INSTALL_DIR%\sources\download_history.json" >nul
    del "%TEMP%\linkcatty_history.keep" 2>nul
)
rmdir /s /q "%TEMP_DIR%" 2>nul

rem ---- PATH (user scope, appended safely; never rewrites the whole PATH) -
powershell -NoProfile -Command "& { $d = '%INSTALL_DIR%'; $p = [Environment]::GetEnvironmentVariable('Path','User'); if (-not $p) { $p = '' }; $parts = @($p -split ';' | Where-Object { $_ }); if ($parts -notcontains $d) { [Environment]::SetEnvironmentVariable('Path', (($parts + $d) -join ';'), 'User') } }" >nul 2>&1
set "PATH_OK=1"
if errorlevel 1 set "PATH_OK=0"

rem ---- Start Menu shortcut ---------------------------------------------
set "SHORTCUT_PATH=%APPDATA%\Microsoft\Windows\Start Menu\Programs\LinkCatty.lnk"
if not exist "%SHORTCUT_PATH%" (
    powershell -NoProfile -Command "$WS = New-Object -ComObject WScript.Shell; $SC = $WS.CreateShortcut('%SHORTCUT_PATH%'); $SC.TargetPath = '%INSTALL_DIR%\linkcatty.bat'; $SC.Save()" >nul 2>&1
)

set "INSTALLED_VER=?"
if exist "%INSTALL_DIR%\sources\version.txt" (
    for /f "usebackq delims=" %%i in ("%INSTALL_DIR%\sources\version.txt") do set "INSTALLED_VER=%%i"
)

set "MSG=LinkCatty is installed"
set "DET=v!INSTALLED_VER!"
call :ui_ok
if "!FFMPEG_OK!"=="0" (
    set "MSG=FFmpeg could not be downloaded"
    set "DET=it is fetched on first use; video merging needs it"
    call :ui_warn
)
if "!PATH_OK!"=="0" (
    set "MSG=Could not add LinkCatty to your PATH"
    set "DET=start it with the full path below"
    call :ui_warn
)
echo.
echo   %G%+- READY%R%
echo   %G%^|%R%  %D%Location   %R%!INSTALL_DIR!
echo   %G%^|%R%  %D%Downloads  %R%your Downloads folder, in a LinkCatty folder
echo   %G%^|%R%  %D%Start      %R%open a new terminal and type  %B%linkcatty%R%
echo   %G%+-%R%
echo.
set "STARTNOW="
set /p "STARTNOW=    Start LinkCatty now? (Y/n): "
if /i "!STARTNOW!"=="n" exit /b 0
call "%INSTALL_DIR%\linkcatty.bat"
exit /b 0

rem ======================================================================
rem  Subroutines
rem ======================================================================

:GetFile
set "idx=%1"
set "entry=!FILE_LIST[%idx%]!"
for /f "tokens=1,2 delims=|" %%a in ("!entry!") do (
    set "FILE_PATH=%%a"
    set "FILE_URL=%%b"
)
set "FILE_URL=!FILE_URL:/LinkCatty/main/=/LinkCatty/%REF%/!"
for %%f in ("%TEMP_DIR%\!FILE_PATH!") do set "OUT_DIR=%%~dpf"
if not exist "!OUT_DIR!" mkdir "!OUT_DIR!" 2>nul
set "TRY=0"
:GetTry
set /a TRY+=1
powershell -NoProfile -Command "& { $ProgressPreference = 'SilentlyContinue'; try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 60 -Uri '!FILE_URL!' -OutFile '%TEMP_DIR%\!FILE_PATH!'; exit 0 } catch { exit 1 } }" >nul 2>&1
if errorlevel 1 (
    if !TRY! LSS 3 (
        ping -n 2 127.0.0.1 >nul
        goto :GetTry
    )
    set "DL_FAILED=1"
    set "FAILED_FILE=!FILE_PATH!"
    exit /b 1
)
rem .cmd files must be CRLF + ASCII whatever the server sent
if /i "%FILE_PATH:~-4%"==".cmd" powershell -NoProfile -Command "& { $p='%TEMP_DIR%\!FILE_PATH!'; if (Test-Path $p) { $t=[IO.File]::ReadAllText($p); [IO.File]::WriteAllText($p, ($t -replace '\r?\n', ([string][char]13 + [char]10)), [Text.Encoding]::ASCII) } }" >nul 2>&1
exit /b

:ui_init
rem Colors only where the console understands them (Windows 10 or newer)
set "ESC="
set "R="
set "B="
set "D="
set "G="
set "Y="
set "RD="
set "C="
set "WINVER=0"
for /f "tokens=4 delims=. " %%v in ('ver') do set "WINVER=%%v"
if %WINVER% GEQ 10 (
    for /f %%a in ('echo prompt $E ^| cmd') do set "ESC=%%a"
)
if defined ESC (
    set "R=%ESC%[0m"
    set "B=%ESC%[1m"
    set "D=%ESC%[2m"
    set "G=%ESC%[32m"
    set "Y=%ESC%[33m"
    set "RD=%ESC%[31m"
    set "C=%ESC%[36m"
)
exit /b

:ui_header
echo.
echo   %D%- a Maiz's one -%R%
echo   %B%LinkCatty%R%  %D%%SHOW_VER%%R%
echo   %D%----------------------------------------------------------%R%
exit /b

:ui_ok
echo   %G%+%R% !MSG!  %D%!DET!%R%
exit /b

:ui_warn
echo   %Y%^^!%R% !MSG!  %D%!DET!%R%
exit /b

:ui_fail
echo   %RD%x%R% !MSG!  %D%!DET!%R%
exit /b

:ui_arrow
echo   %C%^>%R% !MSG!  %D%!DET!%R%
exit /b

:ui_note
echo   %D%%~1%R%
exit /b

:ui_bar
rem One in-place progress line from BAR_LABEL, BAR_DONE and BAR_TOTAL. The line is redrawn with
rem ANSI cursor codes (erase line + go to column 1); the classic "carriage return in a
rem variable" trick prints nothing on current Windows builds. The bar is drawn with
rem colored spaces (solid look, ASCII only). Consoles without ANSI only get a final line.
set /a BP=BAR_DONE*100/BAR_TOTAL
set /a BF=BAR_DONE*28/BAR_TOTAL
if not defined ESC goto :ui_bar_plain
set "BB1="
set "BB2="
for /l %%k in (1,1,28) do (
    if %%k leq !BF! (set "BB1=!BB1! ") else (set "BB2=!BB2! ")
)
<nul set /p "=%ESC%[2K%ESC%[1G  %C%!BAR_LABEL!%R%  %ESC%[46m!BB1!%ESC%[100m!BB2!%R%  %B%!BP!%%%R%  %D%!BAR_DONE!/!BAR_TOTAL!%R%"
exit /b
:ui_bar_plain
if "!BAR_DONE!"=="!BAR_TOTAL!" <nul set /p "=  !BAR_LABEL!  done (!BAR_DONE!/!BAR_TOTAL!)"
exit /b
