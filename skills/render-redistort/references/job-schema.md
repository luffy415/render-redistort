# Job JSON v1

All paths are local, relative to the job JSON or absolute. `input` is one file or a directory containing exactly one contiguous, consistently padded numbered sequence. `map` is one static map or one numbered EXR/TIFF map sequence. `output` must not exist. Input filenames and frame identifiers are retained.

```json
{
  "version": 1,
  "input": "renders",
  "map": "lens/redistort.exr",
  "output": "delivery_redistorted",
  "mapping": {
    "direction": "output_to_input",
    "space": "stmap_uv",
    "uv_origin": "bottom_left",
    "normalization": "pixel_edges",
    "channels": ["R", "G"],
    "source_size": [4224, 2376],
    "output_size": [3840, 2160]
  },
  "image": {
    "color_space": "linear",
    "alpha": "premultiplied",
    "filter": "cubic",
    "border": "error"
  },
  "timing": {"fps_numerator": 24000, "fps_denominator": 1001}
}
```

The sizes above are examples, not defaults for other shots. Confirm alpha association from the renderer/export settings. RGB-only sources use `alpha: none`; PNG RGBA must be `straight`.

## Map conventions

Each output array element stores the coordinate to sample in the input CG. EXR array scanlines are top-to-bottom. For a Nuke-style normalized STMap:

- R = `(source_x + 0.5) / input_width`
- G = `1 - (source_y + 0.5) / input_height` for bottom-left UV origin
- Source `x,y` use top-left integer pixel centers. The half-pixel is the raster/UV adapter, not a camera re-solve.

No colorspace conversion is applied to map channels. They must be FLOAT32 or higher; 16-bit half EXR maps are too imprecise at UHD. The helper accepts `top_left` origin only when explicitly declared. Endpoint normalization such as x/(width−1), forward point maps, displacement maps and lens coefficients are different contracts: convert them with independently checked geometry before use, never relabel.

A `.npy` alternative is float32/64 H×W×2 with `space: pixel_xy`: X/Y are already top-left integer-center source pixel coordinates. Load is non-pickle. Omit UV fields.

Animated maps match source frame numbers plus `map_frame_offset` (integer, default0). Render10 uses map0 if offset−10. Every frame must match; a static single map is reused. Do not silently sort two unrelated sequences and zip them together.

For the previously delivered Unreal-style lens sidecar, use `cg_input_render_size` as source size and `map_output_size` as output size; check declared STMap channels/origin. The camera must be the matching overscan camera. Do not add another overscan percentage, crop, offset, stabilization or resize.

## Pixels, color and alpha

`color_space: linear` means scene-linear RGB in the source's existing primaries (e.g. ACEScg); no primaries/OCIO transform is introduced. `srgb` decodes/encodes the sRGB transfer function around filtering. Rec709 gamma, LogC, camera log and other transfer functions are not sRGB. Route them through an explicit managed host pipeline.

Straight alpha is premultiplied for filtering and then unpremultiplied for delivery. Premultiplied linear RGB remains associated. Hidden RGB under zero alpha may be cleared by a non-identity warp to prevent edge contamination. Alpha ringing is clamped to[0,1] and counted; floating-point RGB remains unclamped. Integer output is quantized once at native bit depth and range clipping is counted. If clipping is material, report it and discuss a floating-point alternative instead of silently changing the required format.

`cubic` is a float64 prefiltered cubic B-spline; `linear` is bilinear. Cubic may ring at hard edges, like other reconstruction filters. Use an edge comparison to select a filter, not a claim that any filter is lossless. Coverage defaults to error. Explicit `black` fills unsupported output pixels with black/zero alpha and reports their count. Boundary sampling extends the last pixel for the finite filter footprint; it does not synthesize new scene coverage.

## Run

Use the Python path written to `runtime.local.json`:

```text
python scripts/redistort.py inspect /path/to/renders
python scripts/redistort.py run /path/to/job.json --check-only
python scripts/redistort.py run /path/to/job.json
```

`--check-only` verifies source headers and every map's coverage without creating output. Full processing decodes/hashes each frame, saves in the original extension/precision, decodes the saved pixels, and writes a manifest. Manifest timing is descriptive: the helper does not retime or manufacture a movie.
