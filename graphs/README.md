# chaiNNer graphs

`template.chn` is a working graph saved from chaiNNer 0.25.1 with placeholder paths (`C:\work\...`,
`C:\models\4x-UltraSharp.pth`). Use it as a reference, but save your own template: chaiNNer versions differ,
and your model path is different.

## Save your own template (once)

1. In chaiNNer, build: **Load Images** -> **Upscale Image** (fed by **Load Model**) -> **Save Image**.
   Connect Load Images' *Subdirectory Path* and *Name* outputs to the matching Save Image inputs, as in
   `template.chn`, so the folder structure is kept.
2. Load Model: pick `4x-UltraSharp.pth`.
3. Upscale Image: tick **Custom Scale** and set it to **2**; tick **Separate Alpha**; tile size **Auto**.
4. Save Image: tick **Skip existing files**.
5. Load Images: untick **Use limit**.
6. Save it as `graphs\local\template.chn`. The `graphs\local\` folder is ignored by git, so your paths stay on your machine.

The folders you put in the template do not matter; `make_graphs.py` replaces them.

## Generate the per-folder graphs

```powershell
Copy-Item graphs\folders.example.json graphs\local\folders.json
# edit work_dir (and model, or delete that line to keep the template's model)
python scripts\make_graphs.py graphs\local\folders.json
```

This writes `graphs\local\01_alpha_entity_-human.chn`, `02_opaque_entity_-human.chn`, ... and `graphs.txt`
with the run order. Open each one in chaiNNer and run it.

Lanes in the config:

| lane     | loads                               | glob        | saves                     | format |
|----------|-------------------------------------|-------------|---------------------------|--------|
| `alpha`  | `<work_dir>\stage_alpha\<folder>`   | `**/*.tga`  | `<work_dir>\hd_out\<folder>` | TGA |
| `opaque` | `<work_dir>\stage_opaque\<folder>`  | `**/*.bmp`  | `<work_dir>\hd_out\<folder>` | BMP |
| `custom` | `load_dir`                          | `glob`      | `save_dir`                | `format` |

chaiNNer's *Subdirectory Path* is relative to the loaded folder, so the save folder has to end in the same
subfolder as the load folder. The `alpha` and `opaque` lanes do that for you. For `custom` jobs, keep the two
folders parallel yourself.

Example `custom` job for the image-named folders that `tga_stage.py` puts aside:

```json
{"lane": "custom", "name": "dirnamed", "load_dir": "C:\\work\\tga_hold\\dirnamed",
 "glob": "**/*.tga", "save_dir": "C:\\work\\hd_out", "format": "tga"}
```

## How make_chn.py edits a graph

A `.chn` file is JSON: `{version, content: {nodes, edges, viewport}, timestamp, checksum, migration}`.
`checksum` is the MD5 of the compact JSON (`separators=(',', ':')`, UTF-8) of `content`. chaiNNer checks it,
so it is recomputed after every edit.

Inputs changed (node input numbers as in chaiNNer 0.25.1):

| node                         | input | meaning       |
|------------------------------|-------|---------------|
| `chainner:image:load_images` | `0`   | directory     |
|                              | `3`   | glob          |
|                              | `4`   | use limit (set to 0) |
| `chainner:image:save`        | `1`   | base directory |
|                              | `4`   | image format  |
| `chainner:pytorch:load_model`| `0`   | model path    |

Other chaiNNer versions may number inputs differently (**hypothesis**: not tested). If a generated graph
opens with wrong settings, save a new template in your version and check the numbers in its JSON.
