# Engine notes

Observations from one install of *Soldiers: Heroes of World War II* (Enhanced Edition, Gem engine, 2004).
Facts were seen on that install; guesses are marked **(hypothesis)**.

## resource.pak

- All assets are in `resource.pak` in the game folder. It is a **plain ZIP**: 7-Zip lists, extracts, updates
  and tests it.
- Entry paths start at the top-level asset folders (`entity\...`, `texture\...`, `fx\...`). A file added as
  `hd_out\entity\...` is a different path, and the game ignores it.
- Cutscenes are **not** in the pak. They are loose `.wmv` files in `<game>\resource\video\<campaign>\...`.
  The pak has its own `video\` folder, but it holds TGA/EBM sprites, not movies.

## Image files

| type | what was found |
|------|----------------|
| `.bmp` | Mostly 24 bpp. Some are 32 bpp with real alpha, stored either as `BI_RGB` (BGRA) or as `BI_BITFIELDS` with explicit masks. |
| `.tga` | 24 and 32 bpp, uncompressed. `tga_stage.py` also decodes RLE and greyscale TGAs in case they occur. |

Textures are small: soldier skins 64x64, animals 28x28, many sprites 124x144. The original-TGA set had
2,699 files on the test install, 1,293 of them under `interface\`.

## Descriptors

Text files, latin-1, CRLF line ends. Lines starting with `;` are comments.

### .tex

```
{Bitmap {Filtering}{Mipmap}{Blend}{AlphaChannel}{Frame "x.bmp"}}
```

No dimensions. After an upscale only the `Frame` extension may need to change (when a BMP became a TGA).

### .ebm

```
{bitmap {Axis x y}{Filtering}{Mipmap}{AlphaChannel}{Blend}{Frame "x"}}
```

`Axis` is an anchor point in **image pixels**, roughly the image centre. When the image doubles, `Axis` must
double too, or the sprite is drawn shifted. `fix_descriptors.py` scales the first `Axis` (outside comment lines) by
the measured width and height ratio of the first frame it can match.

### .def

`.def` files hold `{Sprite "x.ebm" ...}` blocks, optionally with `{Scale N}`, `{PreScaleX N}` and `{PreScaleY N}`
(default scale 1.0).

**Ground decals must be corrected.** When a decal (road, track, crater, stamp) is upscaled 2x and its `.def` is
left alone, the game draws it **twice as wide**. An early test on one road stamp suggested `.def` files need no
edit; later checks proved that wrong. **(hypothesis)** The engine draws a decal at *image pixels x scale*, which
fits what was seen.

`fix_def_scale.py` divides every `Scale`, `PreScaleX` and `PreScaleY` in a sprite block by the upscale ratio, or
inserts `{Scale 1/ratio}` (e.g. `{Scale 0.5 }`) when the block has none. Run it over the whole `entity` folder,
not only the TGA batch, because BMP-converted decals have the same problem. Sprites that point at shared images
that were not upscaled, such as `/properties/shadow/round.ebm`, must keep their scale. The script skips them
because it finds no upscaled image for them.

`compare_alpha.py` showed the wide roads were not caused by the upscale spreading alpha: coverage and mean
alpha stayed the same. Same-camera screenshots before and after are the best check.

### Frame references

- A `Frame` path is relative to the descriptor's folder.
- About **80** `Frame "..."` references in the *original* game files point at files that do not exist (often
  the name without an extension while a `.bmp` with that name exists). `fix_descriptors.py` lists them as
  "unresolved". They were already there before any change and are harmless.
- Other text files can also name images. `fix_descriptors.py` only **reports** non-descriptor files that name a
  converted BMP; it does not edit them. No problems from such files were seen in game.

## Folder-name quirks

- **Leading hyphen:** `entity\-human`, `entity\-vehicle`, `entity\-fauna` start with an ASCII hyphen (code 45).
  chaiNNer's WCMatch glob `entity/?human/...` matched nothing. Load by directory instead (as the generated
  graphs do). In PowerShell, quote such paths.
- **Folders named like images:** for example `fx\_bmp\explosion\faerog.bmp\Faer01.bmp` (animation frames) and
  `...\vihlop.tga\...`. A `**/*.bmp` glob matches the folder itself, and chaiNNer then fails with
  `[Errno 13] Permission denied`. The staging scripts rename such folders to `NAME.ext__dir`; `unmark-dirs.ps1`
  renames them back in `hd_out` after chaiNNer.

## Why BMPs with alpha become TGAs

chaiNNer's image loader drops the alpha channel of 32 bpp BMPs. This was confirmed for both `BI_RGB` and
`BI_BITFIELDS`. TGA alpha is kept. So `bmp_stage.py` converts 32 bpp BMPs with varying alpha into 32 bpp TGAs, and
`fix_descriptors.py` points their descriptors at the `.tga`. The game loads the TGA through the edited
descriptor.

## Rendering

There is no PBR and there are no shaders to change. A texture swap makes the game sharper. It does not make it
look modern.
