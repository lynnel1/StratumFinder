@echo off
chcp 65001 >nul
echo ============================================================
echo  Stratum Finder - CLEAN build (fewest antivirus false flags)
echo ============================================================
echo.
echo  This build is optimized to look like a normal, legitimate app:
echo   - folder mode (--onedir) - fewer detections than single-file
echo   - application icon (icon.ico)
echo   - Windows manifest (asInvoker, no admin rights requested)
echo   - version metadata (version_info.txt)
echo   - no UPX compression
echo.
echo  We do NOT hide from antivirus - we make the app properly
echo  formatted so heuristics have no reason to flag it.
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python not found in PATH
    pause
    exit /b 1
)

echo [1/4] Installing dependencies...
python -m pip install -r requirements.txt

echo [2/4] Cleaning...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist StratumFinder.spec del StratumFinder.spec

echo [3/4] Building (clean, signed-ready)...
python -m PyInstaller --name "StratumFinder" --onedir --windowed --noupx --icon "icon.ico" --version-file version_info.txt --manifest app.manifest --add-data "+data;+data" --add-data "icon.ico;." --hidden-import "tkinter" --hidden-import "tkinter.ttk" --hidden-import "tkinter.filedialog" --hidden-import "tkinter.messagebox" --collect-all "certifi" --noconfirm app.py

if errorlevel 1 (
    echo [ERROR] Build failed
    pause
    exit /b 1
)

echo [4/4] Copying +data next to EXE...
if exist "dist\StratumFinder\+data" rmdir /s /q "dist\StratumFinder\+data"
xcopy /e /i /q "+data" "dist\StratumFinder\+data"

echo.
echo ============================================================
echo  DONE: dist\StratumFinder\StratumFinder.exe
echo  Distribute the WHOLE dist\StratumFinder\ folder.
echo ============================================================
echo.
echo  NEXT STEPS to reduce detections further (see BUILD_ANTIVIRUS.md):
echo   1. Rebuild PyInstaller bootloader from source
echo   2. Upload EXE to virustotal.com to check
echo   3. Submit to vendors using texts in WHITELIST_SUBMISSIONS.md
pause
