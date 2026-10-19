# Changelog

## 2026-10-19 — individual features, real depth, story continuity, image models

Built for the current model generation's spatial reasoning — and every number such a
model authors (a depth, a hinted eye position, a page's continuity claims) is checked by
code or by eye on a render, never trusted from the plan.

- **Individual facial features** (`charlib.face` / `face_traits`): `face_shape`, `eyes`
  (dot/round/almond/smile) + `lashes`, measured `eye_spacing` / `eye_size` /
  `smile_width`, `nose`, `ears`, `mouth` (grin, gap_tooth), `dimples`, `moles`, freckle
  density, `brows="thick"`, a 3/4 head turn (`look`), `hair_part`, six new hair styles
  (ponytail, afro, bun, braids, side_part, bald) and `headwear="hijab"`. Every default is
  the classic face — a golden hash pins 1378 classic variants byte-identical. A visual
  pass fixed the eerie first drafts: lashes on the lid read as a scowl, round eyes in
  glasses as hypnotic spirals, dimples beside the mouth as smirk brackets, a plain
  ponytail cap as a beanie.
- **`lib/likeness.py`**: `traits_from_face` (landmarks → measured proportions with
  documented, uncalibrated anthropometric centres; feature words → traits),
  `describe_traits`, `check_traits`, `cast_distinctness`, `model_sheet` (the "Meet
  <name>!" approval page; showcase 21). `reference/likeness-guide.md`.
- **`lib/space3d.py`**: one-point-perspective `Camera`, depth-sorted `Stage` (far→near,
  mats, contact lines after mats, `data-depth` tags, `gaze`), colorable `room_box`,
  `path_recede`, `box3d`, `table3d`, `receding_row`, `ground_grid`, `ground_ellipse` —
  converging lines stop at the 14 px sliver floor. Validator `depth_order` (MED);
  `head_clearance` exempts strictly farther depth groups. Showcase 20.
  `reference/spatial-guide.md`.
- **`lib/story.py`**: the story bible (`story.json`) + continuity linter — trait drift,
  prop-state windows, solve-beat actor, location anchors, refrain cadence, arc coverage,
  caption rules, rendered caption/figure cross-checks — `python3 -m lib.story`. On the
  bundled example it found a bedroom whose window and bed swapped sides (04/05), a
  refrain gap (05-06) and past tense (08/09): all fixed, pages embed their story record,
  example checks clean. `reference/story-mode.md` "Continuity" + "Coherence craft".
- **Validator `hand_hidden`** (MED): a figure's own hand erased by its own wide hair —
  found the girl's raised hand swallowed by a pigtail puff on showcase 12 (fixed with
  `wave_high`). `lint_book` ignores story records when looking for duplicates.
- **Photo mode, people**: YuNet landmarks are surfaced (`face_landmarks`,
  `detect_faces_full`, IMAGE-left/right) and the never-wired `protect_face` policy flag
  now protects eyes, brows, nose, mouth, glasses and declared marks from despeckling;
  protected eyes get iris dots (a traced lid alone reads asleep); `feature_fidelity`
  scores the trace (synthetic portrait: 1.0 protected vs 0.43 unprotected) and is a gated
  eval tier.
- **Vision hints** (`hints=`, CLI `--hints`): the agent's own pixel read — faces with
  landmarks and features, subject box, keep / drop boxes — strictly validated;
  `hints_overlay` / `--overlay` draws them on the photo to check by eye.
- **`lib/imagemodels.py`**: pluggable segment / landmarks / depth / lineart backends
  (local ONNX via `cv2.dnn`, or any callable); a remote backend raises `PrivacyError`
  unless `allow_remote=True`, naming the consent a person's photo needs.
  `trace_lineart` / `lineart=` turns an image model's line drawing into the house style
  with fidelity as the identity-drift guard. No weights bundled; nothing phones home.
- Docs: SKILL.md workflow (likeness, story bible, depth, continuity gate), library guide,
  model-tiers (provisional per-tier use of the new capabilities), catalog covers the new
  modules.

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
