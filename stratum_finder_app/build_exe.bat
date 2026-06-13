@echo off
chcp 65001 >nul
echo ============================================================
echo  Stratum Finder - DEV build (with developer mode)
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

echo [1/4] Installing dependencies...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Could not install dependencies
    pause
    exit /b 1
)

echo [2/4] Cleaning old builds...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist StratumFinder-dev.spec del StratumFinder-dev.spec

echo [3/4] Building EXE (with dev mode)...
python -m PyInstaller --name "StratumFinder-dev" --onefile --windowed --noupx --icon "icon.ico" --version-file version_info.txt --manifest app.manifest --add-data "icon.ico;." --add-data "+data;+data" --hidden-import "tkinter" --hidden-import "tkinter.ttk" --hidden-import "tkinter.filedialog" --hidden-import "tkinter.messagebox" --hidden-import "gui.dev_window" --collect-all "certifi" --noconfirm app.py

if errorlevel 1 (
    echo [ERROR] Build failed
    pause
    exit /b 1
)

echo [4/4] Copying +data...
if exist "dist\+data" rmdir /s /q "dist\+data"
xcopy /e /i /q "+data" "dist\+data"

echo.
echo ============================================================
echo  DONE: dist\StratumFinder-dev.exe  (dev mode ON, Ctrl+Shift+D)
echo  For release without dev mode use build_release.bat
echo ============================================================
pause
