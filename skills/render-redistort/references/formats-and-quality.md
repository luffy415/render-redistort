# Same-format delivery and quality

## Tested helper contract

| Source | Output | Precision / compression |
|---|---|---|
| RGB/RGBA single-part EXR | EXR with same filename | original HALF16 or FLOAT32; lossless ZIP |
| RGB/RGBA PNG | PNG with same filename | original8/16-bit; lossless Deflate; straight alpha |
| RGB/RGBA TIFF | TIFF with same filename | original8/16-bit or floating type accepted by writer; lossless Deflate |

Windows/Python3.13 tests cover PNG8/16, RGBA PNG16, TIFF16/FLOAT32, EXR HALF/FLOAT32, HDR/negative values, correct alpha filtering, sRGB linear-light interpolation, asymmetric map orientation, animated map frame offsets, source immutability, overwrite rejection and missing coverage/frames. Other operating systems and TIFF floating variants require the shipped self-test plus representative input/output verification before production claims.

All working resampling is float64. The saved file returns to its native representation. Re-reading verifies pixel values against that native quantization, including exact HALF/FLOAT values; normalized integer decodes allow only the OpenImageIO conversion roundoff (1e−7), below one16-bit code value. Identity tests compare decoded original/output values. Real distortions necessarily reconstruct/resample pixels; “lossless warp” is not an honest guarantee.

OpenImageIO copies the image header. Writer-specific fields and obsolete pixel dimensions are refreshed; original/delivery dimensions and compression changes remain in the manifest. Color space tag, chromaticities, ICC profile and SMPTE timecode, when present, are compared after saving. A mismatch is a failed delivery, not silently accepted. Frame rate and custom shot metadata belong in the supplied sidecar and manifest; do not invent them from filenames.

## Routes that require a host-specific workflow

- **MOV/MP4/AVI/MKV and other videos:** inspect container, codec, native pixel format/bit depth, chroma subsampling, full/video range, color primaries/transfer/matrix, timestamps, frame rate, audio and timecode with ffprobe if available. A container name is not a quality guarantee. Re-encoding ProRes/H.264/H.265 in the same codec introduces generation loss. Do not claim it satisfies a strict no-additional-loss requirement. Explain the constraint and request a lossless image sequence from the renderer, or an explicitly accepted output codec/format. Preserve audio/timing when a separately authorized video pipeline is used. The supplied helper does not decode/encode video and must not be used to make8-bit intermediates.
- **JPEG / lossy TIFF / lossy source codec:** JPEG cannot be saved again as JPEG with a general distortion and zero further coding loss. Explain and ask for a lossless delivery format. A TIFF container may still use ZIP; EXR DWAA/DWAB may use ZIP without changing native type/extension—report that compression change.
- **DPX10/12/log:** preserve packing, transfer characteristics, timecode, range and bit depth in a verified Nuke/OCIO/OpenImageIO workflow. Do not treat code values as scene-linear, change to8/16-bit PNG, or call it a supported path without testing saved values.
- **Multilayer/multipart/deep EXR, mixed precision, Cryptomatte/IDs, vectors/normals/depth:** do not drop channels or interpolate identifiers as colors. Use a host aware of channel semantics and deep samples, with per-layer filtering, full metadata and native type checks. Do not claim beauty-warped vector fields are geometrically transformed motion vectors. If a beauty-only delivery is acceptable, obtain that scope explicitly.
- **Cropped EXR / nonzero display windows / orientations:** honor absolute window coordinates. Expand or adapt in a verified host; don't reset origins and stretch pixels. The helper deliberately rejects these rather than silently shifting a shot.
- **Unknown/log/OCIO color spaces:** establish the transfer function, primaries, OCIO config and alpha association. Filter in the appropriate linear working space and return to the original encoding if that is the required deliverable. Keep every conversion documented.

For unsupported cases, continue useful inspection and prepare a concrete compatible route. Do not weaken “same format/precision” silently or claim completion after producing only a preview.

## Alignment and maps

Map plumbing tests prove direction/coordinate handling only. Verify the render camera, frame offsets and intended plate independently. If a plate is supplied, compare stationary features and asymmetric corners at beginning/middle/end. Do not warp an original-space person matte again. A whole background render normally stays behind the original-space keyed foreground; keying/roto are separate from this skill's default output.
