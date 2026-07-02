@echo off
cd /d "%~dp0"

set FAFE_BUILD_KIND=teaser
set FAFE_FULLAUTO=0

title Full Auto Forza Edition - Build (%FAFE_BUILD_KIND%, web UI)

rem ============================================================
rem  Builds the PyWebView app (app_web.py) into FAFE_dist\FAFE.exe.
rem  - bundles webui\ (HTML/CSS/JS UI) and assets\ into the build
rem  - templates\ are COPIED next to the exe (read from BASE_DIR, not _internal)
rem  Public teaser/free build. Paid modules are intentionally omitted.
rem
rem  PREREQUISITE on the target machine: the Microsoft Edge WebView2 Runtime
rem  (present by default on Windows 11; Windows 10 may need the Evergreen
rem  bootstrapper). PyWebView uses the system runtime - it isn't bundled here.
rem ============================================================

set DEPS_MODE=fast
if /i "%~1"=="full"    set DEPS_MODE=full
if /i "%~1"=="upgrade" set DEPS_MODE=full
set PIP_FLAGS=
if /i "%DEPS_MODE%"=="full" set PIP_FLAGS=--upgrade

rem full_auto (the PAID feature) is OMITTED by default 鈫?safe public/teaser build
rem (defense-by-absence: the .pyd simply isn't shipped, so no env-var/JS bypass can
rem run it). license_client is also omitted in the default teaser build.
rem build_app_paid.bat sets FAFE_FULLAUTO=1 for the private paid build.
set FA_ADD=
set LIC_ADD=
if /i "%FAFE_FULLAUTO%"=="1" set FA_ADD=--add-binary "%CD%\compiled\full_auto.pyd;."
if /i "%FAFE_FULLAUTO%"=="1" set LIC_ADD=--add-binary "%CD%\compiled\license_client.pyd;."

rem Clean old artifacts
taskkill /f /im FAFE.exe >nul 2>&1
ping 127.0.0.1 -n 2 >nul
if exist dist rmdir /s /q dist >nul 2>&1
if exist build rmdir /s /q build >nul 2>&1
if exist FAFE.spec del /f /q FAFE.spec >nul 2>&1
if exist FAFE_dist rmdir /s /q FAFE_dist >nul 2>&1
if exist compiled rmdir /s /q compiled >nul 2>&1

echo.
echo  =====================================================
echo   Full Auto Forza Edition - Building FAFE.exe  (%FAFE_BUILD_KIND%, deps: %DEPS_MODE%)
echo  =====================================================
echo.
if not "%FAFE_NOPAUSE%"=="1" pause

rem -- Step 1: dependencies ------------------------------------
echo.
echo  [1/3]  Ensuring dependencies present (pass "full" to upgrade)...
echo  -----------------------------------------------------
pip install %PIP_FLAGS% pyinstaller nuitka ^
    pywebview pythonnet ^
    opencv-python mss numpy keyboard certifi ^
    rapidocr-onnxruntime ^
    pycaw comtypes
if errorlevel 1 (
    echo  ERROR: pip failed. Check Python installation.
    if not "%FAFE_NOPAUSE%"=="1" pause
    exit /b 1
)

rem -- Step 2: compile the paid modules to native .pyd ----------
rem Nuitka MODULE mode (only these two files). The teaser build skips this step
rem entirely so paid/private code is not shipped.
echo.
echo  [2/3]  Compiling protected modules...
echo  -----------------------------------------------------
if /i not "%FAFE_FULLAUTO%"=="1" (
    echo  Teaser build: full_auto and license_client NOT bundled.
    goto after_fa_compile
)
python -m nuitka --module license_client.py --output-dir=compiled --msvc=latest --assume-yes-for-downloads --remove-output --disable-cache=ccache
if errorlevel 1 ( echo  ERROR: Nuitka license_client failed. & if not "%FAFE_NOPAUSE%"=="1" pause & exit /b 1 )
for %%F in ("compiled\license_client.*.pyd")  do move /y "%%F" "compiled\license_client.pyd" >nul
if not exist "compiled\license_client.pyd" ( echo  ERROR: license_client.pyd not produced. & if not "%FAFE_NOPAUSE%"=="1" pause & exit /b 1 )

rem full_auto only in the private (paid) build 鈥?FAFE_FULLAUTO=1
if /i not "%FAFE_FULLAUTO%"=="1" echo  Teaser build: full_auto (paid feature) NOT bundled.
if /i not "%FAFE_FULLAUTO%"=="1" goto after_fa_compile
python -m nuitka --module full_auto.py --output-dir=compiled --msvc=latest --assume-yes-for-downloads --remove-output --disable-cache=ccache
if errorlevel 1 ( echo  ERROR: Nuitka full_auto failed. & if not "%FAFE_NOPAUSE%"=="1" pause & exit /b 1 )
for %%F in ("compiled\full_auto.*.pyd")      do move /y "%%F" "compiled\full_auto.pyd" >nul
if not exist "compiled\full_auto.pyd" ( echo  ERROR: full_auto.pyd not produced. & if not "%FAFE_NOPAUSE%"=="1" pause & exit /b 1 )
:after_fa_compile

