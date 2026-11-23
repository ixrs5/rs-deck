@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 goto USE_PY_LAUNCHER
where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found. Install Python 3.11 or later and enable Add Python to PATH.
  pause
  exit /b 1
)
python -m pip install -r requirements.txt
if errorlevel 1 goto INSTALL_FAILED
python main.py
if errorlevel 1 pause
goto END

:USE_PY_LAUNCHER
py -3 -m pip install -r requirements.txt
if errorlevel 1 goto INSTALL_FAILED
py -3 main.py
if errorlevel 1 pause
goto END

:INSTALL_FAILED
echo Dependency installation failed. Check your internet connection and Python installation.
pause
:END
endlocal
