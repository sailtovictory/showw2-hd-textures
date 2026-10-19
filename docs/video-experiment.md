# Cutscene upscaling: tried, not recommended

This is a record of an experiment. It is **not** part of the pipeline, and the result was judged not worth it.

## Source material

- Cutscenes are loose `.wmv` files in `<game>\resource\video\<campaign>\...`, outside `resource.pak`.
- Codec WMV3 (Windows Media Video 9), about 2 Mbps, 640x480 or 640x330, 25 fps.
- They are heavily compressed. 4x-UltraSharp **amplified the compression artifacts** instead of adding detail.

## What the game's player accepts

ffmpeg cannot encode WMV3, only WMV2. The game's player showed a **grey box** for ffmpeg's output until the ASF
layout matched the original:

- audio must be **stream 1**, video **stream 2**
- packet size **8000**

A plain remux with those settings plays:

```powershell
ffmpeg -i in.wmv -map 0:a -map 0:v -c copy -packet_size 8000 out.wmv
```

With new (upscaled) frames as input 0 and the original file as input 1:

```powershell
ffmpeg -i frames\%06d.png -i in.wmv -map 1:a -map 0:v -c:v wmv2 -b:v 8M -pix_fmt yuv420p -c:a copy -packet_size 8000 out.wmv
```

(Set the frame-rate of the image input to match the source, e.g. `-framerate 25` before `-i frames\...`.)

A 1280x960 WMV2 file played in game.

## Verdict

It works technically, but it does not look better. Upscaling bakes in the blocking and smearing of the 2 Mbps
source. Not recommended. Other models or a denoise pass before upscaling were not tried.
