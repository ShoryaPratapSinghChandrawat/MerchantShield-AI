<#
.SYNOPSIS
    Run every check this project has, in the order that fails fastest.

.DESCRIPTION
    Each step prints PASS or FAIL and the script stops at the first failure,
    because a green later step proves nothing if an earlier one is red.

    Steps:
      1. backend pytest
      2. frontend tsc --noEmit
      3. frontend vite build
      4. Playwright browser suite (starts its own uvicorn on 127.0.0.1:8010)
      5. mutation check for a phase you name (optional, -Phase 2)

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\test_all.ps1
    powershell -ExecutionPolicy Bypass -File scripts\test_all.ps1 -Phase 2
    powershell -ExecutionPolicy Bypass -File scripts\test_all.ps1 -SkipBrowser
#>
[CmdletBinding()]
param(
    [int]$Phase = -1,
    [switch]$SkipBrowser
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$frontend = Join-Path $repoRoot "frontend"
$started = Get-Date
$results = New-Object System.Collections.Generic.List[string]

function Step([string]$Name, [scriptblock]$Body) {
    Write-Host ""
    Write-Host "==> $Name" -ForegroundColor Cyan
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    & $Body
    if ($LASTEXITCODE -ne 0) {
        $sw.Stop()
        Write-Host "FAIL: $Name (exit $LASTEXITCODE, $([int]$sw.Elapsed.TotalSeconds)s)" -ForegroundColor Red
        $results.Add("FAIL  $Name")
        Write-Host ""
        Write-Host "Stopped. Fix this before trusting anything after it." -ForegroundColor Red
        exit 1
    }
    $sw.Stop()
    Write-Host "PASS: $Name ($([int]$sw.Elapsed.TotalSeconds)s)" -ForegroundColor Green
    $results.Add("PASS  $Name")
}

if (-not (Test-Path $venvPython)) {
    Write-Host "FAIL: no .venv at $venvPython" -ForegroundColor Red
    Write-Host "      py -3.11 -m venv .venv; .\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt" -ForegroundColor Yellow
    exit 1
}

Step "backend pytest" {
    Push-Location (Join-Path $repoRoot "backend")
    try { & $venvPython -m pytest } finally { Pop-Location }
}

Step "frontend typecheck (tsc --noEmit)" {
    Push-Location $frontend
    try { & npx tsc --noEmit } finally { Pop-Location }
}

Step "frontend build (vite build)" {
    Push-Location $frontend
    try { & npx vite build } finally { Pop-Location }
}

if (-not $SkipBrowser) {
    Step "browser suite (Playwright)" {
        Push-Location $frontend
        try { & npx playwright test } finally { Pop-Location }
    }
}

if ($Phase -ge 0) {
    Step "mutation check (phase $Phase)" {
        Push-Location $repoRoot
        try { & $venvPython scripts\mutation_check.py --phase $Phase } finally { Pop-Location }
    }
}

$elapsed = [int]((Get-Date) - $started).TotalSeconds
Write-Host ""
Write-Host "All requested checks passed in ${elapsed}s:" -ForegroundColor Green
$results | ForEach-Object { Write-Host "  $_" }
Write-Host ""
Write-Host "Reminder: this proves the checks RAN HERE. It does not prove Windows," -ForegroundColor Yellow
Write-Host "the PayPal Sandbox, or Gemini work - those are separate, labelled claims." -ForegroundColor Yellow
