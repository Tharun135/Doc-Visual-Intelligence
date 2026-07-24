$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-desktop.txt
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean .\desktop\DocVisualAdvisor.spec

Write-Host "Build complete. Output: .\dist\DocVisualAdvisor\DocVisualAdvisor.exe"
