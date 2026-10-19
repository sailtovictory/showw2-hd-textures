<#
.SYNOPSIS
    Rename NAME.ext__dir folders back to NAME.ext, deepest first.

.DESCRIPTION
    bmp_stage.py and tga_stage.py rename folders that look like images (faerog.bmp, vihlop.tga) to
    NAME.ext__dir so chaiNNer's glob does not try to open them. Run this on hd_out after chaiNNer and
    BEFORE fix_descriptors.py. Supports -WhatIf. Exit codes: 0 ok, 1 error (e.g. target name exists).

.EXAMPLE
    .\scripts\unmark-dirs.ps1 -Root C:\work\hd_out -WhatIf
    .\scripts\unmark-dirs.ps1 -Root C:\work\hd_out
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [Parameter(Mandatory = $true)] [string] $Root
)
$ErrorActionPreference = 'Stop'

function Fail([string] $Message) {
    Write-Host "ERROR: $Message" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path -LiteralPath $Root -PathType Container)) { Fail "Folder not found: $Root" }

$dirs = @(Get-ChildItem -LiteralPath $Root -Recurse -Directory -Filter '*__dir' |
          Sort-Object { $_.FullName.Length } -Descending)
$done = 0
foreach ($d in $dirs) {
    $newName = $d.Name -replace '__dir$', ''
    $target = Join-Path $d.Parent.FullName $newName
    if (Test-Path -LiteralPath $target) {
        Fail "Cannot rename '$($d.FullName)': '$target' already exists. Merge them by hand."
    }
    if ($PSCmdlet.ShouldProcess($d.FullName, "Rename to $newName")) {
        Rename-Item -LiteralPath $d.FullName -NewName $newName
        $done++
    }
}
Write-Host "Renamed $done of $($dirs.Count) folder(s)."
exit 0
