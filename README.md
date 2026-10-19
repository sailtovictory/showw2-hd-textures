# showw2-hd-textures

Scripts and a step-by-step guide to make a **2x AI-upscaled texture pack** for *Soldiers: Heroes of World War II*
(Enhanced Edition) with [chaiNNer](https://github.com/chaiNNer-org/chaiNNer) and the 4x-UltraSharp model, and to
repack it into the game's `resource.pak`.

**What it is:** a texture swap. Soldiers, vehicles, ground and effects get sharper.
**What it is not:** a remaster. The 2004 engine has no PBR or modern shaders, so the game does not look modern,
only sharper. No textures are included. You build the pack yourself from your own copy of the game.

## Requirements

- Windows (the game, the paths and the PowerShell helpers are Windows-only; the Python scripts run anywhere)
- Python 3.9+ (standard library only)
- [7-Zip](https://www.7-zip.org/)
- chaiNNer with the PyTorch backend, and the `4x-UltraSharp.pth` model
- Several GB of free disk space (upscaling everything is estimated at about 2.5 GB of output), and preferably a GPU

## Quick start

```powershell
Copy-Item "C:\Games\Soldiers\resource.pak" "C:\Games\Soldiers\resource.pak.bak"     # backup = reset button
& "C:\Program Files\7-Zip\7z.exe" x "C:\Games\Soldiers\resource.pak" -o"C:\work\resource"
python scripts\bmp_stage.py C:\work\resource C:\work\stage_alpha C:\work\stage_opaque
python scripts\find_grey.py C:\work\stage_alpha C:\work\stage_opaque --move C:\work\grey_hold
# save your chaiNNer template as graphs\local\template.chn (graphs/README.md), copy and edit folders.example.json
python scripts\make_graphs.py graphs\local\folders.json      # then run each graph in chaiNNer
.\scripts\unmark-dirs.ps1 -Root C:\work\hd_out
python scripts\fix_descriptors.py C:\work\resource C:\work\hd_out --dry-run   # then again without --dry-run
.\scripts\size-report.ps1 -HdOut C:\work\hd_out -OriginalPak "C:\Games\Soldiers\resource.pak.bak"
.\scripts\touch-and-pack.ps1 -Pak "C:\Games\Soldiers\resource.pak" -HdOut C:\work\hd_out
```

Or let `scripts\run-pipeline.ps1 -ResourceDir C:\work\resource -WorkDir C:\work -GameDir "C:\Games\Soldiers"`
walk you through it. The full guide with expected output is in [docs/pipeline.md](docs/pipeline.md).

## Result

On the test install, the final pack contained every BMP texture plus the road and ground stamps from the
original TGAs. All were upscaled 2x (soldier skins 64x64 -> 128x128, for example). The pak grew from 0.8 GiB to
1.97 GiB, and the game worked. Textures are sharper. The look of the game is otherwise
unchanged.

## What is in this repository

| path | what |
|------|------|
| `scripts/bmp_stage.py` | Sorts BMPs: alpha BMPs -> 32 bpp TGA (chaiNNer drops BMP alpha), opaque BMPs -> copy |
| `scripts/find_grey.py` | Sets greyscale data maps aside so they are not upscaled |
| `scripts/tga_stage.py` | Stages the game's original TGAs, sorted into groups (optional lane) |
| `scripts/make_graphs.py`, `make_chn.py` | Generate chaiNNer graphs from one template |
| `scripts/fix_descriptors.py` | Rewrites `.ebm`/`.tex`: BMP->TGA frame names, scaled `Axis` anchors |
| `scripts/*.ps1` | Pack with size check, rename marked folders, size report, restore backup, guided run |
| `graphs/` | Example template and folder list |
| `docs/` | [pipeline](docs/pipeline.md), [engine notes](docs/engine-notes.md), [size limit](docs/size-limit.md), [troubleshooting](docs/troubleshooting.md), [video experiment](docs/video-experiment.md) |

Every script has `--help` (Python) or `Get-Help` (PowerShell). No script modifies the extracted tree. Only
`touch-and-pack.ps1` and `restore-backup.ps1` touch the game folder, and both require `resource.pak.bak`.

## Known limits

- **2 GiB pak limit.** A 2.29 GiB pak broke the game; 1.97 GiB worked. You cannot upscale everything. See
  [docs/size-limit.md](docs/size-limit.md).
- **UI images untested.** The 1,293 TGAs under `interface\` were never tried. At 2x they may break the layout.
  They are excluded by default.
- **Cutscenes: not recommended.** Upscaling the WMV videos works technically, but it makes the compression
  artifacts worse. See [docs/video-experiment.md](docs/video-experiment.md).
- **Only one model tested.** Real-ESRGAN, Remacri, NMKD and others were not compared.
- **One install tested** (Enhanced Edition). Other editions or patches may differ.
- **Windows only** for the game-facing steps.

## Development

```powershell
python -m pip install -r requirements-dev.txt
ruff check .
pytest
```

Tests use synthetic images and descriptors generated in code. Never add game files to this repository.

## Legal

This is an unofficial fan project. It is not affiliated with or endorsed by the developers or publishers of
*Soldiers: Heroes of World War II*. You need your own legal copy of the game. This repository contains no game
assets. The game and its assets belong to their respective owners. The scripts are MIT licensed
([LICENSE](LICENSE)).
