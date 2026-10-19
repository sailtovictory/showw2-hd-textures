<#
.SYNOPSIS
    Raw size of hd_out per top-level and second-level folder, and an estimated pak size.

.DESCRIPTION
    Estimate = original pak size + Factor x raw hd_out size. Factor 0.6 is the rule of thumb measured on
    one install (every 1 MB of upscaled output added about 0.6 MB to the pak, after deflate and after
    replacing the originals). It is an estimate, not a promise: check the real size after packing.
    Pass -OriginalPak (usually resource.pak.bak) to get the estimate; without it only raw sizes are shown.
    Exit codes: 0 ok (or estimate under 2 GiB), 1 error, 2 estimate over 2 GiB.

.EXAMPLE
    .\scripts\size-report.ps1 -HdOut C:\work\hd_out -OriginalPak "C:\Games\Soldiers\resource.pak.bak"
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string] $HdOut,
    [string] $OriginalPak,
    [double] $Factor = 0.6
)
$ErrorActionPreference = 'Stop'

function Fail([string] $Message) {
    Write-Host "ERROR: $Message" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path -LiteralPath $HdOut -PathType Container)) { Fail "hd_out folder not found: $HdOut" }
$root = (Resolve-Path -LiteralPath $HdOut).Path.TrimEnd('\') + '\'

$level1 = @{}
$level2 = @{}
$total = 0L
foreach ($f in Get-ChildItem -LiteralPath $root -Recurse -File) {
    $parts = $f.FullName.Substring($root.Length).Split('\')
    $total += $f.Length
    $k1 = if ($parts.Count -gt 1) { $parts[0] } else { '(files at top level)' }
    $level1[$k1] = [long]$level1[$k1] + $f.Length
    if ($parts.Count -gt 2) {
        $k2 = $parts[0] + '\' + $parts[1]
        $level2[$k2] = [long]$level2[$k2] + $f.Length
    }
}

function Show([hashtable] $Table, [string] $Title) {
    Write-Host ''
    Write-Host $Title
    foreach ($e in $Table.GetEnumerator() | Sort-Object Value -Descending) {
        Write-Host ('{0,10:N1} MB  {1}' -f ($e.Value / 1MB), $e.Key)
    }
}

Show $level1 'Raw size by top-level folder:'
Show $level2 'Raw size by second-level folder:'
Write-Host ''
Write-Host ('Total raw output: {0:N1} MB' -f ($total / 1MB))

if ($OriginalPak) {
    if (-not (Test-Path -LiteralPath $OriginalPak -PathType Leaf)) { Fail "Original pak not found: $OriginalPak" }
    $base = (Get-Item -LiteralPath $OriginalPak).Length
    $est = $base + [long]($Factor * $total)
    Write-Host ('Original pak:     {0:N3} GiB' -f ($base / 1GB))
    Write-Host ('Estimated pak:    {0:N3} GiB  (original + {1} x raw output; estimate only)' -f ($est / 1GB), $Factor)
    if ($est -gt 2147483648L) {
        Write-Warning 'Estimate is over 2 GiB. Leave folders out before packing (see docs/size-limit.md).'
        exit 2
    }
    if ($est -gt [long](1.95 * 1GB)) {
        Write-Warning 'Estimate is above 1.95 GiB: close to the limit.'
    }
}
exit 0
