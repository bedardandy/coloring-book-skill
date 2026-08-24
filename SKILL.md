---
name: coloring-book
description: Create a personalized printable kids' coloring book (PDF) starring specific children, family members, and pets doing their favorite things — themed pages or a story-mode narrative for ages 3-6. Use when the user asks for a coloring book, coloring pages, or a personalized activity/story book for kids. Triggers on "coloring book", "coloring pages", "make a book for [kid]", "story coloring book".
---

# Personalized Kids' Coloring Book

Produce a letter-size vector PDF of bold line-art pages starring the user's kids/family/pets.
Characters are PARAMETRIC (trait vectors), never photo-likeness generation — this guarantees
the same recognizable character on every page and avoids identity drift entirely.

**NON-NEGOTIABLE: this skill's quality lives in executing `lib/charlib.py` with Python**
(cairosvg + ghostscript). Never re-implement the drawing library by hand or "approximate"
its helpers in another language/canvas — hand-reimplementations lose the white-fill
back-to-front layering that makes overlapping shapes read as solid objects (you get
transparent outline soup: trees as crossing circles, paths through heads). If you cannot
execute Python in your environment, STOP and tell the user that instead of improvising.

**FIRST: read `reference/model-tiers.md` and pick your operating mode honestly**
(full-creative / standard / conservative) based on your own capability tier. It also
contains the universal pre-flight layout plan — every model bottom-crams first drafts
without it — and the escalation ladder for when an element won't come right after two
attempts (compromise → delegate the element to a stronger model → recommend escalating
the whole build).

## Workflow

### 1. Cast setup — trait vector per character
For each kid collect/derive: name, age, hair style (one of `charlib.HAIR_STYLES`:
bob_bangs, bob [+headband], tousled, long_wavy, pigtails, curly, buzz), glasses y/n,
freckles y/n, a personal motif (star/strawberry/truck/butterfly/dino/ball...), favorite
things, relative height. Pets: species (dog/cat), coat (plain/spots/patch/stripes), collar.
Record the OUTFIT in the trait dict and use it everywhere (`t["outfit"]`) — never
override per-page, and when a cast recurs across books, copy trait dicts verbatim
(silently changing a signature outfit or feature breaks recognition).
Adults (grandparent etc.): long_wavy hair + glasses works well.

If PHOTOS are provided: look at them ONLY to classify trait buckets (hair style/length,
glasses, freckles, pet coat pattern) — never attempt to reproduce a face. State the traits
you extracted so the user can correct them. Distinguishability at this fidelity comes from
hair silhouette + glasses + freckles + motif + height, not facial geometry.

### 2. Mode + plan
- **themed** (default): ~10 pages, each starring the kids together in one child's favorite
  activity; rotate whose interest leads each page; every kid appears on most pages.
- **story** (ages 3-6): use the 10-beat arc in `reference/story-mode.md`. If the user
  hasn't specified a story, offer 2-3 tropes from `reference/story-tropes.md` matched to
  the child's age and interests (one-sentence pitch each) and let them pick. Captions on
  every page: 15-25 words, simple present tense, repeat names, chant-along refrain every
  1-2 pages, the child acts (never watches). Low-stakes obstacles only (hidden toy, shy
  pet). No rhyme.
Plan page-type variety: cover, name-tracing page (`name_trace_page`), scene pages
(start from a `scenes.py` kit matching the setting), one find-the-X activity page,
ONE creativity page (symmetry / finish-the-picture / design-a-thing — see the
creativity layer below), back cover ("Made with love for ...").

### 3. Render
Write a `make_book.py` in the output dir that copies the proven structure:
```python
import sys; sys.path.insert(0, "<skill_dir>/lib")
from charlib import *
def cover(): ...
BUILDERS = [("01-cover", cover), ...]
if __name__ == "__main__":
    import sys as s
    build(BUILDERS, OUTDIR, only=s.argv[1:] or None, pdf_name="<Kids>-Coloring-Book.pdf")
```
Use `charlib` primitives + figures (`kid_stand`, `kid_sitting`, `dog`, `cat_sitting`,
`face_traits`) and motifs; draw scene furniture with P/C/E/LINE. Read
`reference/drawing-guide.md` FIRST — it encodes the collision gotchas and age-band line
weights. Keep pages deterministic; partial rebuild via `python make_book.py 03` must work.

For everyday objects that have no helper (car, truck, tractor, train, boat, tree,
barn, animals, playground gear...), do NOT invent complex geometry freehand — LLMs
reliably botch object proportions. First check `charlib` for a helper
(60+ shapes: vehicles, buildings incl. `castle_small`/`treehouse`/`village_house`,
animals incl. `dog_sit`/`dog_sleep`/`reindeer`/`lion`/`baby_goat`, furniture, food,
costume props like `chef_hat`/`bib_apron`/`tiara`, scene props like `tent`/`campfire`/
`ferris_wheel`/`lamppost`/`wardrobe` — grep charlib for `^def`); if none fits, follow the
relative-proportion recipes in `reference/shape-cookbook.md` and build the object
from primitives at your chosen scale. Wrap each placed object in `matted()` over any
background. See `CREDITS.md` for the recipes' provenance.

