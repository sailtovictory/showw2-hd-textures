<#
.SYNOPSIS
    Run the whole pipeline: stage, hold greyscale, make graphs, (you run chaiNNer), unmark, fix descriptors, pack.

.DESCRIPTION
    Work folder layout (created under -WorkDir):
      stage_alpha, stage_opaque   output of bmp_stage.py
      grey_hold                   greyscale files moved aside by find_grey.py
      stage_tga, tga_hold         output of tga_stage.py (only with -IncludeOriginalTga)
      hd_out                      chaiNNer output, edited descriptors; this is what gets packed
      reports                     *_report.txt files and the generated folders.json

    The extracted tree (-ResourceDir) is only read. The game folder (-GameDir) is only changed by
    touch-and-pack.ps1 at the very end, after you confirm. The script refuses to run without
    <GameDir>\resource.pak.bak.

    At each chaiNNer step the script stops and tells you which graph to open. Resume a later step with
    -StartAt (stage, graphs, upscale, unmark, descriptors, pack).
    Exit codes: 0 done, 1 error, 3 stopped by you.

.EXAMPLE
    .\scripts\run-pipeline.ps1 -ResourceDir C:\work\resource -WorkDir C:\work\hd -GameDir "C:\Games\Soldiers"
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string] $ResourceDir,
    [Parameter(Mandatory = $true)] [string] $WorkDir,
    [Parameter(Mandatory = $true)] [string] $GameDir,
    [string] $Config,
    [string] $Template,
    [switch] $IncludeOriginalTga,
    [ValidateSet('stage', 'graphs', 'upscale', 'unmark', 'descriptors', 'pack')] [string] $StartAt = 'stage',
    [ValidateRange(0, 9)] [int] $Level = 1,
    [string] $Python = 'python',
    [string] $SevenZip = 'C:\Program Files\7-Zip\7z.exe'
)
$ErrorActionPreference = 'Stop'
$Here = $PSScriptRoot
$Repo = Split-Path $Here -Parent
$Steps = @('stage', 'graphs', 'upscale', 'unmark', 'descriptors', 'pack')

