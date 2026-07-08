# One-command build: produces dist\DragonwildsSync.exe
# Usage:  .\build.ps1

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment..."
    python -m venv .venv
    .\.venv\Scripts\pip.exe install -r requirements.txt -r requirements-dev.txt
}

Write-Host "Running tests..."
.\.venv\Scripts\python.exe -m pytest tests -q
if ($LASTEXITCODE -ne 0) { throw "Tests failed - not building." }

Write-Host "Regenerating icon..."
.\.venv\Scripts\python.exe tools\generate_icon.py

Write-Host "Building DragonwildsSync.exe..."
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm DragonwildsSync.spec

Write-Host ""
Write-Host "Done -> dist\DragonwildsSync.exe"
Write-Host "(Optional: compile installer.iss with Inno Setup for a setup wizard.)"
