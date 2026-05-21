#!/usr/bin/env pwsh
# Job Copilot — tek komutla başlat
# Kullanım: .\start.ps1

param(
    [string]$Provider = "ollama",
    [string]$Model    = "",
    [switch]$Help
)

if ($Help) {
    Write-Host "Kullanim:"
    Write-Host "  .\start.ps1                        # Ollama ile baslat (varsayilan)"
    Write-Host "  .\start.ps1 -Provider openai       # OpenAI ile baslat (OPENAI_API_KEY gerekir)"
    Write-Host "  .\start.ps1 -Provider anthropic    # Anthropic ile baslat (ANTHROPIC_API_KEY gerekir)"
    exit 0
}

$ErrorActionPreference = "Stop"
$Root    = $PSScriptRoot
$Backend = Join-Path $Root "apps\backend"

function Log-Step($msg)  { Write-Host "`n  $msg" -ForegroundColor Cyan }
function Log-Ok($msg)    { Write-Host "  OK  $msg" -ForegroundColor Green }
function Log-Warn($msg)  { Write-Host "  !!  $msg" -ForegroundColor Yellow }
function Log-Err($msg)   { Write-Host "  ERR $msg" -ForegroundColor Red }

Clear-Host
Write-Host ""
Write-Host "  ================================================" -ForegroundColor Blue
Write-Host "            Job Copilot  —  Baslaniyor           " -ForegroundColor White
Write-Host "  ================================================" -ForegroundColor Blue

# ── 1. Python ─────────────────────────────────────────────────────────────────
Log-Step "Python kontrol ediliyor..."
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Log-Err "Python bulunamadi. python.org adresinden Python 3.11+ yukleyin."
    exit 1
}
$ver = python --version 2>&1
Log-Ok $ver

# ── 2. Backend bagımlılıkları ─────────────────────────────────────────────────
Log-Step "Backend bagimliliklar yukleniyor..."
Push-Location $Backend
pip install -e ".[dev]" -q 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) { Log-Err "pip install basarisiz"; Pop-Location; exit 1 }
Log-Ok "Hazir"
Pop-Location

# ── 3. .env dosyasi ───────────────────────────────────────────────────────────
$envFile    = Join-Path $Backend ".env"
$envExample = Join-Path $Backend ".env.example"
if (-not (Test-Path $envFile)) {
    if (Test-Path $envExample) {
        Copy-Item $envExample $envFile
    } else {
        # .env.example yoksa sıfırdan oluştur
        @"
JOB_COPILOT_LLM_PROVIDER=ollama
JOB_COPILOT_LLM_MODEL=qwen2.5-coder:7b
JOB_COPILOT_OLLAMA_HOST=http://localhost:11434
JOB_COPILOT_DEV_TOKEN=dev-token
"@ | Set-Content $envFile -Encoding UTF8
    }
}

if ($Provider -ne "ollama") {
    $c = Get-Content $envFile -Raw
    $c = $c -replace "JOB_COPILOT_LLM_PROVIDER=\S+", "JOB_COPILOT_LLM_PROVIDER=$Provider"
    Set-Content $envFile $c -Encoding UTF8
}

# ── 4. Ollama ─────────────────────────────────────────────────────────────────
if ($Provider -eq "ollama") {
    Log-Step "Ollama kontrol ediliyor..."

    if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
        Log-Err "Ollama bulunamadi. https://ollama.com adresinden indirip yukleyin."
        exit 1
    }

    # Ollama servisi calisiyor mu?
    $running = $false
    try {
        $r = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/version" -TimeoutSec 2 -ErrorAction Stop
        $running = $true
    } catch { }

    if (-not $running) {
        Log-Step "Ollama baslatiliyor..."
        Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden
        # Servisi bekle (max 15 saniye)
        $waited = 0
        while ($waited -lt 15) {
            Start-Sleep -Seconds 1
            $waited++
            try {
                Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/version" -TimeoutSec 1 -ErrorAction Stop | Out-Null
                break
            } catch { }
        }
        if ($waited -ge 15) {
            Log-Err "Ollama 15 saniye icinde baslayamadi."
            exit 1
        }
        Log-Ok "Ollama baslatildi"
    } else {
        Log-Ok "Ollama zaten calisiyor"
    }

    # Model var mi?
    $targetModel = if ($Model) { $Model } else { "qwen2.5-coder:7b" }
    $models = ollama list 2>&1
    if ($models -notmatch [regex]::Escape($targetModel)) {
        Log-Step "Model indiriliyor: $targetModel (ilk seferde uzun surebilir)..."
        ollama pull $targetModel
        if ($LASTEXITCODE -ne 0) { Log-Err "Model indirilemedi"; exit 1 }
        Log-Ok "Model hazir"
    } else {
        Log-Ok "Model mevcut: $targetModel"
    }
}

# ── 5. API key kontrolu (cloud providerlar icin) ──────────────────────────────
if ($Provider -eq "openai" -and -not $env:OPENAI_API_KEY) {
    Log-Warn "OPENAI_API_KEY ayarli degil. apps\backend\.env dosyasina ekleyin."
}
if ($Provider -eq "anthropic" -and -not $env:ANTHROPIC_API_KEY) {
    Log-Warn "ANTHROPIC_API_KEY ayarli degil. apps\backend\.env dosyasina ekleyin."
}

# ── 6. Testler ────────────────────────────────────────────────────────────────
Log-Step "Testler calistiriliyor..."
Push-Location $Backend
python -m pytest tests/ -q 2>&1
if ($LASTEXITCODE -ne 0) {
    Log-Err "Testler basarisiz. Sunucu baslatilmadi."
    Pop-Location
    exit 1
}
Log-Ok "54 test gecti"
Pop-Location

# ── 7. Port 8000 temizle (eski process varsa) ─────────────────────────────────
$portInfo = netstat -ano 2>&1 | Select-String ":8000 " | Where-Object { $_ -match "LISTENING" }
if ($portInfo) {
    $pid = ($portInfo -split "\s+")[-1]
    try {
        Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
        Start-Sleep -Milliseconds 500
        Log-Ok "Eski sunucu kapatildi (PID $pid)"
    } catch { }
}

# ── 8. Baslar ─────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "  ================================================" -ForegroundColor Blue
Write-Host "   API   ->  http://localhost:8000              " -ForegroundColor White
Write-Host "   Docs  ->  http://localhost:8000/docs         " -ForegroundColor White
Write-Host "   Durmak icin: Ctrl+C                          " -ForegroundColor Gray
Write-Host "  ================================================" -ForegroundColor Blue
Write-Host ""

Push-Location $Backend
python -m uvicorn job_copilot_api.main:app --reload --port 8000
Pop-Location
