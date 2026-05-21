#!/usr/bin/env pwsh
# Job Copilot -- Chrome extension dev server (hot reload)
# Run this in a second terminal alongside start.ps1

$Root      = $PSScriptRoot
$Extension = Join-Path $Root "apps\extension"

Push-Location $Extension

Write-Host "`n==> Installing extension dependencies" -ForegroundColor Cyan
npm install --ignore-scripts --silent

# On Windows, sharp's native binary is not installed when --ignore-scripts is used.
# Install the pre-built Windows binary explicitly so Plasmo's file watcher works.
Write-Host "`n==> Installing Windows native binaries (sharp)" -ForegroundColor Cyan
npm install --platform=win32 --arch=x64 sharp --silent

Write-Host "`n==> Starting Plasmo dev server" -ForegroundColor Cyan
Write-Host "    Output folder: apps\extension\build\chrome-mv3-dev" -ForegroundColor Yellow
Write-Host "    Chrome: Extensions > Developer mode > Load unpacked > select that folder" -ForegroundColor Yellow
Write-Host ""

npm run dev
Pop-Location
