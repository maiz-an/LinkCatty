@echo off
chcp 65001 >nul 2>&1
title LinkCatty
setlocal enabledelayedexpansion

rem LinkCatty Launcher (Windows)
rem NOTE: this file must stay pure ASCII with CRLF line endings (see .gitattributes).

rem ---- flags -----------------------------------------------------------
echo %* | findstr /i "\-\-uninstall" >nul
if not errorlevel 1 goto :DoUninstall

echo %* | findstr /i "\-\-location" >nul
if not errorlevel 1 (
    echo.
    echo LinkCatty is installed at:
    echo %~dp0
    exit /b 0
)

set "FORCE_UPDATE=0"
echo %* | findstr /i "\-\-update" >nul
if not errorlevel 1 set "FORCE_UPDATE=1"

rem --repaired / --restarted: this is a restart after an update, never update again
set "RESTARTED=0"
echo %* | findstr /i "\-\-repaired \-\-restarted" >nul
if not errorlevel 1 set "RESTARTED=1"

mode con cols=62 lines=30 >nul 2>&1

rem ---- look and feel ---------------------------------------------------
call :ui_init

set "LOCAL_VER=0.0.0"
if exist "%~dp0sources\version.txt" (
    for /f "usebackq delims=" %%i in ("%~dp0sources\version.txt") do set "LOCAL_VER=%%i"
)
set "SHOW_VER=v%LOCAL_VER%"
call :ui_header

rem ---- 1. updates ------------------------------------------------------
rem raw.githubusercontent.com caches "main" for ~5 minutes and ignores query strings.
rem Ask git (never cached) for the latest commit SHA and download from a SHA-pinned URL.
rem If the lookup fails we fall back to "main".
set "REF=main"
set "REF_FILE=%TEMP%\linkcatty_ref.txt"
del "%REF_FILE%" 2>nul
powershell -NoProfile -Command "& { try { $r = Invoke-WebRequest -UseBasicParsing -TimeoutSec 8 -Uri 'https://github.com/maiz-an/LinkCatty.git/info/refs?service=git-upload-pack'; $t = if ($r.Content -is [byte[]]) { [Text.Encoding]::ASCII.GetString($r.Content) } else { [string]$r.Content }; if ($t -match '([0-9a-f]{40}) refs/heads/main') { $matches[1] | Set-Content -Encoding ascii '%REF_FILE%' } } catch {} }" >nul 2>&1
if exist "%REF_FILE%" (
    for /f "usebackq delims=" %%R in ("%REF_FILE%") do set "REF=%%R"
    del "%REF_FILE%" 2>nul
)
set "RAW_BASE=https://raw.githubusercontent.com/maiz-an/LinkCatty/%REF%"

set "TEMP_FILE=%TEMP%\remote_version.txt"
del "%TEMP_FILE%" 2>nul
powershell -NoProfile -Command "& { $ProgressPreference='SilentlyContinue'; try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 8 -Uri '%RAW_BASE%/sources/version.txt' -OutFile '%TEMP_FILE%' } catch {} }" >nul 2>&1
set "REMOTE_VER=%LOCAL_VER%"
if exist "%TEMP_FILE%" (
    for /f "usebackq delims=" %%A in ("%TEMP_FILE%") do set "REMOTE_VER=%%A"
    del "%TEMP_FILE%"
)

set "FILE_LIST[0]=sources\downloaders\spotify_downloader.py|https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/downloaders/spotify_downloader.py"
set "FILE_LIST[1]=sources\downloaders\youtube_downloader.py|https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/downloaders/youtube_downloader.py"
set "FILE_LIST[2]=sources\utils\config.py|https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/utils/config.py"
set "FILE_LIST[3]=sources\utils\ffmpeg.py|https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/utils/ffmpeg.py"
set "FILE_LIST[4]=sources\utils\logger.py|https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/utils/logger.py"
set "FILE_LIST[5]=sources\utils\ui.py|https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/utils/ui.py"
set "FILE_LIST[6]=sources\requirements.txt|https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/requirements.txt"
set "FILE_LIST[7]=sources\version.txt|https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/version.txt"
set "FILE_LIST[8]=run.sh|https://raw.githubusercontent.com/maiz-an/LinkCatty/main/run.sh"
set "FILE_LIST[9]=uninstall_linkcatty.cmd|https://raw.githubusercontent.com/maiz-an/LinkCatty/main/uninstall_linkcatty.cmd"
set "FILE_LIST[10]=uninstall_linkcatty.sh|https://raw.githubusercontent.com/maiz-an/LinkCatty/main/uninstall_linkcatty.sh"
set "FILE_LIST[11]=sources\LinkCatty.py|https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/LinkCatty.py"
set "FILE_LIST[12]=sources\downloaders\other_downloader.py|https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/downloaders/other_downloader.py"
set "FILE_LIST[13]=sources\downloaders\universal.py|https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/downloaders/universal.py"
set "TOTAL_FILES=14"

