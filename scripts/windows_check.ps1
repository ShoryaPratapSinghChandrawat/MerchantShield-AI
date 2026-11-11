<#
.SYNOPSIS
    Runs every MerchantShield AI check on this Windows machine (current phase:
    phase 6 mutation set, which includes phases 0, 1, 2 and 5) and saves the
    evidence to artifacts\phase-0\local-windows\.

.DESCRIPTION
    This script does NOT prove anything about any machine other than the one
    it runs on. It prints exactly what it ran, what passed, what failed, and
    what it did not attempt. If a step fails it stops immediately and shows
    the real error instead of continuing and reporting a misleading summary.

    Compatible with Windows PowerShell 5.1 and PowerShell 7.

.EXAMPLE
    Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
    .\scripts\windows_check.ps1

.EXAMPLE
    .\scripts\windows_check.ps1 -SkipBrowserInstall
#>

[CmdletBinding()]
param(
    # Skip "npx playwright install chromium" (useful if already downloaded).
    [switch] $SkipBrowserInstall,

    # Skip "npm ci" (useful when node_modules is already correct).
    [switch] $SkipNpmInstall
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# ---------------------------------------------------------------------------
# Paths. Resolved from this script's own location, so the working directory
# does not matter.
# ---------------------------------------------------------------------------
$ScriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot    = Split-Path -Parent $ScriptDir
$BackendDir  = Join-Path $RepoRoot 'backend'
$FrontendDir = Join-Path $RepoRoot 'frontend'
$ArtifactDir = Join-Path $RepoRoot 'artifacts\phase-0\local-windows'
$VenvPython  = Join-Path $RepoRoot '.venv\Scripts\python.exe'

New-Item -ItemType Directory -Force -Path $ArtifactDir | Out-Null

$TranscriptPath = Join-Path $ArtifactDir 'windows-run.log'
try { Stop-Transcript | Out-Null } catch { }
Start-Transcript -Path $TranscriptPath -Force | Out-Null

# ---------------------------------------------------------------------------
# Step bookkeeping
# ---------------------------------------------------------------------------
$script:Steps = New-Object System.Collections.ArrayList

function Write-Heading {
    param([string] $Text)
    Write-Host ''
    Write-Host ('=' * 78) -ForegroundColor Cyan
    Write-Host "  $Text" -ForegroundColor Cyan
    Write-Host ('=' * 78) -ForegroundColor Cyan
}

function Add-StepResult {
    param([string] $Name, [string] $Status, [string] $Detail = '')
    [void] $script:Steps.Add([pscustomobject]@{
        Step   = $Name
        Status = $Status
        Detail = $Detail
    })
}

<#
    Runs a native command and FAILS LOUDLY on a non-zero exit code.
    $ErrorActionPreference = 'Stop' does not catch native exit codes, so the
    check has to be explicit. Without this, a failed pytest run would scroll
    past and the summary would claim success.
#>
function Invoke-Step {
    param(
        [Parameter(Mandatory = $true)][string] $Name,
        [Parameter(Mandatory = $true)][string] $Exe,
        [Parameter(Mandatory = $true)][string[]] $Arguments,
        [string] $WorkingDirectory = $RepoRoot
    )

    Write-Heading $Name
    Write-Host "> $Exe $($Arguments -join ' ')" -ForegroundColor DarkGray
    Write-Host "  (in $WorkingDirectory)" -ForegroundColor DarkGray
    Write-Host ''

    Push-Location $WorkingDirectory
    try {
        $global:LASTEXITCODE = 0
        & $Exe @Arguments
        $code = $LASTEXITCODE
    }
    finally {
        Pop-Location
    }

    if ($code -ne 0) {
        Add-StepResult -Name $Name -Status 'FAILED' -Detail "exit code $code"
        Write-Host ''
        Write-Host "STEP FAILED: $Name (exit code $code)" -ForegroundColor Red
        Write-Host 'Stopping here. The output above is the real error - do not' -ForegroundColor Red
        Write-Host 'ignore it and do not re-run with the test weakened.' -ForegroundColor Red
        Show-Summary
        Stop-Transcript | Out-Null
        exit $code
    }

    Add-StepResult -Name $Name -Status 'PASSED'
    Write-Host ''
    Write-Host "OK: $Name" -ForegroundColor Green
}

function Show-Summary {
    Write-Heading 'Summary of what THIS machine actually ran'
    $script:Steps | Format-Table -AutoSize | Out-String | Write-Host

    Write-Host 'NOT verified by this script:' -ForegroundColor Yellow
    Write-Host '  - any machine other than this one'
    Write-Host '  - any real PayPal Sandbox API call (Phase 0 is mock-only)'
    Write-Host '  - any browser other than the Chromium that Playwright pinned'
    Write-Host ''
}

# ---------------------------------------------------------------------------
# 0. Environment report
# ---------------------------------------------------------------------------
Write-Heading 'Environment'
Write-Host "Date (local)     : $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz')"
Write-Host "Date (UTC)       : $((Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ'))"
Write-Host "PowerShell       : $($PSVersionTable.PSVersion)"
Write-Host "PS edition       : $($PSVersionTable.PSEdition)"
Write-Host "OS               : $([System.Environment]::OSVersion.VersionString)"
Write-Host "64-bit process   : $([System.Environment]::Is64BitProcess)"
Write-Host "Repo root        : $RepoRoot"
Write-Host "Artifacts        : $ArtifactDir"
Write-Host "Transcript       : $TranscriptPath"

if ($RepoRoot -match '\s') {
    Write-Host ''
    Write-Host 'NOTE: the repository path contains a space. That is supported,' -ForegroundColor Yellow
    Write-Host '      but always quote paths you type yourself.' -ForegroundColor Yellow
}
if ($RepoRoot -match 'OneDrive') {
    Write-Host ''
    Write-Host 'WARNING: this repo is inside OneDrive. File syncing can lock' -ForegroundColor Yellow
    Write-Host '         files and cause failures that look random.' -ForegroundColor Yellow
    Write-Host '         Prefer a path such as C:\dev\merchantshield-test.' -ForegroundColor Yellow
}

# ---------------------------------------------------------------------------
# 1. Version gates
# ---------------------------------------------------------------------------
Write-Heading 'Version gates'

function Get-CommandVersion {
    param([string] $Exe, [string[]] $Arguments)
    try {
        $global:LASTEXITCODE = 0
        $out = & $Exe @Arguments 2>&1 | Out-String
        if ($LASTEXITCODE -ne 0) { return $null }
        return $out.Trim()
    }
    catch {
        return $null
    }
}

$pyVersion = Get-CommandVersion -Exe 'py' -Arguments @('-3.11', '--version')
if ($null -eq $pyVersion) {
    Write-Host 'Python 3.11 was not found via the "py -3.11" launcher.' -ForegroundColor Red
    Write-Host 'Install Python 3.11 from python.org and tick "Add python.exe to PATH".' -ForegroundColor Red
    Add-StepResult -Name 'Python 3.11 present' -Status 'FAILED' -Detail 'py -3.11 not available'
    Show-Summary
    Stop-Transcript | Out-Null
    exit 1
}
Write-Host "python (py -3.11): $pyVersion"
Add-StepResult -Name 'Python 3.11 present' -Status 'PASSED' -Detail $pyVersion

$nodeVersion = Get-CommandVersion -Exe 'node' -Arguments @('--version')
if ($null -eq $nodeVersion) {
    Write-Host 'Node.js was not found. Install Node 24.' -ForegroundColor Red
    Add-StepResult -Name 'Node present' -Status 'FAILED' -Detail 'node not available'
    Show-Summary
    Stop-Transcript | Out-Null
    exit 1
}
Write-Host "node             : $nodeVersion"
if ($nodeVersion -notmatch '^v24\.') {
    Write-Host ''
    Write-Host "WARNING: Node $nodeVersion is not the pinned major (v24.x, see .nvmrc)." -ForegroundColor Yellow
    Write-Host '         Vite 8 requires >= 22.12. Anything older will fail.' -ForegroundColor Yellow
    Add-StepResult -Name 'Node 24 pinned major' -Status 'WARNING' -Detail $nodeVersion
}
else {
    Add-StepResult -Name 'Node 24 pinned major' -Status 'PASSED' -Detail $nodeVersion
}

$npmVersion = Get-CommandVersion -Exe 'npm' -Arguments @('--version')
Write-Host "npm              : $npmVersion"

# ---------------------------------------------------------------------------
# 2. Backend virtualenv
# ---------------------------------------------------------------------------
if (-not (Test-Path $VenvPython)) {
    Invoke-Step -Name 'Create virtualenv (.venv)' -Exe 'py' `
        -Arguments @('-3.11', '-m', 'venv', '.venv') -WorkingDirectory $RepoRoot
}
else {
    Write-Heading 'Create virtualenv (.venv)'
    Write-Host 'Already present - skipping.'
    Add-StepResult -Name 'Create virtualenv (.venv)' -Status 'SKIPPED' -Detail 'already present'
}

if (-not (Test-Path $VenvPython)) {
    Write-Host "Expected interpreter missing: $VenvPython" -ForegroundColor Red
    Add-StepResult -Name 'Virtualenv interpreter' -Status 'FAILED' -Detail $VenvPython
    Show-Summary
    Stop-Transcript | Out-Null
    exit 1
}

Invoke-Step -Name 'Upgrade pip' -Exe $VenvPython `
    -Arguments @('-m', 'pip', 'install', '--upgrade', 'pip') -WorkingDirectory $RepoRoot

Invoke-Step -Name 'Install backend dependencies (pinned)' -Exe $VenvPython `
    -Arguments @('-m', 'pip', 'install', '-r', 'backend\requirements.txt') `
    -WorkingDirectory $RepoRoot

# ---------------------------------------------------------------------------
# 3. Backend tests
# ---------------------------------------------------------------------------
Invoke-Step -Name 'Backend tests (pytest)' -Exe $VenvPython `
    -Arguments @('-m', 'pytest', '-v') -WorkingDirectory $BackendDir

# ---------------------------------------------------------------------------
# 4. Frontend
# ---------------------------------------------------------------------------
if (-not $SkipNpmInstall) {
    Invoke-Step -Name 'Install frontend dependencies (npm ci)' -Exe 'npm' `
        -Arguments @('ci') -WorkingDirectory $FrontendDir
}
else {
    Add-StepResult -Name 'Install frontend dependencies (npm ci)' -Status 'SKIPPED' -Detail '-SkipNpmInstall'
}

if (-not $SkipBrowserInstall) {
    Invoke-Step -Name 'Download Chromium for Playwright' -Exe 'npx' `
        -Arguments @('playwright', 'install', 'chromium') -WorkingDirectory $FrontendDir
}
else {
    Add-StepResult -Name 'Download Chromium for Playwright' -Status 'SKIPPED' -Detail '-SkipBrowserInstall'
}

Invoke-Step -Name 'Type-check and build the SPA' -Exe 'npm' `
    -Arguments @('run', 'build') -WorkingDirectory $FrontendDir

# ---------------------------------------------------------------------------
# 5. Browser tests
# ---------------------------------------------------------------------------
Invoke-Step -Name 'Browser tests (Playwright)' -Exe 'npx' `
    -Arguments @('playwright', 'test') -WorkingDirectory $FrontendDir

# ---------------------------------------------------------------------------
# 6. Mutation check
# ---------------------------------------------------------------------------
Invoke-Step -Name 'Mutation check (phase 6)' -Exe $VenvPython `
    -Arguments @('scripts\mutation_check.py', '--phase', '6') -WorkingDirectory $RepoRoot

# ---------------------------------------------------------------------------
# 7. Evidence
# ---------------------------------------------------------------------------
Write-Heading 'Evidence files'

$evidence = Get-ChildItem -Path $ArtifactDir -File -ErrorAction SilentlyContinue |
    Sort-Object Name
if ($null -eq $evidence -or @($evidence).Count -eq 0) {
    Write-Host 'No evidence files were produced. That is itself a failure.' -ForegroundColor Red
    Add-StepResult -Name 'Evidence produced' -Status 'FAILED' -Detail 'artifact directory empty'
}
else {
    $evidence |
        Select-Object Name, @{ Name = 'SizeBytes'; Expression = { $_.Length } }, LastWriteTime |
        Format-Table -AutoSize | Out-String | Write-Host
    Add-StepResult -Name 'Evidence produced' -Status 'PASSED' -Detail "$(@($evidence).Count) file(s)"
}

Write-Heading 'Screenshots'
$shots = Get-ChildItem -Path $ArtifactDir -Filter 'screenshot-*.png' -File -ErrorAction SilentlyContinue
if ($null -eq $shots -or @($shots).Count -eq 0) {
    Write-Host 'No screenshots found.' -ForegroundColor Yellow
}
else {
    foreach ($shot in $shots) {
        Write-Host ("  {0}  ({1:N0} bytes)" -f $shot.Name, $shot.Length)
    }
}

Write-Heading 'Browser console logs'
$logs = Get-ChildItem -Path $ArtifactDir -Filter 'console-*.log' -File -ErrorAction SilentlyContinue
if ($null -eq $logs -or @($logs).Count -eq 0) {
    Write-Host 'No console logs found.' -ForegroundColor Yellow
}
else {
    foreach ($log in $logs) {
        Write-Host ''
        Write-Host ("----- {0} -----" -f $log.Name) -ForegroundColor DarkGray
        Get-Content -Path $log.FullName | Write-Host
    }
}

# ---------------------------------------------------------------------------
# 8. Summary
# ---------------------------------------------------------------------------
Show-Summary

Write-Host 'All steps above completed on THIS machine.' -ForegroundColor Green
Write-Host "Full transcript: $TranscriptPath" -ForegroundColor Green
Write-Host ''
Write-Host 'Please send the transcript and the screenshots back, so the result'
Write-Host 'can be recorded as verified instead of assumed.'

Stop-Transcript | Out-Null
exit 0
