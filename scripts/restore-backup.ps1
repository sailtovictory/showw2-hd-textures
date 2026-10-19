<#
.SYNOPSIS
    Copy resource.pak.bak back over resource.pak (the reset button).

.DESCRIPTION
    Asks for confirmation unless -Force is given. Supports -WhatIf.
    Exit codes: 0 restored, 1 error, 3 cancelled.

.EXAMPLE
    .\scripts\restore-backup.ps1 -GameDir "C:\Games\Soldiers"
#>
[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'High')]
param(
    [Parameter(Mandatory = $true)] [string] $GameDir,
    [string] $PakName = 'resource.pak',
    [switch] $Force
)
$ErrorActionPreference = 'Stop'

function Fail([string] $Message) {
    Write-Host "ERROR: $Message" -ForegroundColor Red
    exit 1
}

$pak = Join-Path $GameDir $PakName
$bak = "$pak.bak"
if (-not (Test-Path -LiteralPath $bak -PathType Leaf)) { Fail "No backup found at $bak" }

$bakSize = (Get-Item -LiteralPath $bak).Length
Write-Host ('Backup: {0} ({1:N0} bytes)' -f $bak, $bakSize)
if (Test-Path -LiteralPath $pak) {
    Write-Host ('Current: {0} ({1:N0} bytes) will be overwritten.' -f $pak, (Get-Item -LiteralPath $pak).Length)
}
if ($Force) { $ConfirmPreference = 'None' }
if (-not $PSCmdlet.ShouldProcess($pak, "Overwrite with $bak")) {
    Write-Host 'Cancelled.'
    exit 3
}
Copy-Item -LiteralPath $bak -Destination $pak -Force
if ((Get-Item -LiteralPath $pak).Length -ne $bakSize) { Fail 'Size after copy does not match the backup.' }
Write-Host 'Restored.'
exit 0
