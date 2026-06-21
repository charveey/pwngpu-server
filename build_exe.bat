@echo off
REM Builds a standalone PwnGPUCrackServer.exe so the end user doesn't need
REM Python installed at all.

python -m pip install -r requirements.txt
python -m pip install pyinstaller

pyinstaller --noconfirm --onefile --windowed --name "PwnGPUCrackServer" main.py

echo.
echo Build complete: dist\PwnGPUCrackServer.exe
echo You can copy this single exe to any Windows machine.
pause
