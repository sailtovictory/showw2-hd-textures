<#
.SYNOPSIS
    Touch every file in hd_out, update resource.pak with 7-Zip, test it and check the 2 GiB limit.

.DESCRIPTION
    1. Sets the modified time of every file under -HdOut to now. 7z u skips files whose disk time is not
       newer than the archive entry, so without this step old textures silently stay in the pak.
    2. Runs: 7z u -tzip -mx=<Level> <Pak> "<HdOut>\*"
       The trailing \* makes 7-Zip store paths relative to hd_out (entity\..., not hd_out\entity\...).
    3. Runs: 7z t <Pak>
    4. Prints the pak size. Warns above 1.95 GiB, fails (exit 1) above 2 GiB (2,147,483,648 bytes).
    Refuses to run if <Pak>.bak does not exist, so there is always a way back (restore-backup.ps1).
    Exit codes: 0 ok, 1 error or pak over 2 GiB.

.EXAMPLE
    .\scripts\touch-and-pack.ps1 -Pak "C:\Games\Soldiers\resource.pak" -HdOut C:\work\hd_out
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string] $Pak,
    [Parameter(Mandatory = $true)] [string] $HdOut,
    [ValidateRange(0, 9)] [int] $Level = 1,
    [string] $SevenZip = 'C:\Program Files\7-Zip\7z.exe'
)
$ErrorActionPreference = 'Stop'

function Fail([string] $Message) {
    Write-Host "ERROR: $Message" -ForegroundColor Red
    exit 1
}

$Limit = 2147483648L
$WarnAt = [long](1.95 * 1GB)

if (-not (Test-Path -LiteralPath $SevenZip -PathType Leaf)) { Fail "7-Zip not found at '$SevenZip'. Install it or pass -SevenZip." }
if (-not (Test-Path -LiteralPath $Pak -PathType Leaf)) { Fail "Pak not found: $Pak" }
if (-not (Test-Path -LiteralPath "$Pak.bak" -PathType Leaf)) {
    Fail "No backup at '$Pak.bak'. Make one first: Copy-Item '$Pak' '$Pak.bak'"
}
if (-not (Test-Path -LiteralPath $HdOut -PathType Container)) { Fail "hd_out folder not found: $HdOut" }
$marked = @(Get-ChildItem -LiteralPath $HdOut -Recurse -Directory -Filter '*__dir')
if ($marked.Count -gt 0) {
    Fail "$($marked.Count) folder(s) still end in __dir (e.g. $($marked[0].FullName)). Run unmark-dirs.ps1 first."
}

$now = Get-Date
$files = @(Get-ChildItem -LiteralPath $HdOut -Recurse -File)
foreach ($f in $files) { $f.LastWriteTime = $now }
Write-Host "Touched $($files.Count) files."

$src = Join-Path (Resolve-Path -LiteralPath $HdOut).Path '*'
& $SevenZip u -tzip "-mx=$Level" $Pak $src
if ($LASTEXITCODE -ne 0) { Fail "7z u failed with exit code $LASTEXITCODE." }
& $SevenZip t $Pak
if ($LASTEXITCODE -ne 0) { Fail "7z t failed with exit code $LASTEXITCODE. The pak is damaged: run restore-backup.ps1." }

$size = (Get-Item -LiteralPath $Pak).Length
Write-Host ('Pak size: {0:N0} bytes = {1:N3} GiB' -f $size, ($size / 1GB))
if ($size -gt $Limit) {
    $msg = 'Pak is over 2 GiB ({0:N0} > {1:N0} bytes). The game is known to break at this size. ' -f $size, $Limit
    Fail ($msg + 'Run restore-backup.ps1, leave folders out of hd_out and pack again (see docs/size-limit.md).')
}
if ($size -gt $WarnAt) {
    Write-Warning 'Pak is above 1.95 GiB. The largest size tested to work is 1.97 GiB (2,117,542,008 bytes).'
}
exit 0
