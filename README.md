# coloring-book — a Claude Code skill for personalized kids' coloring books

Give it your kids' names, hair, glasses, freckles, pets, and favorite things — get back a
printable, letter-size vector PDF coloring book starring them. Themed pages ("their
favorite things") or **story mode** for ages 3-6 (a gentle 10-beat quest with captions
built for pre-readers: simple present tense, name repetition, a chant-along refrain).

<p align="center">
<img src="examples/where-is-button/pages/01-cover.png" width="30%"> <img src="examples/where-is-button/pages/06-search-living.png" width="30%"> <img src="examples/where-is-button/pages/08-solve.png" width="30%">
</p>

*The bundled example, "Where Is Button?" — a fictional family's teddy-bear hunt,
built end-to-end by the skill.*

## Why it works (design choices)

- **Parametric characters, not AI likeness.** Each child is a small trait vector
  (hair silhouette, glasses, freckles, height, a personal motif). Same recognizable
  kid on every page, zero identity drift, no photos needed or wanted.
- **Everything is bold vector line art** (SVG → PDF), tuned to age-band line weights.
  No diffusion raster output, no broken gray lines.
- **A shape library instead of freehand geometry.** LLMs reliably botch bicycles and
  side-view cars; the skill ships 200+ object helpers indexed by interest in
  [`reference/catalog.md`](reference/catalog.md) — vehicles, trains, boats, space, farm
  and wild animals, buildings, playground gear, people in run/jump/point/carry/sleep
  poses, a wheelchair user — plus relative-proportion recipes for anything else
  (derived from public-domain 1910s drawing pedagogy and MIT-licensed icon skeletons —
  see [CREDITS.md](CREDITS.md)).
- **Scene kits and a composition recipe.** `lib/scenes.py` gives proven backgrounds
  (meadow, street, beach, space, farm) with declared ground lines; the drawing guide's
  three-layer recipe (background kit → midground anchor → foreground figures at
  300-380 px) is what keeps pages from reading bottom-crammed.
- **Deterministic validation gate.** `python -m lib.validate pages/*.svg` turns every
  numeric layout rule into exact arithmetic on the emitted SVG — border clearance,
  scene span, **mass distribution** (a hollow middle third or a sky-only top is
  flagged even when the bounding-box arithmetic passes), figure and face sizes, head
  clearance, mat-swallowing, ground tangency, text fit — and fails on HIGH findings.
- **Machine-independent renders.** All page text (titles, captions, page numbers) is
  drawn as glyph paths from the bundled Andika literacy font, so the same SVG renders
  identically on any machine and the PDF embeds no system font. Hollow letters for
  tracing pages are overlap-free with a colorable body.
- **Anti-tangency matting** (`matted()`) knocks white halos out of backgrounds around
  figures, so rug lines can't visually fuse with dress hems.
- **Creativity layer**: finish-the-symmetry and finish-the-picture pages, blank speech
  bubbles, pattern menus, design-your-own templates, sticker sheets — pages that invite
  the child's own art.
- **Tile-based QA loop**: pages are re-rendered as overlapping zoom tiles and reviewed
  (by vision-capable subagents when available) for collisions, floaters, and ambiguous
  shapes.
- **Model-tier aware**: the skill tells weaker models to run in a conservative
  helpers-only mode and when to escalate — calibrated by benchmarking the same build
  across model tiers ([`reference/model-tiers.md`](reference/model-tiers.md)).
- **Photo mode** (`lib/photolib.py`) traces a photo into colorable outlines, fully
  local (OpenCV + a bundled Apache-2.0 face model). It is honest about its limits:
  best on a single high-contrast subject in `sketch` style; interiors and textured
  backgrounds still trace noisily. See [`reference/photo-guide.md`](reference/photo-guide.md).

## Install

```bash
git clone https://github.com/bedardandy/coloring-book-skill ~/.claude/skills/coloring-book
pip install -r ~/.claude/skills/coloring-book/requirements.txt
```

Rendering needs `cairosvg` (installed above) and Ghostscript (`gs`) for the final PDF
merge. Then in Claude Code: `/coloring-book` — or just ask for "a coloring book for my
kids".

## Try the example

```bash
cd examples/where-is-button
python3 make_book.py          # full book -> Harper-Coloring-Book.pdf
python3 make_book.py 05       # rebuild just page 5
python3 -m lib.validate examples/where-is-button/pages/*.svg   # from the repo root
```

`python3 tools/showcase.py` renders one page per content pack into
`examples/showcase/pages/` and validates each — a fast visual smoke test of the whole
library.

## Layout

- `SKILL.md` — the skill workflow (cast setup → plan → render → validate → QA → deliver)
- `lib/charlib.py` — the drawing library: primitives, curve engine, motifs, parametric
  faces/figures, animals, furniture, vehicles, letters, creativity pages, page/PDF assembly
- `lib/scenes.py` — scene kits with declared ground lines
- `lib/validate.py` — the deterministic page validator and book linter
- `lib/photolib.py` — photo-to-outline tracing
- `reference/drawing-guide.md` — collision gotchas, age-band rules, composition recipe
- `reference/story-mode.md` + `reference/story-tropes.md` — the 10-beat arc and 18 story
  structures for ages 3-6
- `reference/shape-cookbook.md` — relative-proportion recipes for everyday objects
- `reference/catalog.md` — every helper, indexed by interest (auto-generated)
- `reference/model-tiers.md` — operating modes and escalation ladder by model capability
- `tools/` — showcase renderer, catalog generator, font baker, photo evaluation, PII gate
- `tests/` — pytest suite (run `pytest -q -m "not slow"`; `-m slow` builds the example book)

CI runs the PII gate, the fast tests, the photo-pipeline evaluation gate, and (on push)
the full example build + validation. See [CHANGELOG.md](CHANGELOG.md) for what changed
when.

## License

- **Code** (`lib/`, `tools/`, `tests/`, `examples/`): [AGPL-3.0-or-later](LICENSE).
  Chosen deliberately: this is a for-fun community project, and AGPL means anyone who
  builds a service on it must share their improvements back. Personal and family use is
  completely unencumbered.
- **Documentation and recipes** (`SKILL.md`, `reference/`): CC BY-SA 4.0.
- Upstream reference material and its licensing: [CREDITS.md](CREDITS.md).

Photos of real children never belong in this pipeline — the skill extracts trait
*buckets* ("short hair, glasses") at most, and works fine with none.

## Using this outside Claude Code (other agents / LLMs)

The skill is plain markdown + Python, so any agent can use it — but three things are
non-negotiable, and skipping them is why hand-rolled attempts come out rough:

1. **Execute `lib/charlib.py`** (Python + `cairosvg` + Ghostscript). Do not re-implement
   the helpers "in the spirit of" the library — the geometry is battle-tested and the
   helpers do ordered white-fill layering internally.
2. **White fills, back-to-front.** Every solid shape is drawn with `fill="white"` over
   what's behind it, in depth order, and figures get `matted()` halos. Outline-only
   drawing produces transparent shapes whose strokes all cross each other.
3. **Run the validator** (`python -m lib.validate pages/*.svg`) after every build and
   fix what it reports by moving or scaling elements. Every model bottom-crams first
   drafts; arithmetic catches it when eyeballing doesn't.

If your environment can't run Python, the honest move is to say so rather than
approximate — the output difference is not subtle.