rem If a managed file is missing (e.g. a module added in a newer release), repair by
rem re-downloading. The restart flag stops any update loop.
set "MISSING=0"
if "%RESTARTED%"=="0" (
    for /l %%i in (0,1,99) do (
        if defined FILE_LIST[%%i] (
            for /f "tokens=1 delims=|" %%p in ("!FILE_LIST[%%i]!") do (
                if not exist "%~dp0%%p" set "MISSING=1"
            )
        )
    )
)

set "NEED_UPDATE=0"
set "UPDATE_KIND=update"
if "%RESTARTED%"=="0" (
    if not "%LOCAL_VER%"=="%REMOTE_VER%" set "NEED_UPDATE=1"
    if "%FORCE_UPDATE%"=="1" set "NEED_UPDATE=1"
    if "!NEED_UPDATE!"=="0" if "%MISSING%"=="1" (
        set "NEED_UPDATE=1"
        set "UPDATE_KIND=repair"
    )
)

if "%NEED_UPDATE%"=="0" (
    set "MSG=Up to date"
    set "DET=v%LOCAL_VER%"
    call :ui_ok
)

if "%NEED_UPDATE%"=="1" (
    if "%UPDATE_KIND%"=="repair" (
        set "MSG=Repairing missing files"
        set "DET="
    ) else (
        set "MSG=Update available"
        set "DET=%LOCAL_VER% -> %REMOTE_VER%"
        if "%FORCE_UPDATE%"=="1" set "DET=latest is %REMOTE_VER%"
    )
    call :ui_arrow
    echo.

    rem Everything is downloaded to a staging folder first; the install is only touched
    rem when every file arrived, so a dropped connection can never leave a half update.
    set "STAGE=%TEMP%\linkcatty_stage"
    if exist "!STAGE!" rmdir /s /q "!STAGE!" 2>nul
    mkdir "!STAGE!" 2>nul
    set "DL_FAILED=0"

    set "BAR_LABEL=Updating"
    set "BAR_TOTAL=%TOTAL_FILES%"
    for /l %%i in (0,1,13) do (
        set /a BAR_DONE=%%i
        call :ui_bar
        if "!DL_FAILED!"=="0" call :DownloadFile %%i
    )
    set "BAR_DONE=!BAR_TOTAL!"
    call :ui_bar
    echo.
    echo.

    if "!DL_FAILED!"=="1" (
        rmdir /s /q "!STAGE!" 2>nul
        set "MSG=Could not download !FAILED_FILE!"
        set "DET=!DL_ERR!"
        call :ui_warn
        call :ui_note "Nothing was changed. LinkCatty will try again next time you start it."
        echo.
        ping -n 4 127.0.0.1 >nul
        goto :AfterUpdate
    )

    xcopy "!STAGE!\*" "%~dp0" /E /Y /Q >nul
    rmdir /s /q "!STAGE!" 2>nul

    rem The version file is written WITHOUT a BOM
    powershell -NoProfile -Command "& { [System.IO.File]::WriteAllText('%~dp0sources\version.txt', '%REMOTE_VER%', [System.Text.UTF8Encoding]::new($false)) }" >nul 2>&1

    rem Deps are re-checked after an update
    del "%~dp0sources\.deps_installed" 2>nul

    set "MSG=Updated to %REMOTE_VER%"
    set "DET=restarting"
    call :ui_ok

    rem Update the launcher itself (installed name is linkcatty.bat, repo name is run.cmd).
    rem Download to temp, force CRLF + ASCII, validate, then copy over the running file.
    rem Nothing after this copy may call a label: cmd reads the new file from here on.
    set "LAUNCHER_NEW=%TEMP%\linkcatty_launcher.new"
    del "!LAUNCHER_NEW!" 2>nul
    powershell -NoProfile -Command "& { $ProgressPreference='SilentlyContinue'; try { $t = (Invoke-WebRequest -UseBasicParsing -Uri '%RAW_BASE%/run.cmd').Content; if ($t -is [byte[]]) { $t = [Text.Encoding]::ASCII.GetString($t) }; if ($t -match 'LinkCatty Launcher') { [IO.File]::WriteAllText('!LAUNCHER_NEW!', ($t -replace '\r?\n', ([string][char]13 + [char]10)), [Text.Encoding]::ASCII) } } catch {} }" >nul 2>&1
    findstr /c:"LinkCatty Launcher" "!LAUNCHER_NEW!" >nul 2>&1
    if not errorlevel 1 copy /y "!LAUNCHER_NEW!" "%~f0" >nul
    del "!LAUNCHER_NEW!" 2>nul
    if /i not "%~nx0"=="run.cmd" del "%~dp0run.cmd" 2>nul

    ping -n 2 127.0.0.1 >nul
    rem one line: nothing is re-read from the (replaced) file after the restart returns
    call "%~f0" --restarted & exit /b !errorlevel!
)

