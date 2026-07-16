#!/usr/bin/env bash
# Build a standalone macOS app bundle.
# Run this on a Mac (or macOS CI runner) with the venv activated
# and dependencies from requirements.txt already installed.
set -e

pyinstaller --noconfirm --onefile --windowed \
  --name "MangaDownloader" \
  --collect-data customtkinter \
  --collect-all playwright \
  --add-data "assets:assets" \
  app.py

echo ""
echo "Build finished: dist/MangaDownloader.app (or dist/MangaDownloader)"
echo "Note: unsigned builds will show a Gatekeeper warning on other Macs"
echo "('unidentified developer') unless you codesign + notarize it."
echo "Remember: the target machine still needs 'playwright install chromium' run once."