rem -- Step 3: build FAFE.exe ----------------------------------
echo.
echo  [3/3]  Building FAFE.exe (PyWebView)...
echo  -----------------------------------------------------
python -m PyInstaller --onedir --windowed --name FAFE ^
    --icon "%CD%\FAFE_icon.ico" ^
    --add-data "%CD%\FAFE_icon.ico;." ^
    --add-data "%CD%\webui;webui" ^
    --add-data "%CD%\assets;assets" ^
    --exclude-module full_auto ^
    --exclude-module license_client ^
    %FA_ADD% ^
    %LIC_ADD% ^
    --collect-all webview ^
    --collect-all clr_loader ^
    --hidden-import clr ^
    --hidden-import detector ^
    --hidden-import rapidocr_onnxruntime ^
    --hidden-import certifi ^
    --hidden-import pycaw ^
    --hidden-import comtypes ^
    --collect-all rapidocr_onnxruntime ^
    --collect-all certifi ^
    --collect-all comtypes ^
    --collect-submodules pycaw ^
    app_web.py
if errorlevel 1 (
    echo  ERROR: Build failed. See output above.
    if not "%FAFE_NOPAUSE%"=="1" pause
    exit /b 1
)

if exist FAFE_dist rmdir /s /q FAFE_dist >nul 2>&1
xcopy /e /i /q dist\FAFE FAFE_dist >nul

rem OCR runs on CPU; PyInstaller may still collect huge CUDA provider DLLs
rem through onnxruntime. Strip that GPU-only bloat from both output folders.
echo  [+]    Removing unused CUDA OCR DLLs...
del /f /q "FAFE_dist\_internal\cublasLt64_13.dll" 2>nul
del /f /q "FAFE_dist\_internal\cublas64_13.dll" 2>nul
del /f /q "FAFE_dist\_internal\cufft64_12.dll" 2>nul
del /f /q "FAFE_dist\_internal\onnxruntime\capi\onnxruntime_providers_cuda.dll" 2>nul
del /f /q "FAFE_dist\_internal\onnxruntime\capi\onnxruntime_providers_tensorrt.dll" 2>nul
del /f /q "dist\FAFE\_internal\cublasLt64_13.dll" 2>nul
del /f /q "dist\FAFE\_internal\cublas64_13.dll" 2>nul
del /f /q "dist\FAFE\_internal\cufft64_12.dll" 2>nul
del /f /q "dist\FAFE\_internal\onnxruntime\capi\onnxruntime_providers_cuda.dll" 2>nul
del /f /q "dist\FAFE\_internal\onnxruntime\capi\onnxruntime_providers_tensorrt.dll" 2>nul

rem Template sets are read from BASE_DIR\templates (next to the exe), so COPY them.
echo  [+]    Bundling templates...
if exist templates xcopy /e /i /q templates "FAFE_dist\templates" >nul

rem Teaser build: strip the Full Auto template images (paid feature) so the FREE
rem download doesn't ship them. The paid build (FAFE_FULLAUTO=1) keeps them.
if /i not "%FAFE_FULLAUTO%"=="1" echo  [+]    Teaser build: removing Full Auto templates...
if /i not "%FAFE_FULLAUTO%"=="1" for /d %%D in ("FAFE_dist\templates\*") do if exist "%%D\full_auto" rmdir /s /q "%%D\full_auto"

rem Bundle the Edge WebView2 Evergreen bootstrapper if present, so Win10 PCs
rem without the runtime can install it on first launch (app_web._ensure_webview2
rem searches _internal via _res_dir/_MEIPASS).
if exist MicrosoftEdgeWebview2Setup.exe copy /y MicrosoftEdgeWebview2Setup.exe "FAFE_dist\_internal\" >nul

rem No config.json is written here - config.py self-completes a full default
rem config.json from DEFAULTS on first launch (avoids shipping stale keys).

rem -- Step 4: build the installer (Inno Setup) ----------------
rem An installer avoids the "Mark of the Web" DLL block (a downloaded ZIP flags
rem its DLLs; .NET refuses to load them). Installer-written files don't inherit
rem MOTW. Skipped gracefully if Inno Setup (ISCC.exe) isn't installed.
echo.
echo  [4/4]  Building installer (Inno Setup, if present)...
echo  -----------------------------------------------------
set ISCC=
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe
if defined ISCC goto build_installer
echo  ERROR: Inno Setup not found. Install from https://jrsoftware.org/isdl.php
echo  and re-run to produce Output\FAFE_Setup.exe.
if not "%FAFE_NOPAUSE%"=="1" pause
exit /b 1

:build_installer
if exist Output\FAFE_Setup.exe del /f /q Output\FAFE_Setup.exe >nul 2>&1
if exist Output\FAFE_Setup.exe (
    echo  ERROR: Output\FAFE_Setup.exe is locked or in use. Close it and re-run.
    if not "%FAFE_NOPAUSE%"=="1" pause
    exit /b 1
)
"%ISCC%" build_installer.iss
if errorlevel 1 (
    echo  ERROR: installer build failed. See output above.
    if not "%FAFE_NOPAUSE%"=="1" pause
    exit /b 1
)
if not exist Output\FAFE_Setup.exe (
    echo  ERROR: installer build finished but Output\FAFE_Setup.exe is missing.
    if not "%FAFE_NOPAUSE%"=="1" pause
    exit /b 1
)
for %%F in ("Output\FAFE_Setup.exe") do if %%~zF LSS 10000000 (
    echo  ERROR: installer output is too small. Expected bundled app payload.
    if not "%FAFE_NOPAUSE%"=="1" pause
    exit /b 1
)
echo  [+]    Installer written to Output\

echo.
echo  =====================================================
echo   BUILD COMPLETE  -  FAFE.exe is in FAFE_dist\
echo  =====================================================
echo.
echo  Note: requires the Edge WebView2 Runtime on the target PC (default on Win11).
echo  You can delete 'dist', 'build', 'compiled', and FAFE.spec.
echo.
if not "%FAFE_NOPAUSE%"=="1" pause
