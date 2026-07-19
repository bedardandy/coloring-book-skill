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
Plan page-type variety: cover, name-tracing page (large outline letters of the kids' names),
scene pages, one find-the-X activity page, back cover ("Made with love for ...").

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
(`car_side`, `pickup_truck`, `tractor`, `train_engine`, `bicycle`, `house`,
`tree_round`, `tree_pine`, `horse`, `bird_side`, `swing_set`, plus `dog`,
`cat_sitting`, `dino`, `couch`, `bed`, `armchair`); if none fits, follow the
relative-proportion recipes in `reference/shape-cookbook.md` and build the object
from primitives at your chosen scale. Wrap each placed object in `matted()` over any
background. See `CREDITS.md` for the recipes' provenance.

### 4. Self-inspect + QA loop
After building, Read every page PNG yourself and fix obvious collisions/floaters. Then run
tile QA: `render_tiles(svg, qa_dir, name)` per page and review the overlapping tiles (spawn
sonnet subagent reviewers if the Agent tool is available, one per page, prompt them for:
unintended overlapping lines, tangent-line/figure-ground illusions where background
contours touch figures, floating/disconnected parts, out-of-proportion elements,
ambiguous shapes, eerie/off-putting facial expressions, elements cut off;
severity-tagged findings). Apply fixes, re-render, and
re-verify the pages that had HIGH findings. 1-2 fix rounds is normal.

### 5. Deliver
Merge to PDF via `build()` (cairosvg + ghostscript). Report the PDF path, page list, and
which traits distinguish each character. If the user has a family share, offer to copy there.
