<#
.SYNOPSIS
    Start MerchantShield AI locally, in demo mode, from a clean checkout.

.DESCRIPTION
    Checks the three things that actually go wrong (no virtual environment, no
    built frontend, port already in use), then starts uvicorn in the foreground.

    Demo mode means: 15 seeded SIMULATED orders, PayPal served by the local mock
    and labelled MOCK, no credentials required, no real money anywhere.

    Every check prints PASS or FAIL with a one-line fix. Nothing here silently
    continues after a failure.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\run_demo.ps1
    powershell -ExecutionPolicy Bypass -File scripts\run_demo.ps1 -Port 8010
#>
[CmdletBinding()]
param(
    [int]$Port = 8000,
    [string]$HostAddress = "127.0.0.1",
    [switch]$NoSeed
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$distIndex = Join-Path $repoRoot "frontend\dist\index.html"

function Write-Step([string]$Text) { Write-Host "==> $Text" -ForegroundColor Cyan }
function Fail([string]$Message, [string]$Fix) {
    Write-Host "FAIL: $Message" -ForegroundColor Red
    if ($Fix) { Write-Host "      $Fix" -ForegroundColor Yellow }
    exit 1
}

Write-Step "Checking the repository layout"
if (-not (Test-Path (Join-Path $repoRoot "backend\app\main.py"))) {
    Fail "backend\app\main.py not found next to this script." "Run this from the repository you cloned."
}

Write-Step "Checking the Python virtual environment"
if (-not (Test-Path $venvPython)) {
    Fail "no .venv found at $venvPython" "py -3.11 -m venv .venv; .\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt"
}
$version = & $venvPython --version 2>&1
Write-Host "    $version"

Write-Step "Checking that the frontend is built"
if (-not (Test-Path $distIndex)) {
    Fail "frontend\dist is missing, so there is no SPA to serve." "cd frontend; npm ci; npm run build"
}
Write-Host "    found $distIndex"

Write-Step "Checking that port $Port is free"
$busy = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($busy) {
    $owners = ($busy | Select-Object -ExpandProperty OwningProcess -Unique) -join ", "
    Fail "port $Port is already in use by process id $owners" "Get-Process -Id $owners ; Stop-Process -Id $owners    (or pass -Port 8010)"
}

$env:DEMO_MODE = "true"
$env:PAYPAL_MODE = "mock"
$env:PORT = "$Port"
if ($NoSeed) { $env:MS_SKIP_SEED = "true" }

Write-Step "Starting MerchantShield AI on http://${HostAddress}:$Port"
Write-Host "    DEMO_MODE   = $env:DEMO_MODE"
Write-Host "    PAYPAL_MODE = $env:PAYPAL_MODE"
Write-Host "    LLM_PROVIDER= $($env:LLM_PROVIDER)"
Write-Host ""
Write-Host "    Open http://${HostAddress}:$Port in your browser." -ForegroundColor Green
Write-Host "    Press Ctrl+C to stop." -ForegroundColor Green
Write-Host ""

Push-Location $repoRoot
try {
    & $venvPython -m uvicorn app.main:app --app-dir backend --host $HostAddress --port $Port
    $code = $LASTEXITCODE
} finally {
    Pop-Location
}

if ($code -ne 0) {
    Write-Host "uvicorn exited with code $code" -ForegroundColor Red
    exit $code
}
