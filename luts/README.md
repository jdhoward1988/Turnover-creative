# Turnover Creative LUTs

Five 33-point `.cube` LUTs built from the PMV5 Lightroom presets (Seeker, Summit, Ranger, 400t + PM Film, 400p PM Film).

- **Input:** Rec.709 / standard footage. Correct and expose log or flat footage to normal Rec.709 colour first.
- **Premiere:** Lumetri → Creative → Look → Browse, then lower Intensity to taste (60–80% is a good start).
- **Not included:** grain, sharpening, noise reduction, clarity, dehaze and vignette, because a LUT can't hold them. Add grain and vignette separately if you want them.
- **400p PM Film** uses Auto white balance in Lightroom, which can't be baked in. Set white balance on each clip.

These rebuild the presets' colour and tone settings with approximate maths, so they are close to the presets, not exact matches.
`lut-preview.png` shows each LUT on a test chart. To regenerate the LUTs: `python3 xmp2cube.py <out_dir> preset1.xmp preset2.xmp ...` (needs numpy).