:AfterUpdate

rem ---- 2. Python -------------------------------------------------------
set "PORTABLE_DIR=%~dp0sources\portable_python"
set "PYTHON_EXE="
set "PYTHON_SCRIPTS="
set "PY_KIND=system"
set "DEPS_MARKER=%~dp0sources\.deps_installed"

if exist "%PORTABLE_DIR%\python.exe" (
    set "PYTHON_EXE=%PORTABLE_DIR%\python.exe"
    set "PYTHON_SCRIPTS=%PORTABLE_DIR%\Scripts"
    set "PY_KIND=portable"
    goto :PythonFound
)
if exist "%PORTABLE_DIR%\Scripts\python.exe" (
    set "PYTHON_EXE=%PORTABLE_DIR%\Scripts\python.exe"
    set "PYTHON_SCRIPTS=%PORTABLE_DIR%\Scripts"
    set "PY_KIND=portable"
    goto :PythonFound
)

rem Extract the portable Python if the zip is present
if exist "%~dp0sources\PortablePython.zip" (
    set "MSG=Preparing Python"
    set "DET=first run only"
    call :ui_arrow
    if not exist "%PORTABLE_DIR%" mkdir "%PORTABLE_DIR%"
    powershell -NoProfile -Command "& { Add-Type -AssemblyName System.IO.Compression.FileSystem; [System.IO.Compression.ZipFile]::ExtractToDirectory('%~dp0sources\PortablePython.zip', '%PORTABLE_DIR%') }" >nul 2>&1
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
    if exist "%PORTABLE_DIR%\python.exe" (
        set "PYTHON_EXE=%PORTABLE_DIR%\python.exe"
        set "PYTHON_SCRIPTS=%PORTABLE_DIR%\Scripts"
        set "PY_KIND=portable"
        del "%DEPS_MARKER%" 2>nul
        goto :PythonFound
    )
    if exist "%PORTABLE_DIR%\Scripts\python.exe" (
        set "PYTHON_EXE=%PORTABLE_DIR%\Scripts\python.exe"
        set "PYTHON_SCRIPTS=%PORTABLE_DIR%\Scripts"
        set "PY_KIND=portable"
        del "%DEPS_MARKER%" 2>nul
        goto :PythonFound
    )
)

rem Fall back to system Python
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
    set "MSG=Python was not found"
    set "DET="
    call :ui_fail
    call :ui_note "Install Python from https://www.python.org/downloads/"
    call :ui_note "and tick 'Add Python to PATH' during setup."
    echo.
    pause
    exit /b 1
)

for /f "usebackq delims=" %%s in (`%PYTHON_EXE% -c "import sysconfig; print(sysconfig.get_path('scripts'))" 2^>nul`) do (
    set "PYTHON_SCRIPTS=%%s"
)

:PythonFound
set "MSG=Python ready"
set "DET=%PY_KIND%"
call :ui_ok

if defined PYTHON_SCRIPTS (
    if exist "!PYTHON_SCRIPTS!" (
        set "PATH=!PYTHON_SCRIPTS!;%PATH%"
    )
)

