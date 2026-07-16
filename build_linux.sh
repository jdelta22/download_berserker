#!/usr/bin/env bash
# Build a standalone Linux executable.
# Run this on Linux (or an ubuntu-latest CI runner) with the venv activated
# and dependencies from requirements.txt already installed.
set -e

pyinstaller --noconfirm --onefile --windowed \
  --name "MangaDownloader" \
  --collect-data customtkinter \
  --collect-all playwright \
  --add-data "assets:assets" \
  app.py

echo ""
echo "Build finished: dist/MangaDownloader"
echo "Remember: the target machine still needs 'playwright install chromium --with-deps' run once."