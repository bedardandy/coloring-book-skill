# Changelog

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