rem FFmpeg
set "FFMPEG_DIR=%~dp0sources\FFmpeg\windows\ffmpeg\bin"
if exist "%FFMPEG_DIR%\ffmpeg.exe" (
    set "PATH=%FFMPEG_DIR%;%PATH%"
) else (
    set "MSG=FFmpeg not found"
    set "DET=video merging may not work"
    call :ui_warn
)

rem ---- 3. dependencies -------------------------------------------------
if exist "%DEPS_MARKER%" (
    set "MSG=Dependencies ready"
    set "DET="
    call :ui_ok
) else (
    set "MSG=Installing packages"
    set "DET=first run only, one moment"
    call :ui_arrow
    "%PYTHON_EXE%" -m pip --version >nul 2>&1
    if errorlevel 1 "%PYTHON_EXE%" -m ensurepip --upgrade >nul 2>&1
    "%PYTHON_EXE%" -m pip install --quiet --upgrade pip --no-warn-script-location >nul 2>&1
    "%PYTHON_EXE%" -m pip install --quiet --upgrade yt-dlp spotipy spotdl --no-warn-script-location --no-cache-dir
    if errorlevel 1 (
        set "MSG=Could not install the packages"
        set "DET="
        call :ui_fail
        call :ui_note "Check your internet connection and start LinkCatty again."
        echo.
        pause
        exit /b 1
    )
    echo %REMOTE_VER%> "%DEPS_MARKER%"
    set "MSG=Dependencies ready"
    set "DET="
    call :ui_ok
)

"%PYTHON_EXE%" "%~dp0sources\LinkCatty.py"
set EXIT_CODE=%errorlevel%
if %EXIT_CODE% neq 0 (
    echo.
    set "MSG=LinkCatty stopped unexpectedly"
    set "DET=error code %EXIT_CODE%"
    call :ui_fail
    echo.
    pause
)
exit /b %EXIT_CODE%

rem ======================================================================
rem  Subroutines (only reached through call; the main flow always exits above)
rem ======================================================================

:DoUninstall
rem Every call below is one line ending in "& exit": the uninstaller deletes this very
rem folder, so this file must not be read again afterwards.
if exist "%~dp0uninstall_linkcatty.cmd" call "%~dp0uninstall_linkcatty.cmd" & exit /b 0
if exist "%LOCALAPPDATA%\LinkCatty\uninstall_linkcatty.cmd" call "%LOCALAPPDATA%\LinkCatty\uninstall_linkcatty.cmd" & exit /b 0
echo Uninstaller not found. Downloading...
set "UNINSTALL_FILE=%TEMP%\uninstall_linkcatty.cmd"
powershell -NoProfile -Command "& { $ProgressPreference='SilentlyContinue'; try { $t = (Invoke-WebRequest -UseBasicParsing -Uri 'https://raw.githubusercontent.com/maiz-an/LinkCatty/main/uninstall_linkcatty.cmd').Content; if ($t -is [byte[]]) { $t = [Text.Encoding]::ASCII.GetString($t) }; [IO.File]::WriteAllText('%UNINSTALL_FILE%', ($t -replace '\r?\n', ([string][char]13 + [char]10)), [Text.Encoding]::ASCII) } catch {} }" >nul 2>&1
if exist "%UNINSTALL_FILE%" call "%UNINSTALL_FILE%" & exit /b 0
echo Failed to download the uninstaller.
pause
exit /b 1

:DownloadFile
set "idx=%1"
set "entry=!FILE_LIST[%idx%]!"
for /f "tokens=1,2 delims=|" %%a in ("!entry!") do (
    set "FILE_PATH=%%a"
    set "FILE_URL=%%b"
)
set "FILE_URL=!FILE_URL:/LinkCatty/main/=/LinkCatty/%REF%/!"
set "OUT_FILE=!STAGE!\!FILE_PATH!"
for %%f in ("!OUT_FILE!") do set "OUT_DIR=%%~dpf"
if not exist "!OUT_DIR!" mkdir "!OUT_DIR!" 2>nul
call :FetchFile
if errorlevel 1 (
    set "DL_FAILED=1"
    set "FAILED_FILE=!FILE_PATH!"
)
exit /b

