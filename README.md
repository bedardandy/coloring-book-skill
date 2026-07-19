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
- **A shape cookbook instead of freehand geometry.** LLMs reliably botch bicycles and
  side-view cars; the skill ships ~20 object helpers plus relative-proportion recipes
  (derived from public-domain 1910s drawing pedagogy and MIT-licensed icon skeletons —
  see [CREDITS.md](CREDITS.md)).
- **Anti-tangency matting** (`matted()`) knocks white halos out of backgrounds around
  figures, so rug lines can't visually fuse with dress hems.
- **Tile-based QA loop**: pages are re-rendered as overlapping zoom tiles and reviewed
  (by subagents when available) for collisions, floaters, and ambiguous shapes.
- **Model-tier aware**: the skill tells weaker models to run in a conservative
  helpers-only mode and when to escalate — calibrated by benchmarking the same build
  across three model tiers.

## Install

```bash
git clone <this-repo> ~/.claude/skills/coloring-book
```

Then in Claude Code: `/coloring-book` — or just ask for "a coloring book for my kids".

Rendering needs `cairosvg` (`pip install cairosvg`) and Ghostscript (`gs`) for the
final PDF merge.

## Try the example

```bash
cd examples/where-is-button
python3 make_book.py          # full book -> Harper-Coloring-Book.pdf
python3 make_book.py 05       # rebuild just page 5
```

## Layout

- `SKILL.md` — the skill workflow (cast setup → plan → render → QA → deliver)
- `lib/charlib.py` — the drawing library: primitives, motifs, parametric faces/figures,
  animals, furniture, vehicles, page/PDF assembly, QA tile renderer
- `reference/drawing-guide.md` — collision gotchas and age-band rules, learned in production
- `reference/story-mode.md` — the 10-beat arc + caption rules for ages 3-6
- `reference/shape-cookbook.md` — relative-proportion recipes for everyday objects
- `reference/model-tiers.md` — operating modes and escalation ladder by model capability

## License

- **Code** (`lib/`, `examples/`): [AGPL-3.0-or-later](LICENSE). Chosen deliberately:
  this is a for-fun community project, and AGPL means anyone who builds a service on it
  must share their improvements back. Personal and family use is completely unencumbered.
- **Documentation and recipes** (`SKILL.md`, `reference/`): CC BY-SA 4.0.
- Upstream reference material and its licensing: [CREDITS.md](CREDITS.md).

Photos of real children never belong in this pipeline — the skill extracts trait
*buckets* ("short hair, glasses") at most, and works fine with none.
