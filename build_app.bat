@echo off
:: Change to the folder containing this bat file
cd /d "%~dp0"

title Forza Auto App - Build

:: -- Build mode -------------------------------------------------
:: Dependency handling:
::   (default)  FAST  - install only what's missing. Near-instant when deps are
::                      already present (no PyPI re-check, no re-download).
::   full / upgrade    - re-check & --upgrade every package from PyPI (slow).
::                       Use this for release builds.
:: Set FAFE_NOPAUSE=1 in the environment to skip all pauses (unattended / CI).
set DEPS_MODE=fast
if /i "%~1"=="full"    set DEPS_MODE=full
if /i "%~1"=="upgrade" set DEPS_MODE=full
set PIP_FLAGS=
if /i "%DEPS_MODE%"=="full" set PIP_FLAGS=--upgrade

:: Clean up old build artifacts to avoid permission errors
taskkill /f /im FAFE.exe >nul 2>&1
timeout /t 1 /nobreak >nul
if exist dist rmdir /s /q dist >nul 2>&1
if exist build rmdir /s /q build >nul 2>&1
if exist FAFE.spec del /f /q FAFE.spec >nul 2>&1
if exist FAFE_dist rmdir /s /q FAFE_dist >nul 2>&1

echo.
echo  =====================================================
echo   Full Auto Forza Edition - Building FAFE.exe  (deps: %DEPS_MODE%)
echo  =====================================================
echo.
if not "%FAFE_NOPAUSE%"=="1" pause

:: -- Step 1: Install dependencies ----------------------------
echo.
if /i "%DEPS_MODE%"=="full" (
    echo  [1/2]  Installing / upgrading dependencies ^(full^)...
) else (
    echo  [1/2]  Ensuring dependencies present ^(fast - pass "full" to upgrade^)...
)
echo  -----------------------------------------------------
pip install %PIP_FLAGS% pyinstaller customtkinter Pillow ^
    pydirectinput opencv-python ^
    mss numpy keyboard requests certifi ^
    rapidocr-onnxruntime ^
    pycaw comtypes
if errorlevel 1 (
    echo.
    echo  ERROR: pip failed. Check Python installation.
    echo.
    if not "%FAFE_NOPAUSE%"=="1" pause
    exit /b 1
)

:: -- Step 2: Build FAFE.exe ----------------------------------
echo.
echo  [2/2]  Building FAFE.exe...
echo  -----------------------------------------------------
python -m PyInstaller --onedir --windowed --name FAFE ^
    --icon "%CD%\FAFE_icon.ico" ^
    --add-data "%CD%\FAFE_icon.ico;." ^
    --add-data "%CD%\assets;assets" ^
    --add-data "%CD%\app_lang.py;." ^
    --add-data "%CD%\config.py;." ^
    --add-data "%CD%\capture.py;." ^
    --add-data "%CD%\detector.py;." ^
    --add-data "%CD%\theme.py;." ^
    --add-data "%CD%\race.py;." ^
    --add-data "%CD%\gameio.py;." ^
    --add-data "%CD%\mastery.py;." ^
    --add-data "%CD%\main_window.py;." ^
    --add-data "%CD%\setup_panel.py;." ^
    --add-data "%CD%\grid_widget.py;." ^
    --add-data "%CD%\log_widget.py;." ^
    --add-data "%CD%\version.py;." ^
    --add-data "%CD%\updater.py;." ^
    --add-data "%CD%\delete_cars.py;." ^
    --add-data "%CD%\wheelspin.py;." ^
    --add-data "%CD%\buy.py;." ^
    --add-data "%CD%\full_auto.py;." ^
    --add-data "%CD%\report.py;." ^
    --add-data "%CD%\overlay.py;." ^
    --hidden-import customtkinter ^
    --hidden-import PIL ^
    --hidden-import PIL.Image ^
    --hidden-import PIL.ImageTk ^
    --hidden-import detector ^
    --hidden-import rapidocr_onnxruntime ^
    --hidden-import asyncio ^
    --hidden-import asyncio.base_events ^
    --hidden-import asyncio.events ^
    --hidden-import asyncio.futures ^
    --hidden-import asyncio.tasks ^
    --hidden-import urllib.request ^
    --hidden-import zipfile ^
    --hidden-import certifi ^
    --hidden-import pycaw ^
    --hidden-import comtypes ^
    --collect-all customtkinter ^
    --collect-all rapidocr_onnxruntime ^
    --collect-all certifi ^
    --collect-all comtypes ^
    --collect-submodules pycaw ^
    forza_app.py
if errorlevel 1 (
    echo.
    echo  ERROR: Build failed. See output above.
    echo.
    if not "%FAFE_NOPAUSE%"=="1" pause
    exit /b 1
)

if exist FAFE_dist rmdir /s /q FAFE_dist >nul 2>&1
xcopy /e /i /q dist\FAFE FAFE_dist >nul

:: -- Bundle the template sets (read from BASE_DIR\templates = next to the exe,
::    NOT from _internal, so they must be COPIED here, not --add-data'd) --------
echo  [+]    Bundling templates...
if exist templates xcopy /e /i /q templates "FAFE_dist\templates" >nul

:: -- Step 3: Generate default config.json -------------------
echo  [+]    Writing default config.json...
(
  echo {
  echo   "lang": "en",
  echo   "lang_chosen": false,
  echo   "theme": "system",
  echo   "toggle_key": "f9",
  echo   "capture_key": "caps lock",
  echo   "monitor_index": 1,
  echo   "race_resolution": "built-in",
  echo   "mastery_resolution": "built-in",
  echo   "wheelspin_resolution": "built-in",
  echo   "buy_resolution": "built-in",
  echo   "race_threshold": 0.6,
  echo   "thresh_start_menu": 0.5,
  echo   "thresh_racing": 0.5,
  echo   "thresh_restart_menu": 0.5,
  echo   "thresh_confirm": 0.5,
  echo   "thresh_mastery_ride_car": 0.6,
  echo   "thresh_mastery_esc_hint": 0.6,
  echo   "thresh_mastery_upgrade_item": 0.5,
  echo   "thresh_mastery_mastery_item": 0.6,
  echo   "thresh_mastery_anchor": 0.6,
  echo   "thresh_mastery_my_cars": 0.6,
  echo   "thresh_mastery_sort_recent": 0.6,
  echo   "race_check_interval": 0.5,
  echo   "race_post_key_wait": 0.75,
  echo   "mastery_threshold": 0.85,
  echo   "mastery_check_interval": 0.5,
  echo   "mastery_start_loop": 1,
  echo   "mastery_post_click_wait": 0.8,
  echo   "mastery_post_key_wait": 1.2,
  echo   "mastery_node_click_wait": 0.8,
  echo   "buy_post_key_wait": 0.5,
  echo   "delete_post_key_wait": 0.5
  echo }
) > FAFE_dist\config.json

echo.
echo  =====================================================
echo   BUILD COMPLETE
echo  =====================================================
echo.
echo  FAFE.exe is ready in FAFE_dist\.
echo.
echo  Templates will be saved to a 'templates' subfolder
echo  next to the exe automatically.
echo.
echo  You can delete 'dist', 'build', and FAFE.spec.
echo.
if not "%FAFE_NOPAUSE%"=="1" pause
