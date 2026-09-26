@echo off
chcp 65001 >nul 2>&1
title LinkCatty Uninstall
setlocal enabledelayedexpansion

rem LinkCatty Uninstaller (Windows)
rem NOTE: this file must stay pure ASCII with CRLF line endings (see .gitattributes).

set "INSTALL_DIR=%LOCALAPPDATA%\LinkCatty"

rem Running from inside the install folder? Continue from a temp copy so the folder can be deleted.
rem The copy is started as a separate window and this one ends at once: a batch file that
rem is deleted while another one still has to return into it makes cmd print errors.
if /i "%~dp0"=="%INSTALL_DIR%\" if /i not "%~1"=="--from-temp" (
    copy /y "%~f0" "%TEMP%\linkcatty_uninstall.cmd" >nul
    start "LinkCatty Uninstall" "%TEMP%\linkcatty_uninstall.cmd" --from-temp
    exit /b 0
)

call :ui_init
set "SHOW_VER=Uninstall"
call :ui_header

if not exist "%INSTALL_DIR%" (
    set "MSG=LinkCatty is not installed"
    set "DET="
    call :ui_warn
    echo.
    pause
    exit /b 0
)

echo.
echo   %D%This will remove%R%
echo   %D%-%R% the LinkCatty folder  %D%!INSTALL_DIR!%R%
echo   %D%-%R% its entry in your PATH
echo   %D%-%R% the Start Menu shortcut
echo.
echo   %D%Your downloaded files are not touched.%R%
echo.
set "CONFIRM="
set /p "CONFIRM=    Continue? (y/n): "
if /i not "!CONFIRM!"=="y" exit /b 0
echo.

rmdir /s /q "%INSTALL_DIR%" 2>nul
if exist "%INSTALL_DIR%" (
    set "MSG=Could not remove the folder"
    set "DET=close any running LinkCatty window first"
    call :ui_fail
    echo.
    pause
    exit /b 1
)
set "MSG=Files removed"
set "DET="
call :ui_ok

powershell -NoProfile -Command "& { $d = '%INSTALL_DIR%'.TrimEnd('\'); $p = [Environment]::GetEnvironmentVariable('Path','User'); if ($p) { $parts = @($p -split ';' | Where-Object { $_ -and ($_.TrimEnd('\') -ine $d) }); [Environment]::SetEnvironmentVariable('Path', ($parts -join ';'), 'User') } }" >nul 2>&1
if errorlevel 1 (
    set "MSG=Could not update your PATH"
    set "DET=remove the LinkCatty folder from it by hand"
    call :ui_warn
) else (
    set "MSG=Removed from PATH"
    set "DET="
    call :ui_ok
)

set "SHORTCUT_PATH=%APPDATA%\Microsoft\Windows\Start Menu\Programs\LinkCatty.lnk"
if exist "%SHORTCUT_PATH%" del "%SHORTCUT_PATH%" >nul 2>&1
set "MSG=Shortcut removed"
set "DET="
call :ui_ok

echo.
echo   %G%+- LINKCATTY IS UNINSTALLED%R%
echo   %G%^|%R%  %D%Open a new terminal so the change takes effect.%R%
echo   %G%+-%R%
echo.
pause
exit /b 0

rem ======================================================================
rem  Subroutines
rem ======================================================================

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
