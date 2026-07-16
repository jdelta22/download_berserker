@echo off
REM Build a standalone Windows executable.
REM Run this on a Windows machine (or Windows CI runner) with the venv activated
REM and dependencies from requirements.txt already installed.

pyinstaller --noconfirm --onefile --windowed ^
  --name "MangaDownloader" ^
  --collect-data customtkinter ^
  --collect-all playwright ^
  --add-data "assets;assets" ^
  app.py

echo.
echo Build finished: dist\MangaDownloader.exe
echo Remember: the target machine still needs "playwright install chromium" run once.