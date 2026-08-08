@echo off
rem ============================================================
rem  RwG PAA Convert - Starter
rem  Sucht eine Python-Installation und startet die GUI.
rem ============================================================
setlocal
cd /d "%~dp0"

rem Bevorzugt den Python-Launcher "py", sonst "python", sonst "python3"
where py >nul 2>&1 && (
    start "" pyw "%~dp0RwG_Paa_Convert.py"
    goto :eof
)
where pythonw >nul 2>&1 && (
    start "" pythonw "%~dp0RwG_Paa_Convert.py"
    goto :eof
)
where python >nul 2>&1 && (
    start "" python "%~dp0RwG_Paa_Convert.py"
    goto :eof
)
echo Python wurde nicht gefunden.
echo Bitte Python 3 installieren: https://www.python.org/downloads/
echo (Beim Setup "Add python.exe to PATH" aktivieren.)
pause
