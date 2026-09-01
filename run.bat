@echo off
cd /d "%~dp0"
where pythonw >nul 2>nul
if %errorlevel% equ 0 (
    start "" pythonw "%~dp0app.py"
) else if exist "%LocalAppData%\Python\bin\pythonw.exe" (
    start "" "%LocalAppData%\Python\bin\pythonw.exe" "%~dp0app.py"
) else if exist "%LocalAppData%\Python\bin\python.exe" (
    start "" "%LocalAppData%\Python\bin\python.exe" "%~dp0app.py"
) else (
    py -3 "%~dp0app.py"
    if errorlevel 1 pause
)
