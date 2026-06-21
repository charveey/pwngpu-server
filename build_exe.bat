@echo off
setlocal

python -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo Failed to install requirements. See errors above.
    pause
    exit /b 1
)

python -m pip install pyinstaller
if errorlevel 1 (
    echo.
    echo Failed to install PyInstaller. See errors above.
    pause
    exit /b 1
)

REM Call PyInstaller as a module rather than a bare command - this works
REM even if its Scripts folder isn't on PATH (common with the Microsoft
REM Store build of Python).
python -m PyInstaller --noconfirm --onefile --windowed --name "PwnGPUServer" main.py
if errorlevel 1 (
    echo.
    echo Build FAILED - see errors above.
    pause
    exit /b 1
)

echo.
echo Build complete: dist\PwnGPUServer.exe
echo You can copy this single exe to any Windows machine.
pause