:FetchFile
rem in : FILE_PATH (with backslashes), FILE_URL (raw.githubusercontent.com), OUT_FILE
rem out: errorlevel 0 = ok; DL_ERR = the reason when it failed
set "DL_ERR="
set "FILE_FWD=!FILE_PATH:\=/!"
set "MIRROR_URL="
if not "%REF%"=="main" set "MIRROR_URL=https://cdn.jsdelivr.net/gh/maiz-an/LinkCatty@%REF%/!FILE_FWD!"
set "ERR_FILE=%TEMP%\linkcatty_dl_error.txt"
set "TRY=0"
:FetchTry
set /a TRY+=1
del "!ERR_FILE!" 2>nul
powershell -NoProfile -Command "& { $ProgressPreference = 'SilentlyContinue'; $urls = @('!FILE_URL!', '!MIRROR_URL!') | Where-Object { $_ }; $err = ''; foreach ($u in $urls) { try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 45 -Uri $u -OutFile '!OUT_FILE!'; exit 0 } catch { $err = $_.Exception.Message } }; Set-Content -Path '!ERR_FILE!' -Value $err; exit 1 }" >nul 2>&1
if not errorlevel 1 goto :FetchCheck
if exist "!ERR_FILE!" set /p DL_ERR=<"!ERR_FILE!"
goto :FetchRetry
:FetchCheck
rem A proxy or captive portal can answer 200 with a web page. That must never be installed
rem as a file (it would show up later as a syntax or format error).
findstr /b /i /r /c:"<.doctype" /c:"<html" "!OUT_FILE!" >nul 2>&1
if not errorlevel 1 (
    set "DL_ERR=received a web page instead of the file"
    goto :FetchRetry
)
if /i not "!FILE_PATH!"=="sources\version.txt" goto :FetchCmdCheck
rem The version file must be digits and dots only, and not empty. The next two lines must not
rem contain an exclamation mark: with delayed expansion cmd would treat the caret in the
rem pattern as an escape character even inside quotes.
findstr /r /c:"[^0-9.]" "%OUT_FILE%" >nul 2>&1
if not errorlevel 1 set "DL_ERR=the version file is not valid" & goto :FetchRetry
for %%s in ("%OUT_FILE%") do if %%~zs LSS 3 set "DL_ERR=the version file is empty" & goto :FetchRetry
:FetchCmdCheck
rem .cmd files must be CRLF + ASCII whatever the server sent
if /i "!FILE_PATH:~-4!"==".cmd" powershell -NoProfile -Command "& { $p='!OUT_FILE!'; if (Test-Path $p) { $t=[IO.File]::ReadAllText($p); [IO.File]::WriteAllText($p, ($t -replace '\r?\n', ([string][char]13 + [char]10)), [Text.Encoding]::ASCII) } }" >nul 2>&1
exit /b 0
:FetchRetry
if !TRY! LSS 3 (
    rem wait a little longer each time (a busy server or a scan of the new file usually clears)
    set /a WAIT=TRY*2
    set /a WAIT+=1
    ping -n !WAIT! 127.0.0.1 >nul
    goto :FetchTry
)
if not defined DL_ERR set "DL_ERR=no answer from the server"
exit /b 1

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
)
set "RULE="
for /l %%k in (1,1,58) do set "RULE=!RULE!!G_BAR2!"
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
rem One in-place progress line from BAR_LABEL, BAR_DONE and BAR_TOTAL, same look as the app.
rem It is redrawn with ANSI cursor codes (erase line + go to column 1); the old "carriage
rem return in a variable" trick prints nothing on current Windows builds. Consoles without
rem ANSI only get a final line.
set /a BP=BAR_DONE*100/BAR_TOTAL
set /a BF=BAR_DONE*28/BAR_TOTAL
if not defined ESC goto :ui_bar_plain
set "BB1="
set "BB2="
for /l %%k in (1,1,28) do (
    if %%k leq !BF! (set "BB1=!BB1!!G_BAR1!") else (set "BB2=!BB2!!G_BAR2!")
)
<nul set /p "=%ESC%[2K%ESC%[1G  %C%!BAR_LABEL!%R%  %C%!BB1!%R%%D%!BB2!%R%  %B%!BP!%%%R%  %D%!BAR_DONE!/!BAR_TOTAL!%R%"
exit /b
:ui_bar_plain
if "!BAR_DONE!"=="!BAR_TOTAL!" <nul set /p "=  !BAR_LABEL!  done (!BAR_DONE!/!BAR_TOTAL!)"
exit /b
