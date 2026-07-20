# Drawing guide — line-art rules & hard-won gotchas

## Age-band tuning
| Age | main stroke | elements/page | notes |
|---|---|---|---|
| 3-4 | SW=5-6 | 5-10 | big shapes, subject fills 40-60% of page, minimal background |
| 5-6 | SW=4-5 | 8-14 | simple patterns/expressions OK, moderate backgrounds |
| 6-7 | SW=4 | 10-20 | small details (freckles, seeds, shingles) fine |
charlib default SW=5 suits the 3-6 middle. Detail strokes 2.5-3.5.

## Collision gotchas (every one of these bit us in production)
1. **Heads are drawn LAST** in figure helpers with white fill — any raised hand, prop, or
   line within ~1.3*r of the head center gets silently covered. Keep grip-hands and props
   offset well outside the hair silhouette (hands at |x| ≥ 1.5*r from head center).
2. **Never mirror with a negative uniform scale** (`G(..., scale=-1)` renders upside-down).
   Use `GM()` (flips x only).
3. **Hand circles must overlap their arm-line ends** — a 2px gap reads as a floating bubble.
4. **Ropes/webs/leashes must end AT the hand circle** — compute the global position:
   `global = (figure_x + local_x*scale, figure_y + local_y*scale)`.
5. **Adjacent rectangles (windows) must not overlap** — overlapping strokes render as solid
   black slabs. Keep ≥4px gaps.
6. **Text in burst stars**: font-size ≤ 0.4 × star radius or it overflows the points.
6b. **Text in any banner/box**: DejaVu Sans runs ≈ 0.55 × font-size per character (bold ≈ 0.62).
   Container width must be ≥ text width + 2×18px padding — compute it, don't eyeball it
   (a 29-char name banner at 24px needs ≥ 420px, not 340).
6c. **Text in organic shapes (hearts, bursts, clouds)**: measure the shape's interior
   width AT THE TEXT'S y, not its widest point — a heart narrows fast above and below
   its lobes. Proven combo for back covers: heart s≈210 with "The End!" at ≤52px bold.
7. Background objects (sun, clouds, bunting) collide with tower/flag/head tops — check the
   sky lane before placing. Sun rays extend r+32 beyond the disc.
8. Anchor everything to a ground line or tuft — floating animals/objects get flagged by kids
   and reviewers alike. Two short paired marks read as "eyes" on buildings — offset vents.
9. Standing figures: feet origin y=0; place with G(x, ground_y, ...). Caption band is below
   y≈1000 — keep art above it.
10. Keep every element ≥12px inside the border rect (x 28-822, y 28-1072).

## Tangent lines & figure-ground illusions
When a background contour (rug, path, fence rail, furniture edge) passes tangent to or
touches a foreground contour (a leg, a dress hem), the shapes visually fuse and confuse.
Two defenses, use both:
1. **Wrap every foreground figure/object in `matted(inner, pad=9)`** after drawing the
   background — it knocks a white halo out of everything behind the figure, so tangency
   is impossible by construction. Draw order: ground/rug → furniture (matted if over rug)
   → figures (matted).
2. Even with matting, don't run a closed background shape (full rug ellipse) through a
   crowd — prefer partial arcs behind groups, and keep ≥14px designed clearance between
   unrelated contours.

## Friendly faces (anti-eerie rules)
The eerie combo is: eyebrows close above dot eyes (reads scheming) + a wide flat smile
arc (reads smirk). charlib `face()` defaults now encode the fixes — keep them:
- **No eyebrows by default** (`brows=False`). If used, they sit HIGH above the eyes.
- Smile is a **narrow deep U** (width ≤ 0.48*r), never a wide flat arc.
- `mouth="open"` (closed D-shape) for celebration pages — unambiguously joyful.
- Small open **cheek circles** (colorable blush) add warmth; auto-suppressed with freckles.

## Everyday objects — use the cookbook, don't freehand
For any real-world object (vehicles, houses, trees, animals, playground gear),
call a `charlib` helper if one exists (`car_side`, `bicycle`, `tractor`,
`train_engine`, `pickup_truck`, `house`, `tree_round`, `tree_pine`, `horse`,
`bird_side`, `swing_set`, ...); otherwise follow the relative-proportion recipes
in `reference/shape-cookbook.md`. Never guess raw coordinates for object geometry —
that is exactly where line-art goes wrong (floating wheels, unequal bike wheels,
roofs that don't overhang). Side-profile objects face right; mirror with `GM()`.

## Composition
- **Numeric layout check (run it, don't eyeball)**: scene bbox spans ≥55% of page height
  (top ≤450, bottom ≥900); every element ≥12px inside the border; main figures ≥180px
  tall; faces r≥28 or trait features crowd. Every model bottom-crams first drafts —
  plan the vertical layout BEFORE drawing (see reference/model-tiers.md).
- Whole-page layout: title y≈100, scene y≈150-950, caption y≈1038, page number bottom.
- Fill the middle band — a fence at the top and kids at the bottom with 300px of empty
  space between reads as unfinished; add a barn/tree/path/mid-ground element.
- Even icon distribution on cover/back; balance sparkle density left/right.
- Name labels under figures (24px, weight normal) on the intro page help parents.

## Print
- `build()` renders letter-size vector PDF (612x792pt) — never rasterize pages.
- One page per builder function; BUILDERS list + argv substring filter = partial rebuilds.

## Costumes, facial accessories & props on figures (lessons from user pushback)
- **Never stroke across the face interior.** An accessory edge crossing the face gets
  read AS a facial feature (a beard's inner arc reads as a giant grin no matter how
  small the real mouth is). Beards hang UNDER the jaw (see charlib `face(beard=True)`);
  glasses/masks are the only sanctioned face-crossing shapes.
- **One silhouette + at most two accents per costume overlay.** A bib apron = one
  outline + waist line + one low pocket. Stacking strap + bib + bow + pocket + tool on
  a small chest reads as clutter every time.
- **Props must match their iconic silhouette** (a chef toque = straight band + mushroom
  puff overhanging it; wider than tall). If a prop needs a caption to identify it, redraw it.
- **Face clearance is numeric:** no prop/held-item center within 1.3×r of any face
  center (a gift held "up" drifts onto the face — the caption said hand, the render said face).

## Foliage & structures in trees
- Big canopies need TEXTURE: scallops along the outer rim + scattered inner leaf marks.
  Bare overlapping circles read as balloons. Keep inner marks ASYMMETRIC — two marks at
  the same height read as a pair of eyes.
- A structure in a tree sits BELOW/BESIDE the foliage with visible support (fork of
  branches, platform planks) — a house floating inside a leaf blob drowns.
- Ladders/ropes attach beside the trunk, never overlapping it (rails over the trunk
  crowd out its silhouette).
