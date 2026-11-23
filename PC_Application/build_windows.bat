@echo off
setlocal
cd /d "%~dp0"
py -3 -m pip install -r requirements.txt pyinstaller
if errorlevel 1 exit /b 1
py -3 -m PyInstaller --noconfirm --clean --windowed --name RS-Deck --collect-all PySide6 main.py
if errorlevel 1 exit /b 1
echo.
echo Built executable: dist\RS-Deck\RS-Deck.exe
pause
