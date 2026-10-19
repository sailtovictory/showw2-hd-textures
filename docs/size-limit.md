# The 2 GiB limit

## What was measured

| build | pak size | result |
|-------|----------|--------|
| original game | 0.8 GiB | works |
| several partial builds | 1.5, 1.8, 1.96 GiB | worked |
| final build | 1.97 GiB (2,117,542,008 bytes) | worked |
| everything upscaled | **2.29 GiB** | **game broke** |

The exact symptom of the 2.29 GiB build was not recorded. `7z t` passed on it, so the archive itself was not
damaged.

**(hypothesis)** The 2004 engine reads the pak with 32-bit signed file offsets, so it fails once the pak is
larger than 2 GiB (2,147,483,648 bytes). Only the two sides of the boundary were tested (1.97 works, 2.29 fails).

`touch-and-pack.ps1` warns above 1.95 GiB and fails above 2 GiB.

## Rule of thumb

On the test install, **every 1 MB of upscaled output added about 0.6 MB to the pak**. This is after deflate
and after replacing the original files. **(hypothesis)** The factor depends on the mix of BMP and TGA, so treat
it as a rough guide.

Compression level barely matters: `-mx=9` saved only about 0.03 GiB compared with `-mx=1`, and it is much slower.

`size-report.ps1` prints the raw size per folder and this estimate:

```powershell
.\scripts\size-report.ps1 -HdOut C:\work\hd_out -OriginalPak "C:\Games\Soldiers\resource.pak.bak"
```

```
estimated pak = original pak + 0.6 x raw hd_out size
```

## Where the size goes

Raw upscaled output by folder on the test install (MB, before packing):

| folder | raw MB |
|--------|-------:|
| `texture\common` | 1,357 (ground textures alone: 540) |
| `entity\-vehicle` | 589 |
| `entity\landscape` | 151 |
| `entity\background` | 115 |
| `map\multi` | 70 |

## Budgeting method

1. Upscale everything you might want into `hd_out` and run the descriptor fix.
2. Run `size-report.ps1` with `-OriginalPak` and look at the biggest folders.
3. If the estimate is above about 1.9 GiB, move **whole folders** out of `hd_out` (into a `*_hold` folder),
   starting with the ones that matter least to you.
4. Pack, then read the real size that `touch-and-pack.ps1` prints. If it is over the limit, restore the backup
   and repeat. Always pack onto a fresh copy of the original (`restore-backup.ps1` first), so files you removed
   from `hd_out` do not stay in the pak.

**Never remove only an image and keep its descriptor, or the reverse.** A descriptor that says `Frame "x.tga"`
needs `x.tga` in the pak. Either move whole folders, or re-run `fix_descriptors.py` on the reduced `hd_out` after
deleting the descriptors it wrote earlier.

## What the working build contained

The final 1.97 GiB build on the test install was:

- all BMP batches (`entity\-human`, `entity\-vehicle`, `texture`, `entity`, `fx\_bmp`), and
- from the original-TGA batch only the road and ground stamps: `entity\landscape\stamp\Roads` and
  `entity\landscape\stamp\Grounds`.

It left out, for size: the other original-TGA groups, `interface\*` (1,293 TGAs, also untested) and the
`video\*` TGA sprites.
