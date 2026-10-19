# Troubleshooting

When in doubt: restore the backup and pack again from scratch. The result is the same as an incremental update.

```powershell
.\scripts\restore-backup.ps1 -GameDir "C:\Games\Soldiers"
.\scripts\touch-and-pack.ps1 -Pak "C:\Games\Soldiers\resource.pak" -HdOut C:\work\hd_out
```

## Transparent parts turn black or solid after upscaling (alpha loss)

**Cause:** chaiNNer's image loader drops the alpha channel of 32 bpp BMPs, both `BI_RGB` and `BI_BITFIELDS`.

**Fix:** stage with `bmp_stage.py`. It converts 32 bpp BMPs with real alpha to 32 bpp TGA (`stage_alpha`). Save
those as TGA in chaiNNer with *Separate Alpha* ticked. Then run `fix_descriptors.py` so the descriptors point at
the `.tga`. Do not load the original BMP tree into chaiNNer directly.

## Game still shows the old textures, or some textures are magenta

**Cause seen:** `7z u` skips a file when its modified time on disk is not newer than the entry already in the
archive. Any file in `hd_out` written before the pak was last updated is older than its entry, so 7-Zip silently
keeps the version already in the pak. This caused a long debugging session.

**Fix:** always touch before packing. `touch-and-pack.ps1` does this. By hand:

```powershell
Get-ChildItem C:\work\hd_out -Recurse -File | ForEach-Object { $_.LastWriteTime = Get-Date }
```

**(hypothesis)** Magenta means the engine could not load the frame a descriptor names. For example the pak has
an edited descriptor saying `Frame "x.tga"`, but no `x.tga`. Check with:

```powershell
& "C:\Program Files\7-Zip\7z.exe" l "C:\Games\Soldiers\resource.pak" | Select-String "x.tga"
```

Other ways to get there: an image was removed from `hd_out` but its descriptor stayed (see
[size-limit.md](size-limit.md)), or the paths in the pak start with `hd_out\` (next section).

## Files are in the pak but the game ignores them (7-Zip path prefix)

**Cause:** `7z u ... resource.pak C:\work\hd_out` stores entries as `hd_out\entity\...`. The game looks for
`entity\...`.

**Fix:** end the source with `\*`:

```powershell
& "C:\Program Files\7-Zip\7z.exe" u -tzip -mx=1 "C:\Games\Soldiers\resource.pak" "C:\work\hd_out\*"
```

If wrong entries were already added, restore the backup and pack again. `7z l` should show entries such as
`entity\-human\...`, not `hd_out\...`.

## chaiNNer: `[Errno 13] Permission denied` on a folder

**Cause:** some folders are named like images (`faerog.bmp\`, `vihlop.tga\`). The `**/*.bmp` or `**/*.tga` glob
matches the folder, and chaiNNer tries to open it as a file.

**Fix:** both staging scripts rename these folders to `NAME.ext__dir` (`bmp_stage.py` since this repo; before
that, the two BMP cases were renamed by hand). After chaiNNer, rename them back **before** `fix_descriptors.py`:

```powershell
.\scripts\unmark-dirs.ps1 -Root C:\work\hd_out
```

`touch-and-pack.ps1` refuses to pack while `__dir` folders are left.

## chaiNNer glob matches nothing for `-human`, `-vehicle`, `-fauna`

**Cause:** these folder names start with an ASCII hyphen. A WCMatch glob like `entity/?human/**` matched nothing.

**Fix:** load by directory (Load Images directory = the `-human` folder, glob `**/*.tga`). The graphs from
`make_graphs.py` already do this. Quote such paths in PowerShell: `"C:\work\stage_alpha\entity\-human"`.

## Sprites are drawn shifted after upscaling

**Cause:** `.ebm` `Axis` values are in image pixels and were not scaled.

**Fix:** run `fix_descriptors.py` (without `--no-axis`) and make sure the edited `.ebm` files are in `hd_out`
when packing.

## Roads, tracks, craters or other ground decals are twice as wide

**Cause:** the decal's image doubled, and its `.def` still uses the old scale. **(hypothesis)** The engine draws
decals at image pixels x scale.

**Fix:** run `fix_def_scale.py` over the whole `entity` folder (pipeline step 7b) and pack again. Do not limit
it to the TGA batch, because BMP-converted decals have the same problem.

```powershell
python scripts\fix_def_scale.py C:\work\resource C:\work\hd_out entity
```

Alpha spreading was ruled out as the cause: `compare_alpha.py` showed unchanged coverage and mean alpha on
the affected roads.

## Some upscaled images look grey or blotchy, or are missing

`find_grey.py --move` moves images where at least 98% of the pixels are grey into `grey_hold`, because these are
usually data maps (masks, light maps) that should not be upscaled. **(hypothesis)** Some real greyscale
textures may be caught too. Check `grey_candidates.txt`. To upscale a held file anyway, move it back into its
staging folder.

## fix_descriptors.py reports about 80 unresolved frames

Normal. These references are broken in the original game files too. See [engine-notes.md](engine-notes.md).

## The game breaks after packing everything

The pak is probably over 2 GiB. See [size-limit.md](size-limit.md). `touch-and-pack.ps1` prints the size and fails
above 2 GiB.

## Cutscene shows a grey box

See [video-experiment.md](video-experiment.md). The game's player needs audio as stream 1, video as stream 2
and packet size 8000.
