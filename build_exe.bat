@echo off
rem ============================================================
rem  Baut die portable RwG_Paa_Convert.exe mit PyInstaller.
rem  Ergebnis: dist\RwG_Paa_Convert.exe
rem ============================================================
cd /d "%~dp0"

where python >nul 2>&1 || (
    echo Python wurde nicht gefunden. Bitte Python 3 installieren.
    pause
    exit /b 1
)

python -m pip install --upgrade pyinstaller || (
    echo PyInstaller-Installation fehlgeschlagen.
    pause
    exit /b 1
)

python -m PyInstaller --noconfirm --onefile --windowed --name RwG_Paa_Convert ^
  --icon RwG_Logo.ico ^
  --add-data "Stringtable.csv;." ^
  --add-data "RwG_Logo.ico;." ^
  RwG_Paa_Convert.py

echo.
echo Fertig: dist\RwG_Paa_Convert.exe
pause
