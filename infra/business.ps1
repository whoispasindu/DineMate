<#
.SYNOPSIS
Runs the DineMate Business local server: start, stop, status, logs, backup, update.

.EXAMPLE
powershell -ExecutionPolicy Bypass -File infra\business.ps1 backup
#>
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet("start", "stop", "status", "logs", "backup", "update")]
    [string]$Command,
    [Parameter(Position = 1)]
    [string]$Service
)

. (Join-Path $PSScriptRoot "business-common.ps1")

Assert-Docker
if (-not (Test-Path $Script:EnvFile)) {
    Stop-WithError "infra\.env.business is missing. Run infra\install-business.ps1 first."
}

switch ($Command) {
    "start" {
        $address = Update-StreamHost
        Invoke-Compose @("up", "-d", "--wait")
        Show-Urls $address
    }
    "stop" {
        Invoke-Compose @("stop")
        Write-Host "Stopped. Your data is kept; run 'business.ps1 start' to start again."
    }
    "status" {
        Invoke-Compose @("ps")
    }
    "logs" {
        $arguments = @("logs", "--tail", "200")
        if ($Service) { $arguments += $Service }
        Invoke-Compose $arguments
    }
    "backup" {
        New-Item -ItemType Directory -Force -Path $Script:BackupDir | Out-Null
        $name = "dinemate-$(Get-Date -Format 'yyyyMMdd-HHmm').dump"
        Invoke-Compose @("exec", "-T", "db", "pg_dump", "-U", "dinemate", "-d", "dinemate", "-Fc", "-f", "/tmp/$name")
        Invoke-Compose @("cp", "db:/tmp/$name", (Join-Path $Script:BackupDir $name))
        Invoke-Compose @("exec", "-T", "db", "rm", "-f", "/tmp/$name")
        Write-Host "Saved backups\$name. Copy it, together with infra\.env.business, somewhere safe."
    }
    "update" {
        $address = Update-StreamHost
        Invoke-Compose @("up", "-d", "--build", "--wait")
        Write-Host "Updated. Database changes were applied when the API started."
        Show-Urls $address
    }
}
