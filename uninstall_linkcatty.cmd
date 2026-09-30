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
echo   %D%!G_DOT!%R% the LinkCatty folder  %D%!INSTALL_DIR!%R%
echo   %D%!G_DOT!%R% its entry in your PATH
echo   %D%!G_DOT!%R% the Start Menu and Desktop shortcuts
echo.
echo   %D%Your downloaded files are not touched.%R%
echo.
set "CONFIRM="
set /p "CONFIRM=  Continue? (y/n): "
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

if exist "%LOCALAPPDATA%\Microsoft\WindowsApps\linkcatty.cmd" del "%LOCALAPPDATA%\Microsoft\WindowsApps\linkcatty.cmd" >nul 2>&1
set "SHORTCUT_PATH=%APPDATA%\Microsoft\Windows\Start Menu\Programs\LinkCatty.lnk"
if exist "%SHORTCUT_PATH%" del "%SHORTCUT_PATH%" >nul 2>&1
if exist "%USERPROFILE%\Desktop\LinkCatty.lnk" del "%USERPROFILE%\Desktop\LinkCatty.lnk" >nul 2>&1
set "MSG=Shortcuts removed"
set "DET="
call :ui_ok

echo.
set "MSG=LINKCATTY IS UNINSTALLED"
call :ui_card_top
set "ROW_K=Next"
set "ROW_V=open a new terminal so the change takes effect"
call :ui_row
call :ui_card_end
echo.
pause
exit /b 0

rem ======================================================================
rem  Subroutines
rem ======================================================================

:ui_init
rem Colors and real glyphs only where the console can show them (Windows 10 or newer).
rem The glyphs are written as hex and decoded by certutil, so this file stays pure ASCII.
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
set "G_OK="
set "G_DOT="
if not defined ESC goto :ui_glyph_fallback
set "GL=%TEMP%\linkcatty_glyphs_%RANDOM%"
> "%GL%.hex" (
    echo e29c940d0a
    echo e29c960d0a
    echo e29aa00d0a
    echo e280ba0d0a
    echo e294810d0a
    echo e294800d0a
    echo e2948c0d0a
    echo e294820d0a
    echo e294940d0a
    echo e280a20d0a
    echo e2a08b0d0a
    echo e2a0990d0a
    echo e2a0b90d0a
    echo e2a0b80d0a
    echo e2a0bc0d0a
    echo e2a0b40d0a
    echo e2a0a60d0a
    echo e2a0a70d0a
    echo e2a0870d0a
    echo e2a08f0d0a
)
certutil -f -decodehex "%GL%.hex" "%GL%.txt" >nul 2>&1
if exist "%GL%.txt" (
    < "%GL%.txt" (
        set /p G_OK=
        set /p G_FAIL=
        set /p G_WARN=
        set /p G_ARROW=
        set /p G_BAR1=
        set /p G_BAR2=
        set /p G_TL=
        set /p G_V=
        set /p G_BL=
        set /p G_DOT=
        set /p G_SP0=
        set /p G_SP1=
        set /p G_SP2=
        set /p G_SP3=
        set /p G_SP4=
        set /p G_SP5=
        set /p G_SP6=
        set /p G_SP7=
        set /p G_SP8=
        set /p G_SP9=
    )
)
del "%GL%.hex" "%GL%.txt" 2>nul
:ui_glyph_fallback
if not defined G_DOT (
    set "G_OK=+"
    set "G_FAIL=x"
    set "G_WARN=*"
    set "G_ARROW=>"
    set "G_BAR1=#"
    set "G_BAR2=."
    set "G_TL=+"
    set "G_V=|"
    set "G_BL=+"
    set "G_DOT=-"
    set "G_SP0=-"
    set "G_SP1=\"
    set "G_SP2=|"
    set "G_SP3=/"
    set "G_SP4=-"
    set "G_SP5=\"
    set "G_SP6=|"
    set "G_SP7=/"
    set "G_SP8=-"
    set "G_SP9=\"
)
set "RULE="
for /l %%k in (1,1,58) do set "RULE=!RULE!!G_BAR2!"
set "SPIN_I=0"
set "BF_LAST=-1"
set "CUR_HIDDEN="
set "CUR_HIDE="
set "CUR_SHOW="
if defined ESC set "CUR_HIDE=%ESC%[?25l"
if defined ESC set "CUR_SHOW=%ESC%[?25h"
rem a run that was interrupted earlier may have left the cursor hidden
if defined ESC <nul set /p "=%CUR_SHOW%"
exit /b

:ui_header
echo.
echo   %D%- a Maiz's one -%R%
echo   %B%LinkCatty%R%  %D%%SHOW_VER%%R%
echo   %D%!RULE!%R%
exit /b

:ui_ok
echo   %G%!G_OK!%R% !MSG!  %D%!DET!%R%
exit /b

:ui_warn
echo   %Y%!G_WARN!%R% !MSG!  %D%!DET!%R%
exit /b

:ui_fail
echo   %RD%!G_FAIL!%R% !MSG!  %D%!DET!%R%
exit /b

:ui_arrow
echo   %C%!G_ARROW!%R% !MSG!  %D%!DET!%R%
exit /b

:ui_note
echo   %D%%~1%R%
exit /b

:ui_card_top
echo   %G%!G_TL! !G_OK! !MSG!%R%
exit /b

:ui_row
echo   %G%!G_V!%R%  %D%!ROW_K!%R%  !ROW_V!
exit /b

:ui_card_end
echo   %G%!G_BL!%R%
exit /b

:ui_bar
rem One in-place progress line from BAR_LABEL, BAR_DONE and BAR_TOTAL, same look as the app:
rem a spinner frame, the label, the bar, the percent and BAR_TEXT (or done/total).
rem It is redrawn with ANSI cursor codes (erase line + go to column 1); the old "carriage
rem return in a variable" trick prints nothing on current Windows builds. The blinking text
rem cursor is hidden while a bar is on screen (:ui_cursor_show brings it back).
rem Consoles without ANSI only get a final line.
set /a BP=BAR_DONE*100/BAR_TOTAL
set /a BF=BAR_DONE*28/BAR_TOTAL
set /a SPIN_I=(SPIN_I+1)%%10
for %%n in (!SPIN_I!) do set "SPIN_CH=!G_SP%%n!"
if not defined ESC goto :ui_bar_plain
if not defined CUR_HIDDEN (
    <nul set /p "=%CUR_HIDE%"
    set "CUR_HIDDEN=1"
)
if not "!BF!"=="!BF_LAST!" (
    set "BB1="
    set "BB2="
    for /l %%k in (1,1,28) do (
        if %%k leq !BF! (set "BB1=!BB1!!G_BAR1!") else (set "BB2=!BB2!!G_BAR2!")
    )
    set "BF_LAST=!BF!"
)
set "BT=!BAR_DONE!/!BAR_TOTAL!"
if defined BAR_TEXT set "BT=!BAR_TEXT!"
<nul set /p "=%ESC%[2K%ESC%[1G  %C%!SPIN_CH!%R% !BAR_LABEL!  %C%!BB1!%R%%D%!BB2!%R%  %B%!BP!%%%R%  %D%!BT!%R%"
exit /b
:ui_bar_plain
if "!BAR_DONE!"=="!BAR_TOTAL!" <nul set /p "=  !BAR_LABEL!  done"
exit /b

:ui_cursor_show
if defined CUR_HIDDEN (
    <nul set /p "=%CUR_SHOW%"
    set "CUR_HIDDEN="
)
exit /b
