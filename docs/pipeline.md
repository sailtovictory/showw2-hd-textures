# Pipeline: step by step

Every step is a PowerShell block you can paste. Run the commands from the repository folder. Change these three
paths to match your machine:

| placeholder | meaning |
|-------------|---------|
| `C:\Games\Soldiers` | game folder (holds `resource.pak`) |
| `C:\work` | work folder with plenty of free space (several GB) |
| `C:\models\4x-UltraSharp.pth` | the upscaling model |

Expected output lines come from the last run on the test install (Enhanced Edition). On another install your
numbers should be close but may differ.

`run-pipeline.ps1` chains steps 2 to 9 and stops at every manual chaiNNer step:

```powershell
.\scripts\run-pipeline.ps1 -ResourceDir C:\work\resource -WorkDir C:\work -GameDir "C:\Games\Soldiers"
```

The manual steps follow.

## 0. Requirements

- Windows, PowerShell 5.1 or later
- Python 3.9 or later (`python --version`)
- 7-Zip in `C:\Program Files\7-Zip\` (otherwise pass `-SevenZip <path>` to the scripts)
- chaiNNer with the PyTorch backend, and the `4x-UltraSharp.pth` model
- A GPU helps a lot. The full BMP set is a few thousand small images.

## 1. Back up and extract

The backup is your reset button. Keep it until you are done.

```powershell
Copy-Item "C:\Games\Soldiers\resource.pak" "C:\Games\Soldiers\resource.pak.bak"
& "C:\Program Files\7-Zip\7z.exe" x "C:\Games\Soldiers\resource.pak" -o"C:\work\resource"
```

**Never edit `C:\work\resource`.** Every script reads it and writes elsewhere.

## 2. Stage the BMPs

```powershell
python scripts\bmp_stage.py C:\work\resource C:\work\stage_alpha C:\work\stage_opaque
```

- 32 bpp BMPs with real alpha -> 32 bpp TGA in `stage_alpha` (chaiNNer would drop the BMP alpha)
- 24 bpp BMPs, and 32 bpp BMPs whose alpha is all 255 -> copied to `stage_opaque`
- images with a side under 16 px -> skipped (usually data bitmaps)
- folders named like images -> written as `NAME.bmp__dir` (undone in step 6)

Expected (test install):

```
{'alpha_tga': 1140, 'opaque_copy': 1013, 'small_skipped': 141, 'other_skipped': 0} -> details in bmp_report.txt
```

## 3. Set greyscale images aside

```powershell
python scripts\find_grey.py C:\work\stage_alpha C:\work\stage_opaque --move C:\work\grey_hold
```

Images where at least 98% of pixels are grey are usually data maps (masks, light maps) and are not upscaled.
Expected: `flagged 65 greyscale files -> grey_candidates.txt`.

## 4. Make the chaiNNer graphs

Save your own template once (see [graphs/README.md](../graphs/README.md)) as `graphs\local\template.chn`. Then:

```powershell
Copy-Item graphs\folders.example.json graphs\local\folders.json
notepad graphs\local\folders.json        # set work_dir and model
python scripts\make_graphs.py graphs\local\folders.json
```

This writes one graph per folder and lane into `graphs\local\`, plus `graphs.txt` with the order.

## 5. Upscale in chaiNNer

Open each graph in the order of `graphs\local\graphs.txt` and run it. Settings in every graph: *Custom Scale*
**2**, *Separate Alpha* on, tile size Auto, *Skip existing files* on.

Order used: `entity\-human`, `entity\-vehicle`, `texture`, `entity`, `fx\_bmp`. With one graph per top-level folder,
runs stay short and a failure only affects one folder. `entity` comes after its subfolders. *Skip existing files*
makes it skip what is already done.

Output goes to `C:\work\hd_out`. TGA for the alpha lane, BMP for the opaque lane.

### 5b. Optional: the game's original TGAs

The game also has about 2,700 original `.tga` files. Including them all pushes the pak over 2 GiB
([size-limit.md](size-limit.md)). Dry run first:

```powershell
python scripts\tga_stage.py C:\work\resource C:\work\stage_tga C:\work\tga_hold --hd-out C:\work\hd_out --dry-run
```

Expected (test install): `staged 1115, grey 29, small 36, dirnamed 222, excluded 1293, big 4` in the TOTAL line.
Then run it without `--dry-run`. Make graphs for `C:\work\stage_tga` (and `C:\work\tga_hold\dirnamed`) with
`custom` jobs (see [graphs/README.md](../graphs/README.md)). The `dirnamed` files are **not** in `stage_tga`.
They are in `tga_hold\dirnamed` with marked folder names and need their own graph.

On the test install only `entity\landscape\stamp\Roads` and `\Grounds` from this set made it into the final build.

## 6. Rename marked folders back

```powershell
.\scripts\unmark-dirs.ps1 -Root C:\work\hd_out
```

Must run **before** step 7. Otherwise `fix_descriptors.py` cannot match those images to their originals.

## 7. Fix the descriptors

Always dry run first:

```powershell
python scripts\fix_descriptors.py C:\work\resource C:\work\hd_out --dry-run
python scripts\fix_descriptors.py C:\work\resource C:\work\hd_out
```

Expected after all BMP batches (test install):

```
{'written': 963, 'frames_renamed': 936, 'axis_scaled': 82, 'mixed_ratio': 0, 'frame_unresolved': 80}
```

About 80 unresolved frames are normal (broken in the original game). `mixed_ratio` should be 0. Details are in
`descriptor_report.txt`. Edited `.ebm`/`.tex` files are written into `hd_out`. The extracted tree is not touched.

## 8. Check the size

```powershell
.\scripts\size-report.ps1 -HdOut C:\work\hd_out -OriginalPak "C:\Games\Soldiers\resource.pak.bak"
```

If the estimate is near or above 2 GiB, move whole folders out of `hd_out` first. See [size-limit.md](size-limit.md).

## 9. Pack

```powershell
.\scripts\touch-and-pack.ps1 -Pak "C:\Games\Soldiers\resource.pak" -HdOut C:\work\hd_out
```

This touches every file, then runs `7z u -tzip -mx=1 resource.pak "C:\work\hd_out\*"` and `7z t`, and prints the
size. Expected: `Everything is Ok` twice, then `Pak size: ... GiB`. It warns above 1.95 GiB and fails above 2 GiB.

## 10. Test in game, or undo

Start a mission with infantry, vehicles and ground textures in view. If something looks wrong, see
[troubleshooting.md](troubleshooting.md). To undo:

```powershell
.\scripts\restore-backup.ps1 -GameDir "C:\Games\Soldiers"
```
