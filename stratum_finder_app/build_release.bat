@echo off
chcp 65001 >nul
echo ============================================================
echo  Stratum Finder - RELEASE build (no dev mode)
echo ============================================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python not found in PATH
    echo Install Python 3.10+ from https://www.python.org/
    echo Check "Add Python to PATH" during install
    pause
    exit /b 1
)

echo [1/5] Installing dependencies...
python -m pip install -r requirements.txt

echo [2/5] Cleaning old builds...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist StratumFinder.spec del StratumFinder.spec

echo [3/5] Temporarily removing dev_window.py...
if exist gui\dev_window.py (
    ren gui\dev_window.py dev_window.py.bak
)

echo [4/5] Building EXE (release)...
python -m PyInstaller --name "StratumFinder" --onefile --windowed --noupx --icon "icon.ico" --version-file version_info.txt --manifest app.manifest --add-data "icon.ico;." --add-data "+data;+data" --hidden-import "tkinter" --hidden-import "tkinter.ttk" --hidden-import "tkinter.filedialog" --hidden-import "tkinter.messagebox" --collect-all "certifi" --noconfirm app.py

set BUILD_ERR=%errorlevel%

echo [5/5] Restoring dev_window.py...
if exist gui\dev_window.py.bak (
    ren gui\dev_window.py.bak dev_window.py
)

if %BUILD_ERR% neq 0 (
    echo [ERROR] Build failed
    pause
    exit /b 1
)

echo Copying +data...
if exist "dist\+data" rmdir /s /q "dist\+data"
xcopy /e /i /q "+data" "dist\+data"

echo.
echo ============================================================
echo  DONE: dist\StratumFinder.exe  (dev mode DISABLED)
echo ============================================================
pause
