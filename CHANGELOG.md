# Changelog

## 2026-09-24 — photo mode on real photos

The photo pipeline was scored on synthetic fixtures only; on real photos a golden
retriever traced with fence boards and grass as splatter, double contours on every
edge band, and fur shadows as interior blobs. Measured and fixed on three
open-licensed Commons photos.

- **Background drop.** Single-subject policies (`animal`, `plant`, `generic`) now remove
  ink outside the dilated GrabCut mask and stand the subject on a ground contact line
  (`<g data-ground="1">`, absent from fragments — the scene supplies the ground). The
  mask must look like one framed subject (5–70% of the frame, not spilling over the
  border) or the old soft rule applies. GrabCut runs in **colour** (grayscale could not
  separate a white dog from a red barn), seeded by a thin border ring instead of a
  centre rect (the old rect clipped tail and head), on a ≤640px copy with a fixed RNG
  seed — ~10x faster and reproducible call after call.
- **Centreline tracing.** Every ink component is classed as a ribbon (edge band) or a
  blob (solid dark patch). Ribbons are thinned (in-house numpy Zhang-Suen, no
  opencv-contrib), spur-pruned and walked into polylines with branches merged at
  two-way junctions, so a thick band yields one stroke instead of both of its sides.
  Blobs are outlined; interior blobs that are neither dark (eye, nose) nor large are fur
  shadow and go. Length floors apply to whole connected structures (the outline is
  long; a grass tuft is not), a squiggliness rule drops texture networks, and inside a
  dropped subject the clean style's wide-block threshold is 1.5x stricter (shading is
  not a line). Strokes are three-tier: silhouette 4.6 / interior 3.6 / background 2.6.
- **Real-photo evaluation tier.** `tools/eval_photo.py` also traces the sample photos in
  `assets/photos/` (dog, teddy — EXIF stripped, attributed in CREDITS.md) and any
  `--photos DIR`, scoring subject-ink ratio inside the GrabCut mask, slivers and regions,
  with their own bands (`photo:<name>|<style>|<metric>`) in `eval_bands.json`.
  Synthetic bands recalibrated for the new vectorizer (the low-light fixture, which has
  no subject at all, now traces to nothing instead of 190 grain contours).
- **Showcase pages 17/18 are the real dog** (matted onto the meadow kit; sketch style
  with its own ground line) instead of the synthetic rabbit blob.
- A dropped-background trace carries a white knockout of its subject mask
  (`data-knockout="1"`) so scene lines behind it stop at the silhouette when composited.
- Sketch style falls back to the clean extractor when the ridge detector yields almost
  no line on flat, step-edged subjects. Fragments anchor on the traced art's extent
  rather than the raw ink.

## 2026-09-24 — audit and refinement pass

Audit of the repo with the current model generation; execution by Opus 5.5 subagents,
review and integration by Fable 5.1.

- **Page text is now Andika glyph paths** (`charlib.text_path`, `TXT`, `otext`), so renders
  and PDFs are byte-identical across machines and embed no system font. The example PDF
  used to embed Helvetica when built on macOS and DejaVu Sans on Linux. Captions wrap by
  measured width. `TEXT_MODE = "font"` restores the legacy `<text>` output.
- **Hollow letters** (tracing pages, banners) are overlap-free (glyph overlaps removed at
  build time with skia-pathops, a dev-only dependency) and have a thick colorable body
  with counters kept open: the tracing channel went from ~7 px to ~20 px at size 120.
- **Validator: `mass_distribution` check.** Ink coverage is measured in three bands between
  the title and caption; a hollow middle third or a sky-only top is a MED finding with the
  recipe fix in the message. This closed a real blind spot: the old span rule was being
  satisfied by untagged sun rays while the scene sat in a strip on the ground line.
- **Helper redraws** after a visual audit: `cow`, `cactus`, `monkey`, `kid_run`,
  `kid_wheelchair`, `symmetry_page` (motif now ~60% of page width), `sticker_sheet`
  (motifs auto-fit to cells), `speech_bubble`/`thought_bubble` (`speaker_top=`),
  `school_bus` (hood was at the rear), `dump_truck`, `telescope` (tripod was upside down),
  `finish_page` (the house sat entirely on one side of the axis).
- **`tree_round` regression fixed:** the August canopy texture drew paired caret marks
  that read as a sleeping face on every default round tree (and through `scene_*` kits
  and `forest_border`).
- **Dead code removed:** `barn`, `schoolhouse`, `lighthouse`, `windmill` were each defined
  twice; the first definitions were shadowed.
- **Showcase relaid out** as measured grids (catalog pages) and recipe-composed scenes;
  new `19-garden` page; `fragment_bbox`/`fit_fragment`/`restroke` helpers.
- **Example book rebuilt** per the three-layer recipe with the letters kit, a creativity
  page, and library furniture instead of local copies.
- Docs: README, SKILL.md workflow, drawing guide numbers reconciled with the validator,
  model-tiers re-keyed by capability class.

## 2026-08-24 — quality and validation (PR #1)

Deterministic validator (`lib/validate.py`), smooth figure rebuilds (`smooth_path`,
`limb`), Andika letters kit, content packs (100+ helpers), scene kits (`lib/scenes.py`),
creativity layer, photo-to-outline pipeline (`lib/photolib.py`) with an evaluation gate,
pytest suite, CI workflow, PII gate.

## 2026-07-23 — benchmark v2 instruction fixes

Six-model benchmark (three Claude tiers + three GPT-5.6 variants): caption wrapping in
`page()`, anti-gaming span language, matted-cluster swallow rule, canopy-mark rule
co-located in helper docstrings, non-Claude section in model-tiers.

## 2026-07-19 — v1 public release

Parametric faces and figures, room furniture, motifs, story mode with tropes, shape
cookbook, model-tier guidance, the "Where Is Button?" example.
