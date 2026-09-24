# Library guide — what `lib/` gives you, by area

Read this when you need the call, not the rule. The rules live in
`drawing-guide.md`; every helper's signature is in `catalog.md`
(auto-generated — re-run `python3 tools/gen_catalog.py` after adding helpers);
`python3 tools/showcase.py` renders one page per area into
`examples/showcase/pages/` and validates each.

## Line quality (prefer these over hand-drawn Q-chains)
`smooth_path(pts, closed=True)` (G1-continuous organic silhouettes), `limb()`
(tapered two-segment arm/leg outline through shoulder→elbow→wrist with a tagged
hand circle at an exact wrist target), plus a line vocabulary: `wavy_line`,
`zigzag_line`, `scallop_edge`, `stitch_dash`, `hatch_region` (ellipse hatching),
`echo` (double-contour aura around convex motifs). Kid figures and dog/cat are
smooth rebuilds whose wrist targets match the legacy coordinates, so prop anchors
keep working; `use_legacy_figures(True)` restores the old wire-limb geometry.

## Figures and poses
Stock kids: `kid_stand(t, pose="wave"|"up"|"down"|"hold")`, `kid_sitting`,
`kid_reach`, `kid_run`, `kid_jump`, `kid_point`, `kid_carry`, `kid_toddler`,
`kid_wheelchair`, `kid_in_bed`, `kids_holding_hands`; accessories `cap`, `cape`,
`scarf`; faces via `face_traits(cx, cy, r, t)`. Pets: `dog` (stand), `dog_sit`,
`dog_sleep`, `dog_dig` (rump up, paws in a hole, dirt flying), `cat_sitting`.
Custom poses (strong tier only): compose from the PUBLIC parts `kid_top(t)` (head +
torso + legs, no arms; returns `(parts, shoulders, head_y)`) and `arm(shoulder,
wrist)` / `limb(...)` — never re-implement the figure. Test any custom pose with
blind raters (`model-tiers.md`).

## Text, letters and words (Andika OFL outlines baked to paths)
All page text — `TXT()`, titles, captions, page numbers — is drawn as glyph paths via
`text_path()`, so renders are identical on every machine and the PDF embeds no system
font. Captions wrap by measured width (`wrap_width`, `text_width`); a wide one-line
caption lifts off the page-number baseline automatically. `charlib.TEXT_MODE = "font"`
reverts to legacy `<text>` elements.
Colorable letters: `letter()` / `word()` / `word_width()` / `banner(text, cy)`
(ribbon auto-sized from glyph metrics — text-in-box overflow is impossible) /
`name_trace_page(["Name", ...])` (ruled guidelines + dashed trace-style letters +
start stars). Hollow letters are overlap-free with a thick colorable body (`body=`
em fraction, default 0.07; `body=0` gives the thin outline) and open counters.
Accented Latin names (é, ñ, Ł…) render; a missing glyph falls back to its base letter.

## Scene kits (`lib/scenes.py`) and landscapes
`scene_meadow / scene_street / scene_beach / scene_space / scene_farm` return proven
background layers (sky lane, ground systems, props) and document their ground line
(`SCENE_GROUND`, `BEACH_GROUND`, `SPACE_GROUND`) — start pages from a kit, then add a
midground anchor of your own and figures on the declared ground. Kits take `variant=N`
for deterministic variety and `midground=True`. Landscape systems: `hill,
mountain_range, road (+ROAD_H), rail_track, fence_picket/ranch, pond, beach_shore,
forest_border, skyline, bridge`. Wrap your own sky decoration in `sky(fragment)` so
the validator excludes it from scene mass.

## Interest packs
200+ object helpers across vehicles, trains, air, boats, space, flowers/garden, wild
animals, farm, pets, games, buildings, structures, props and costumes — find them by
interest in `catalog.md`. Every side-profile object faces right; `GM()` flips it.
Wrap each placed object in `matted()` over any background.

## Creativity layer (pages that invite the child's own art)
Blank `speech_bubble` / `thought_bubble` (pass `speaker_top=(x, head_top_y)` and the
tail ends 20 px above the head — never guess bubble coordinates), `symmetry_page(motif,
size=)` (left solid, right dotted hint, motif ~60% of page width), `finish_page(kind)`
(dashed ghost to complete), `pattern_menu` (swatch strip kids copy onto blank bands),
`design_template(kind)` (blank tee/cake/rocket), `sticker_sheet(motifs)` (dashed cut
cells; motifs auto-fit to ~70% of each cell). To size any fragment into a box, measure
it: `fragment_bbox(frag)` / `fit_fragment(frag, cx, cy, w, h, anchor="bottom")`
(`restroke` keeps line weight when scaling). Mark such pages `spage(...,
layout="creative")` so the validator knows open composition is intentional.

## Photo mode (`lib/photolib.py` — photos in, coloring outlines out)
`photo_to_svg(photo, style="clean"|"sketch", detail="low|medium|high")` traces a photo
into colorable line art (flow-coherent extraction, anti-splinter morphology, contour
averaging, angle snapping for architectural subjects, region-floor QA loop).
`photo_to_fragment` returns a feet-anchored `G()`-placeable asset; `composite_page(photo,
scene_body, ground_y, x=, scale=)` stands the traced subject in a scene kit beside
charlib characters. Subject policies (face/car/house/animal…) are SOFT rules — the QA
loop adjusts them. Honest limits (2026-09): best on ONE high-contrast subject in
`sketch` style; interiors, fences and grass trace as noise and `clean` can double
contours. Say so to the user instead of shipping a noisy trace. All processing is
local; the bundled YuNet face model (Apache-2.0) never phones home. See
`photo-guide.md`.

## Page assembly and QA
`spage(title, body, num=, caption=, layout=)` / `page(...)` build a page; `build(BUILDERS,
outdir, only=, pdf_name=)` renders SVG/PNG/PDF per page and merges with Ghostscript;
`render_tiles(svg, qa_dir, name)` makes overlapping crops for reviewers; `qa_page(svg)`
counts uncolorable slivers and asserts print-safe stroke widths;
`python3 -m lib.validate pages/*.svg` is the deterministic gate;
`lib.validate.lint_book(svgs)` catches duplicate pages and density pacing.