function Fail([string] $Message) {
    Write-Host "ERROR: $Message" -ForegroundColor Red
    exit 1
}
function Step([string] $Name) { return $Steps.IndexOf($Name) -ge $Steps.IndexOf($StartAt) }
function Header([string] $Text) { Write-Host ''; Write-Host "=== $Text ===" -ForegroundColor Cyan }
function Py {
    & $Python @args
    if ($LASTEXITCODE -ne 0) { Fail "python $($args[0] | Split-Path -Leaf) failed (exit code $LASTEXITCODE)." }
}
function Ask([string] $Question) {
    $a = Read-Host "$Question [y/N]"
    return $a -match '^(y|yes)$'
}
function Full([string] $Path) { return [System.IO.Path]::GetFullPath($Path).TrimEnd('\') + '\' }
function Inside([string] $Child, [string] $Parent) {
    return (Full $Child).StartsWith((Full $Parent), [System.StringComparison]::OrdinalIgnoreCase)
}

# --- safety checks -------------------------------------------------------------------------------
$pak = Join-Path $GameDir 'resource.pak'
if (-not (Test-Path -LiteralPath "$pak.bak" -PathType Leaf)) {
    Fail "No backup at '$pak.bak'. Make one first: Copy-Item '$pak' '$pak.bak'"
}
if (-not (Test-Path -LiteralPath $ResourceDir -PathType Container)) { Fail "Extracted tree not found: $ResourceDir" }

$sa = Join-Path $WorkDir 'stage_alpha'
$so = Join-Path $WorkDir 'stage_opaque'
$gh = Join-Path $WorkDir 'grey_hold'
$st = Join-Path $WorkDir 'stage_tga'
$th = Join-Path $WorkDir 'tga_hold'
$hd = Join-Path $WorkDir 'hd_out'
$rep = Join-Path $WorkDir 'reports'
$graphDir = Join-Path $Repo 'graphs\local'

# The extracted tree must stay untouched: no output folder may be inside it, and it may not be inside one.
if (Inside $WorkDir $ResourceDir) { Fail 'WorkDir must not be inside ResourceDir: the extracted tree must stay untouched.' }
foreach ($o in @($sa, $so, $gh, $st, $th, $hd, $rep)) {
    if (Inside $ResourceDir $o) { Fail "ResourceDir must not be inside the output folder $o." }
}
if (Inside $WorkDir $GameDir) { Fail 'WorkDir must not be inside the game folder.' }
& $Python --version *> $null
if ($LASTEXITCODE -ne 0) { Fail "Python not found ('$Python'). Install Python 3.9+ or pass -Python." }
New-Item -ItemType Directory -Force -Path $WorkDir, $rep | Out-Null

if (-not $Template) { $Template = Join-Path $graphDir 'template.chn' }
if (-not (Test-Path -LiteralPath $Template -PathType Leaf)) {
    Fail "Template graph not found: $Template. Save your own from chaiNNer first (see graphs/README.md)."
}

# --- 1. stage ------------------------------------------------------------------------------------
if (Step 'stage') {
    Header '1/6 Stage BMPs (bmp_stage.py) and hold greyscale images (find_grey.py)'
    $restage = $false
    if ((Test-Path -LiteralPath $sa) -or (Test-Path -LiteralPath $so)) {
        if (-not (Ask "Staging folders already exist in $WorkDir. Stage again on top of them?")) {
            Write-Host 'Skipping staging.'
        } else { $restage = $true }
    } else { $restage = $true }
    if ($restage) {
        Py (Join-Path $Here 'bmp_stage.py') $ResourceDir $sa $so --report (Join-Path $rep 'bmp_report.txt')
        Py (Join-Path $Here 'find_grey.py') $sa $so --move $gh --report (Join-Path $rep 'grey_candidates.txt')
    }
}

# --- 2. graphs -----------------------------------------------------------------------------------
function Make-Graphs([string] $ConfigPath, [string] $OutDir) {
    Py (Join-Path $Here 'make_graphs.py') $ConfigPath --template $Template --out-dir $OutDir
}
function Default-Config {
    $cfgPath = Join-Path $rep 'folders.json'
    $cfg = Get-Content -LiteralPath (Join-Path $Repo 'graphs\folders.example.json') -Raw | ConvertFrom-Json
    $cfg.work_dir = (Full $WorkDir).TrimEnd('\')
    $cfg.PSObject.Properties.Remove('model')       # keep the model path saved in your template
    $cfg.PSObject.Properties.Remove('template')
    $cfg | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $cfgPath -Encoding UTF8
    return $cfgPath
}
if (Step 'graphs') {
    Header '2/6 Make chaiNNer graphs (make_graphs.py)'
    if (-not $Config) { $Config = Default-Config }
    Make-Graphs $Config (Join-Path $graphDir 'bmp')
}

# --- 3. upscale (manual) -------------------------------------------------------------------------
function Run-Graphs([string] $Dir) {
    $list = Join-Path $Dir 'graphs.txt'
    if (-not (Test-Path -LiteralPath $list)) { Fail "No graph list at $list. Run with -StartAt graphs." }
    $lines = @(Get-Content -LiteralPath $list | Where-Object { $_.Trim() })
    $i = 0
    foreach ($line in $lines) {
        $i++
        $f = $line.Split("`t")
        Write-Host ''
        Write-Host "[$i/$($lines.Count)] Open in chaiNNer: $(Join-Path $Dir $f[0])" -ForegroundColor Yellow
        Write-Host "        loads $($f[1]) ($($f[2])) -> saves $($f[4]) to $($f[3])"
        if (-not (Test-Path -LiteralPath $f[1])) { Write-Host '        (load folder does not exist: nothing to do, skip it)' }
        $a = Read-Host '        Run it, wait until it finishes, then press Enter (s = skip, q = quit)'
        if ($a -eq 'q') { Write-Host "Stopped. Resume with -StartAt upscale."; exit 3 }
    }
}
if (Step 'upscale') {
    Header '3/6 Upscale in chaiNNer (manual)'
    Write-Host 'Settings in every graph: Custom Scale 2, Separate Alpha on, Skip existing files on.'
    Run-Graphs (Join-Path $graphDir 'bmp')

    if ($IncludeOriginalTga) {
        Header '3b Original TGAs (tga_stage.py): mind the 2 GiB limit, see docs/size-limit.md'
        Py (Join-Path $Here 'tga_stage.py') $ResourceDir $st $th --hd-out $hd --report (Join-Path $rep 'tga_report.txt')
        $tcfg = [ordered]@{
            jobs = @(
                [ordered]@{ lane = 'custom'; name = 'original_tga'; load_dir = (Full $st).TrimEnd('\'); glob = '**/*.tga'
                            save_dir = (Full $hd).TrimEnd('\'); format = 'tga' },
                [ordered]@{ lane = 'custom'; name = 'dirnamed'; load_dir = (Join-Path (Full $th) 'dirnamed'); glob = '**/*.tga'
                            save_dir = (Full $hd).TrimEnd('\'); format = 'tga' }
            )
        }
        $tcfgPath = Join-Path $rep 'tga_folders.json'
        $tcfg | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $tcfgPath -Encoding UTF8
        Make-Graphs $tcfgPath (Join-Path $graphDir 'tga')
        Run-Graphs (Join-Path $graphDir 'tga')
    }
}

# --- 4. unmark -----------------------------------------------------------------------------------
if (Step 'unmark') {
    Header '4/6 Rename NAME.ext__dir folders back (unmark-dirs.ps1)'
    if (-not (Test-Path -LiteralPath $hd -PathType Container)) { Fail "No chaiNNer output at $hd." }
    & (Join-Path $Here 'unmark-dirs.ps1') -Root $hd
    if ($LASTEXITCODE -ne 0) { Fail 'unmark-dirs.ps1 failed.' }
}

# --- 5. descriptors ------------------------------------------------------------------------------
if (Step 'descriptors') {
    Header '5/6 Fix descriptors (fix_descriptors.py): dry run first'
    $drep = Join-Path $rep 'descriptor_report.txt'
    Py (Join-Path $Here 'fix_descriptors.py') $ResourceDir $hd --dry-run --report $drep
    Write-Host "Check the numbers above and $drep (about 80 unresolved frames are normal: they are in the original game)."
    if (-not (Ask 'Write the edited descriptors into hd_out now?')) { Write-Host 'Stopped. Resume with -StartAt descriptors.'; exit 3 }
    Py (Join-Path $Here 'fix_descriptors.py') $ResourceDir $hd --report $drep
}

# --- 6. pack -------------------------------------------------------------------------------------
if (Step 'pack') {
    Header '6/6 Size check and pack'
    & (Join-Path $Here 'size-report.ps1') -HdOut $hd -OriginalPak "$pak.bak"
    if ($LASTEXITCODE -eq 2) {
        if (-not (Ask 'Estimated pak is over 2 GiB. Pack anyway?')) {
            Write-Host 'Stopped. Move folders out of hd_out (whole folders, with their descriptors), then resume with -StartAt pack.'
            exit 3
        }
    } elseif ($LASTEXITCODE -ne 0) { Fail 'size-report.ps1 failed.' }
    if (-not (Ask "Update $pak now?")) { Write-Host 'Stopped. Resume with -StartAt pack.'; exit 3 }
    & (Join-Path $Here 'touch-and-pack.ps1') -Pak $pak -HdOut $hd -Level $Level -SevenZip $SevenZip
    if ($LASTEXITCODE -ne 0) { Fail 'touch-and-pack.ps1 failed. Restore with restore-backup.ps1 if the game misbehaves.' }
    Write-Host ''
    Write-Host 'Done. Start the game and check. To undo: .\scripts\restore-backup.ps1 -GameDir <game folder>' -ForegroundColor Green
}
exit 0
