#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

python3 -m pip install --upgrade pip
python3 -m pip install -r requirements-desktop.txt
python3 -m PyInstaller --noconfirm --clean ./desktop/DocVisualAdvisor.spec

echo "Build complete. Output: ./dist/DocVisualAdvisor"
