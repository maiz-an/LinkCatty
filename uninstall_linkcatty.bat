@echo off
chcp 65001 >nul 2>&1
title LinkCatty Uninstaller
setlocal enabledelayedexpansion

set "INSTALL_DIR=%LOCALAPPDATA%\LinkCatty"

echo.
echo ============================================================
echo                  LinkCatty Uninstaller
echo ============================================================
echo.

if not exist "%INSTALL_DIR%" (
    echo LinkCatty is not installed.
    pause
    exit /b 0
)

echo This will remove:
echo   - Installation folder: %INSTALL_DIR%
echo   - From user PATH
echo   - Start Menu shortcut
echo.
set /p "CONFIRM=Continue? (y/n): "
if /i not "!CONFIRM!"=="y" exit /b 0

echo.
echo [1/3] Removing files...
rmdir /s /q "%INSTALL_DIR%" 2>nul
if exist "%INSTALL_DIR%" (
    echo [ERROR] Could not remove folder. Close any running LinkCatty processes.
    pause
    exit /b 1
)
echo [1/3] Done.

echo [2/3] Removing from PATH...
:: Build new PATH without the installation directory
set "NEW_PATH="
for %%a in ("%PATH:;=";"%") do (
    if /i not "%%~a"=="%INSTALL_DIR%" (
        if defined NEW_PATH (set "NEW_PATH=!NEW_PATH!;%%~a") else (set "NEW_PATH=%%~a")
    )
)
setx PATH "!NEW_PATH!" >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Could not update PATH automatically. You may need to remove it manually.
) else (
    echo Removed from user PATH.
)
echo [2/3] Done.

echo [3/3] Removing Start Menu shortcut...
set "SHORTCUT_PATH=%APPDATA%\Microsoft\Windows\Start Menu\Programs\LinkCatty.lnk"
if exist "%SHORTCUT_PATH%" del "%SHORTCUT_PATH%" >nul 2>&1
echo [3/3] Done.

echo.
echo UNINSTALL COMPLETE!
echo.
echo You may need to restart your command prompt for changes to take effect.
echo.
pause