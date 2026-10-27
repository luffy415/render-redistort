---
name: render-redistort
description: Apply supplied lens-distortion STMaps to tracked-camera renders and save compositing-ready sources in the original image format and precision. Use for 렌더 디스토션, STMap 적용, redistort, or 렌즈 왜곡 합성 소스; not camera solving, keying, or creative image editing.
metadata:
  version: "1.0.0"
---

# Render Redistort

Deliver saved, frame-aligned renders in the shooting plate's distortion space. Preserve input format, native bit depth, channels, alpha association, and color interpretation. Do not alter the shooting plate or create a final person/background composite unless separately requested.

## Install or first use

Read [setup.md](references/setup.md). Register this folder under `$CODEX_HOME/skills/render-redistort` (default `~/.codex/skills/render-redistort`), prepare the isolated runtime with `scripts/setup_runtime.py`, then run `scripts/self_test.py`. Installation requests include these ordinary local steps. No API keys, paid services, GPU, or camera-tracking skill are required. Do not overwrite an existing skill/runtime without inspecting it. Report that a newly registered skill is discoverable on the next turn.

## Work from supplied evidence

1. Inspect actual render frames, map and calibration/render metadata. Recover dimensions, frame numbers/rate, map direction, UV origin/normalization, render camera and color/alpha encoding. A redistortion map samples **input CG at each output plate pixel**. An undistortion map cannot be substituted by changing a label. Ask only for material information that the files do not establish; do not infer direction from appearance alone.
2. Read [formats-and-quality.md](references/formats-and-quality.md). The tested helper supports single-part RGB/RGBA EXR (HALF/FLOAT), PNG (8/16-bit), and TIFF (8/16-bit/HALF/FLOAT/DOUBLE where the installed writer supports it). Unsupported layers, deep images, mixed channel types, cropped windows, videos, DPX or JPEG must not be silently flattened, demoted or converted. Follow the format-specific routing in that reference.
3. Write an explicit job JSON using [job-schema.md](references/job-schema.md). Paths resolve relative to that JSON. Specify expected CG and output dimensions; do not resize to hide a mismatch. An overscan-to-plate map may intentionally output a smaller raster: this is calibrated sampling geometry, not a separate downscale. Preserve frame identifiers and timing; do not interpolate missing frames.
4. Run `scripts/redistort.py inspect INPUT`, then `scripts/redistort.py run JOB --check-only`. Process a representative frame in a separate preview job first when evidence is uncertain. Use a fresh output folder for the full job. Default to cubic filtering, linear-light RGB and correct alpha association. Use another filter/border policy only when warranted.
5. Run the full job. Inspect beginning/middle/end and difficult edges against supplied footage or a known reference. Numeric map checks do not verify the physical lens fit. Do not claim shot alignment without a shot comparison. Report output paths, format/bit depth, sizes, frame count/range, color/alpha handling, coverage and verification. Include `redistort_manifest.json`.

## Quality contract

“No quality loss” means no additional lossy codec, bit-depth reduction, hidden color transform, gratuitous resize, dropped channels or changed frame cadence. **A non-identity distortion requires resampling and is not mathematically lossless.** Explain that distinction plainly. Keep HDR/negative float values. Report native integer quantization and range clipping. Use lossless compression; replacing lossy EXR DWAA/DWAB with ZIP keeps EXR format and must be disclosed.

Never lower precision because a preview tool only supports 8-bit. Separately named previews are not deliverables. Never upload production footage/maps while installing, testing or distributing this skill.

## Completion and failures

The helper refuses existing outputs, hashes inputs, checks coverage, rejects ambiguous sequences, and decodes every output to verify format/precision/pixels. A failure leaves a failed manifest and any completed frames in the new folder; do not call this a complete delivery. Resolve the cause and use a fresh output. No automatic overwrite, arbitrary repeated retries or undeclared fallback formats.
