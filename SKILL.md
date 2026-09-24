---
name: coloring-book
description: Create a personalized printable kids' coloring book (PDF) starring specific children, family members, and pets doing their favorite things — themed pages or a story-mode narrative for ages 3-6. Use when the user asks for a coloring book, coloring pages, or a personalized activity/story book for kids. Triggers on "coloring book", "coloring pages", "make a book for [kid]", "story coloring book".
---

# Personalized Kids' Coloring Book

Produce a letter-size vector PDF of bold line-art pages starring the user's kids/family/pets.
Characters are PARAMETRIC (trait vectors), never photo-likeness generation — this guarantees
the same recognizable character on every page and avoids identity drift entirely.

**NON-NEGOTIABLE: this skill's quality lives in executing `lib/charlib.py` with Python**
(cairosvg + Ghostscript; `python3`). Never re-implement the drawing library by hand or "approximate"
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
Adults (grandparent etc.): long_wavy hair + glasses works well; `beard=True` exists.

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
ONE creativity page (`symmetry_page` / `finish_page` / `design_template` — a story beat
like "draw Button's hiding spot!" lands the engagement), back cover ("Made with love
for ..."). Alternate calm and busy pages.

**Write the layout plan for every scene page BEFORE drawing** (every model
bottom-crams without it): ground line ~905; one midground anchor (tree / house /
furniture / shelf) whose top reaches y≈450-550; main figures ~300-380 px tall
(`kid_stand` scale 1.2-1.5) standing ON the ground line; sky fillers spread across the
sky lane, none in the title zone (y<145). This is the three-layer recipe in
`reference/drawing-guide.md`; the validator measures it.

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
Read `reference/drawing-guide.md` FIRST — it encodes the collision gotchas, age-band
line weights and the composition recipe. Keep pages deterministic; partial rebuild via
`python3 make_book.py 03` must work. Then:
- **Helpers before geometry.** For every everyday object (vehicles, buildings, animals,
  furniture, props, costumes — 200+ helpers) find the helper by interest in
  `reference/catalog.md`; if none fits, follow the relative-proportion recipes in
  `reference/shape-cookbook.md` and build it from primitives. LLMs reliably botch
  object proportions freehand. Side-profile helpers face right; `GM()` flips.
- **Depth order + matting.** Draw background → furniture → figures, back to front, every
  solid shape white-filled, each foreground figure/object wrapped in `matted()`. Draw
  ground/contact lines AFTER the matted figures (a mat halo otherwise dashes the ground
  line under paws and hems). Keep hands and held props outside 1.3×r of any face.
- **Text is paths.** Titles/captions/page numbers come from `spage()`; names and words
  from `name_trace_page()` / `word()` / `banner()`. Never emit `<text>` with a system
  font — renders would differ per machine.
- **Poses.** Use stock poses (`kid_stand` waves/up/down/hold, `kid_run/jump/point/carry`,
  `dog_sit/sleep/dig`...). Strong-tier only: build a custom pose from the public parts
  `kid_top()` + `arm()`/`limb()` and blind-test it (`reference/model-tiers.md`).
- **Scenes.** Start from a `lib/scenes.py` kit and place figures on its declared ground
  line; add your own midground anchor — kit anchors add depth but do not fill the middle
  band.
`reference/library-guide.md` tours each library area (line vocabulary, letters, scene
kits, creativity layer, photo mode) with the calls that matter.

### 4. Validate, then look
Run the DETERMINISTIC gate first: `python3 -m lib.validate pages/*.svg` (exit 1 on any
HIGH). It checks, with exact arithmetic on the emitted SVG: border clearance (≥12 px),
scene extent (HIGH when the non-sky scene spans < 330 px or floats above y880 — sky
tokens and lone thin strokes don't count), mass distribution (MED when the middle band
y430-715 is hollow — add a midground anchor whose top reaches y≈450-550), figure/face
sizes, caption-band + title-zone intrusion, text width, head-kill-radius prop
clearance, hand/arm overlap, wheel ground tangency, near-parallel sliver gaps,
knockout-mat halo swallowing, duplicate pages and density pacing
(`lib.validate.lint_book`). Fix every HIGH by moving/scaling per the message; MEDs need
a look; LOWs are lint. Non-scene pages opt out of the extent and mass rules via
`spage(..., layout="activity")` (name tracing / find-the-X), `"creative"`, or
`"vignette"` (back cover). Report the validator's numbers, never estimates.

Then Read every page PNG yourself and fix obvious collisions/floaters. Then run tile
QA: `render_tiles(svg, qa_dir, name)` per page and have vision-capable reviewer
subagents (Sonnet-class or stronger, one per page, if the Agent tool is available)
review the overlapping tiles for: unintended overlapping lines, tangent-line /
figure-ground illusions where background contours touch figures, floating or
disconnected parts, out-of-proportion elements, ambiguous shapes (ask "what is this
animal doing?" with no caption), eerie facial expressions, elements cut off, objects
partially ERASED by a neighbour's matting halo (the validator catches FULL erasure;
partial nibbles still need eyes), text crossing the border; severity-tagged findings.
Apply fixes, re-render, re-run `lib.validate`, re-verify the pages that had HIGH
findings. 1-2 fix rounds is normal; if the SAME defect survives two attempts, use the
escalation ladder in `reference/model-tiers.md` and say so in the report.

### 5. Deliver
Merge to PDF via `build()` (cairosvg + ghostscript). Report the PDF path, page list,
which traits distinguish each character, and any compromise you shipped. If the user
has a family share, offer to copy there.
