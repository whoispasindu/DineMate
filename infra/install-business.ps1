<#
.SYNOPSIS
Installs DineMate Business on this Windows PC with Docker Desktop.

.DESCRIPTION
Creates infra/.env.business with new random secrets (kept if it already exists), starts the database, API,
dashboard and camera hub, then creates your business, venue, owner account and camera hub.
Safe to run again: existing data and accounts are kept.

.EXAMPLE
powershell -ExecutionPolicy Bypass -File infra\install-business.ps1

.EXAMPLE
powershell -ExecutionPolicy Bypass -File infra\install-business.ps1 -SampleCafe
#>
param(
    [string]$Business,
    [string]$Venue,
    [string]$OwnerEmail,
    [string]$OwnerName = "Owner",
    [string]$Opens = "07:00",
    [string]$Closes = "21:00",
    [switch]$SampleCafe,
    [switch]$NoCameras,
    [int]$Port = 8080
)

. (Join-Path $PSScriptRoot "business-common.ps1")

function Read-Required([string]$Prompt, [string]$Value) {
    while (-not $Value -or -not $Value.Trim()) { $Value = Read-Host $Prompt }
    return $Value.Trim()
}

function Read-NewPassword {
    while ($true) {
        $first = Read-Host "Owner password (at least 12 characters)" -AsSecureString
        $second = Read-Host "Type it again" -AsSecureString
        $a = [Runtime.InteropServices.Marshal]::PtrToStringBSTR([Runtime.InteropServices.Marshal]::SecureStringToBSTR($first))
        $b = [Runtime.InteropServices.Marshal]::PtrToStringBSTR([Runtime.InteropServices.Marshal]::SecureStringToBSTR($second))
        if ($a -ne $b) { Write-Host "The passwords don't match. Try again." -ForegroundColor Yellow; continue }
        if ($a.Length -lt 12) { Write-Host "Use at least 12 characters." -ForegroundColor Yellow; continue }
        return $a
    }
}

Write-Host "DineMate Business: local server install" -ForegroundColor Cyan
Assert-Docker

Write-Step "Settings and secrets"
$values = Read-EnvFile
$fresh = $values.Count -eq 0
foreach ($pair in @(
        @("POSTGRES_PASSWORD", { New-Secret 24 }),
        @("DINEMATE_JWT_SECRET", { New-Secret 48 }),
        @("DINEMATE_TEMPLATE_KEY", { New-FernetKey }),
        @("DINEMATE_LIVE_LINK_SECRET", { New-Secret 32 }),
        @("DINEMATE_SIMULATOR_TOKEN", { New-Secret 32 }),
        @("DINEMATE_HUB_TOKEN", { New-Secret 32 })
    )) {
    if (-not $values.Contains($pair[0]) -or -not $values[$pair[0]]) { $values[$pair[0]] = & $pair[1] }
}
$values["WEB_PORT"] = "$Port"
$profiles = @()
if (-not $NoCameras) { $profiles += "cameras" }
if ($SampleCafe) { $profiles += "demo" }
$values["DINEMATE_PROFILES"] = ($profiles -join ",")
$values["DINEMATE_STREAM_HOST"] = Get-LanAddress
Write-EnvFile $values
if ($fresh) { Write-Host "  Created infra\.env.business with new secrets. Keep it private and back it up." }
else { Write-Host "  Using the existing infra\.env.business." }

Write-Step "Your business"
$Business = Read-Required "Business name (for example: Green Leaf Cafes)" $Business
$Venue = Read-Required "Venue name (for example: Green Leaf Kandy)" $Venue
$OwnerEmail = Read-Required "Owner email (used to sign in)" $OwnerEmail
$password = Read-NewPassword

Write-Step "Building and starting (the first time takes 10-20 minutes)"
Invoke-Compose @("up", "-d", "--build", "--wait")

Write-Step "Creating the business, owner account and camera hub"
$env:DINEMATE_SETUP_PASSWORD = $password
$env:DINEMATE_HUB_TOKEN = $values["DINEMATE_HUB_TOKEN"]
try {
    Invoke-Compose @(
        "exec", "-T", "-e", "DINEMATE_SETUP_PASSWORD", "-e", "DINEMATE_HUB_TOKEN", "api",
        "python", "-m", "app.business.setup", "create",
        "--org", $Business, "--venue", $Venue, "--owner-email", $OwnerEmail, "--owner-name", $OwnerName,
        "--opens", $Opens, "--closes", $Closes,
        "--password-env", "DINEMATE_SETUP_PASSWORD", "--hub-token-env", "DINEMATE_HUB_TOKEN"
    )
    if ($SampleCafe) {
        Invoke-Compose @(
            "exec", "-T", "-e", "DINEMATE_SETUP_PASSWORD", "api",
            "python", "-m", "app.business.setup", "sample", "--password-env", "DINEMATE_SETUP_PASSWORD"
        )
        Write-Host "  Sample Cafe accounts owner@dinemate.test and manager@dinemate.test use the same password."
    }
} finally {
    Remove-Item Env:\DINEMATE_SETUP_PASSWORD -ErrorAction SilentlyContinue
    Remove-Item Env:\DINEMATE_HUB_TOKEN -ErrorAction SilentlyContinue
    $password = $null
}

if (-not $NoCameras) {
    Invoke-Compose @("restart", "hub")
}

Show-Urls $values["DINEMATE_STREAM_HOST"]
Write-Host ""
Write-Host "Next: sign in as $OwnerEmail, open Cameras, add a camera and press Set up zones."
Write-Host "Day to day: infra\business.ps1 start | stop | status | logs | backup | update"
Write-Host "In Docker Desktop, turn on Settings > General > 'Start Docker Desktop when you sign in' so DineMate starts with the PC."