**Line quality helpers (prefer these over hand-drawn Q-chains):**
`smooth_path(pts, closed=True)` (G1-continuous organic silhouettes), `limb()`
(tapered two-segment arm/leg outlines through shoulder→elbow→wrist with a tagged
hand circle at an exact wrist target), plus line vocabulary: `wavy_line`,
`zigzag_line`, `scallop_edge`, `stitch_dash`, `hatch_region` (ellipse hatching),
`echo` (double-contour aura around convex motifs). Kid figures and dog/cat are
already smooth rebuilds; their wrist targets match legacy coordinates, so prop
anchors keep working (`use_legacy_figures(True)` restores the old wire-limb
geometry if needed).

**Colorable letters & words (Andika OFL outlines baked to paths):** `letter()` /
`word()` / `word_width()` / `banner(text, cy)` (ribbon auto-sized from glyph
metrics — text-in-box overflow is impossible) / `name_trace_page(["Name", ...])`
(ruled guidelines + dashed trace-style letters + start stars). No font needs to
be installed; glyphs are real closed paths kids can color.

**Scene kits (`lib/scenes.py`):** `scene_meadow / scene_street / scene_beach /
scene_space / scene_farm` return proven background layers (sky lane, ground
systems, props) and document their ground line — start pages from a kit, then
add figures/vehicles on the declared ground. Landscape systems in charlib:
`hill, mountain_range, road (+ROAD_H), rail_track, fence_picket/ranch, pond,
beach_shore, forest_border, skyline, bridge`.

**Interest packs:** 100+ object helpers across vehicles, trains, air, boats,
space, flowers/garden, wild animals, farm, pets, games, buildings — find them
by interest in `reference/catalog.md` (auto-generated by `tools/gen_catalog.py`;
re-run after adding helpers). Render one page per pack any time with
`python tools/showcase.py` (writes examples/showcase/pages + validates).

**Creativity layer (pages that invite the child's own art):** blank
`speech_bubble` / `thought_bubble`, `symmetry_page(motif)` (left solid, right
dotted hint), `finish_page(kind)` (dashed ghost to complete), `pattern_menu`
(swatch strip kids copy onto blank bands), `design_template(kind)` (blank
tee/cake/rocket), `sticker_sheet(motifs)` (dashed cut cells). Mark such pages
`spage(..., layout="creative")` so the validator knows open composition is
intentional. Weave 1-2 into every book — a story beat like "draw Button's
hiding spot!" lands the engagement.

**Photo mode (`lib/photolib.py` — photos in, coloring outlines out):**
`photo_to_svg(photo, style="clean"|"sketch", detail="low|medium|high")` traces
a photo into splinter-free colorable line art (flow-coherent extraction,
anti-splinter morphology, contour averaging, angle snapping for
architectural subjects, region-floor QA loop). `photo_to_fragment` returns a
feet-anchored G()-placeable asset; `composite_page(photo, scene_body,
ground_y, x=, scale=)` stands the traced subject in a scene kit beside charlib
characters. Subject policies (face/car/house/animal…) are SOFT rules — the QA
loop adjusts them. See `reference/photo-guide.md`. All processing is local;
the bundled YuNet face model (Apache-2.0) never phones home.

### 4. Self-inspect + QA loop
After building, run the DETERMINISTIC gate first: `python -m lib.validate
pages/*.svg` (exit 1 on any HIGH finding). It checks, with exact arithmetic on
the emitted SVG's embedded geometry: border clearance (>=12px), scene mass span
(>=55% of page height from CONNECTED art, sky tokens excluded), figure/face
sizes, caption-band + title-zone intrusion, text width vs page, head-kill-radius
prop clearance, hand/arm overlap, wheel ground tangency, near-parallel sliver
gaps, knockout-mat halo swallowing, duplicate pages (`lib.validate.lint_book`).
Fix every HIGH by moving/scaling per the message; MEDs need a look; LOWs are lint.
Non-scene pages opt out of the span rule via `spage(..., layout="activity")`
(name tracing / find-the-X) or `layout="vignette"` (back cover).

Then Read every page PNG yourself and fix obvious collisions/floaters. Then run
tile QA: `render_tiles(svg, qa_dir, name)` per page and review the overlapping tiles
(spawn sonnet subagent reviewers if the Agent tool is available, one per page, prompt them for:
unintended overlapping lines, tangent-line/figure-ground illusions where background
contours touch figures, floating/disconnected parts, out-of-proportion elements,
ambiguous shapes, eerie/off-putting facial expressions, elements cut off, objects
partially ERASED by a neighbor's matting halo (the validator catches FULL erasure;
partial nibbles still need eyes), text/captions crossing the border rect;
severity-tagged findings). Apply fixes, re-render, re-run lib.validate, and
re-verify the pages that had HIGH findings. 1-2 fix rounds is normal.

### 5. Deliver
Merge to PDF via `build()` (cairosvg + ghostscript). Report the PDF path, page list, and
which traits distinguish each character. If the user has a family share, offer to copy there.
