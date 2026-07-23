# Shape cookbook — recipes for everyday objects

LLMs reliably botch the geometry of cars, bikes, houses, and animals when
improvising coordinates. Don't. For any object here, follow the recipe: build it
from `charlib` primitives (`P C E LINE rrect DOT`) using the **relative
proportions** given, then place/scale it with `G(x, y, inner, s)`. Proportions
are the point — pick any pixel width `W` and a ground line, and derive every
number from them. Never dump raw coordinates you guessed.

If a `charlib` helper already exists (`car_side`, `bicycle`, `train_engine`,
`tractor`, `tree_round`, `tree_pine`, `horse`, `bird_side`, `swing_set`,
`house`, `dog`, `cat_sitting`, `dino`, `couch`, `bed`, `armchair`),
call it — it's already tuned. Recipes below cover both the helpers (so you can
extend them) and objects with no helper yet.

## How to read a recipe
- **W** = object footprint width; **H** = height; **g** = ground line (y that
  wheels/feet/hull sit ON). All fractions are of W unless noted.
- Primitives listed in DRAW ORDER (background parts first, white-filled caps
  last, exactly like the figure helpers). Every closed shape uses `fill="white"`
  so overlaps knock out cleanly. Main strokes SW 4.5–5, detail 2.5–3.5.
- Relational notes are load-bearing — they encode the tangencies and alignments
  that make the object read. Obey them over your instinct.
- Side-profile vehicles/animals face RIGHT by convention; mirror with `GM()`.

---

## Vehicles (all wheels TANGENT to the shared ground line g)

### car_side  (W wide, wheels r=0.11W)
1. Body: rounded rect, x[0..W], top at g−0.42W, bottom at g−0.13W (wheel hub line).
2. Cabin: rounded trapezoid on the body top, x[0.28W..0.72W], rising to g−0.62W;
   roof shorter than base (windshield + rear slope).
3. Two windows: rects inside cabin, ≥0.03W gap between them and from posts.
4. Wheels: two circles r=0.11W, centers at 0.22W and 0.78W, on g (bottom touches g).
5. Wheel hubs: small concentric circle r=0.4×wheel.
- Wheels sit BELOW the body — hub centers at g−r, so tyres are tangent to g.
- Cabin sits toward the REAR half; hood is the lower front stretch to 0.28W.

### pickup_truck  (W wide, wheels r=0.11W)
1. Cab: tall rounded rect front, x[0.52W..0.96W], top g−0.55W (with a window).
2. Hood: short lower rect ahead of cab is optional — pickups have a stubby nose.
3. Bed: lower open rect behind cab, x[0.04W..0.52W], top g−0.30W (shorter than cab).
4. Bed wall: thin vertical line at the cab/bed seam.
5. Wheels: r=0.11W at 0.20W and 0.80W on g; hubs.
- Cab is clearly TALLER than the bed — the height step is the whole read.
- One wheel under the bed, one under the cab.

### tractor  (W wide)
1. Rear wheel: BIG circle r=0.24W, center at 0.72W, on g. Add 4–5 spoke ticks.
2. Front wheel: SMALL circle r=0.12W, center at 0.20W, on g.
3. Body/hood: rect from front axle up-and-back to the seat, top ~g−0.34W.
4. Cab post + seat: short backrest rising to g−0.5W above the rear axle.
5. Exhaust: short vertical stub on the hood.
- Big rear wheel + small front wheel is the entire silhouette — exaggerate the
  size difference. Both tangent to g.

### train_engine  (steam loco, W wide)
1. Boiler: long rounded rect (cylinder), x[0.10W..0.66W], centered at g−0.34W.
2. Cab: taller rounded rect at rear, x[0.66W..0.98W], top g−0.60W, with a window.
3. Cowcatcher: triangle at front, x[0..0.10W] sloping down to g.
4. Smokestack: short flared rect on the boiler front top (g−0.60W), + puff cloud.
5. Dome: small bump on the boiler mid-top.
6. Wheels: 2–3 circles r=0.10W along g under the boiler + one big driver r=0.14W.
7. Chassis bar: thin rect just above the wheels linking them.
- Cab (rear) is tallest; boiler is a long low cylinder; cowcatcher wedges to g.
- All wheels tangent to g; the big driver wheel sits under the cab.

### bicycle  (W wide, TWO EQUAL wheels — the classic LLM failure)
1. Rear wheel: circle r=0.22W, center at 0.22W, on g.
2. Front wheel: circle r=0.22W (IDENTICAL), center at 0.78W, on g.
3. Frame: a triangle joining rear hub → seat (top, ~g−0.5W) → pedal-center
   (bottom, midway between hubs at g−0.22W) → back to rear hub.
4. Head tube: line from pedal-center up-forward to the front hub top / handlebars.
5. Seat: short flat bar at the frame's top vertex.
6. Handlebars: short line above the front wheel, angled up-back toward the rider.
7. Pedals: small circle at pedal-center + two stub cranks.
- BOTH wheels the same radius, both tangent to g. Hub-to-hub spacing ≈ 2.5×r.
- Frame is a clear diamond/triangle strung BETWEEN the hubs — never a blob.

### sailboat  (W wide, waterline at g)
1. Hull: shallow trapezoid/banana, x[0.05W..0.95W], top at g−0.12W, bottom dips to g.
2. Mast: vertical line from deck center (0.42W) up to g−0.85W.
3. Mainsail: triangle, mast (vertical edge) → out to 0.80W at deck → back to masthead.
4. Jib: smaller triangle forward of the mast (mast → bow 0.10W → up ~0.55W).
5. Water: 2–3 shallow wave arcs under the hull along g.
- Sails are triangles hung off the mast; hull is a shallow smile on the water.
- Mast sits just forward of hull center; mainsail fills the aft triangle.

### rowboat  (W wide, waterline at g)
1. Hull: shallow banana — arc from bow 0 up over to stern W, top rim at g−0.14W,
   belly dipping to g at center.
2. Rim line: second arc just inside the top for the gunwale.
3. Thwarts: 1–2 short seat lines across the hull.
4. Oars: two lines angling out over the rim to blades (small ellipses) at the water.
5. Water: wave arcs along g.
- No mast. Symmetric bow/stern. Oars cross the rim, blades touch the water line.

---

## Buildings

### house  (W wide, wall bottom on g)
1. Walls: rect x[0.05W..0.95W], from g up to g−0.55W (eave line).
2. Roof: triangle, eaves at 0..W (overhang past walls), apex centered at g−0.95W.
3. Door: tall rounded rect, centered or 0.35W, from g up to g−0.32W; + knob dot.
4. Windows: 1–2 square panes with a + mullion, ≥0.04W clear of door and corners.
5. Chimney: thin rect on one roof slope, top above the roof apex line.
- Roof overhangs the walls both sides; apex is the tallest point.
- Door sits ON g; windows float at mid-wall, never touching the roof or door.

### barn  (W wide, wall bottom on g)
1. Walls: tall rect x[0.08W..0.92W], g up to g−0.55W.
2. Gambrel roof: 4-segment polygon — eave → knee (g−0.72W, near full width) →
   apex (g−0.95W, centered) → knee → eave. (Two pitches per side.)
3. Big doors: large rounded rect centered, g up to g−0.42W, with a center split line.
4. Cross-brace: an X of two lines on the doors.
5. Hayloft window: small square/diamond high on the gable under the apex.
- The gambrel (barn) roof has a shallow top pitch and steep lower pitch — that
  double-angle silhouette is what says "barn," not "house."

---

## Trees

### tree_round  (H tall, trunk base on g)
1. Trunk: short rect, width 0.18H, from g up to g−0.28H.
2. Canopy: big circle (or 3-lobe cloud) r=0.34H, center at g−0.62H, sitting on the
   trunk top; overlap the trunk by ~0.05H so no gap.
- Canopy is a fat lollipop; trunk is stubby. Canopy widest part ≈ 1.4× trunk height.

### tree_pine  (H tall, trunk base on g)
1. Trunk: short rect width 0.12H, g up to g−0.14H.
2. Tier 1 (bottom): wide triangle, base 0.7H wide at g−0.14H, apex at g−0.5H.
3. Tier 2 (middle): narrower triangle, base 0.55H, sitting overlapping tier-1 apex.
4. Tier 3 (top): narrowest triangle, apex at g−1.0H (the treetop).
- 3 stacked triangles, each narrower and higher, each overlapping the one below;
  trunk peeks out the bottom.

---

## Animals (side view, facing right, feet on g — reuse dog()'s leg pattern)

### cat_side  (W long, feet on g)
1. Body: horizontal ellipse/rounded blob, ~0.7W long, top at g−0.5W.
2. 4 legs: short vertical lines g−0.22W → g at x = 0.15/0.35/0.6/0.8 W, + paw ticks.
3. Tail: thin S-curve rising off the rear (0.05W) up to g−0.55W.
4. Head: circle r=0.16W at the front (0.85W), overlapping the body front.
5. Ears: two small triangles on the head top.
6. Face: two dot eyes, nose dot, whisker lines (3 per side).
- Cat body is LOW and long; legs short; upright tail. Head small and round.

### horse  (Lutz side view — reuse dog() legs/anchors; W long, feet on g)
1. Body: large ellipse, ~0.55W long, centered at 0.45W, top at g−0.62W.
2. 4 legs: lines g−0.4W → g, paired (front pair ~0.3W, back pair ~0.62W), + hoof ticks.
3. Neck: broad tapered quad rising forward from the body front (0.7W) up-right.
4. Head: elongated ellipse (muzzle) at the neck top (0.86W, g−0.78W).
5. Ears: two short triangles on the head top.
6. Mane: short zigzag/scallop line down the back of the neck.
7. Tail: curved sweep off the rear (0.15W) down to g−0.15W.
8. Face: dot eye, nostril dot on the muzzle.
- Tall at the shoulder, long straight legs, arched neck, long head. Legs are the
  Lutz "four posts under a barrel." Mane and tail flow the same direction.

### bird_side  (W long, perched, feet on g)
1. Body: egg-shaped ellipse, 0.6W long, tilted, top at g−0.5W.
2. Head: circle r=0.2W overlapping the body front-top (0.75W, g−0.6W).
3. Beak: small triangle off the head front pointing right.
4. Wing: a leaf-shaped arc on the body side (one curved P, tucked).
5. Tail: two short lines/triangle off the body rear pointing back-down.
6. Legs: two short lines g−0.12W → g + tiny toe ticks; body sits just above.
7. Eye: dot on the head.
- Round head + egg body + short beak + up-cocked tail. Perch feet on g.

### fish  (W long, swimming right, centered on a mid-line m)
1. Body: pointed ellipse (teardrop), 0.72W long, nose at 0.72W, tallest 0.3W near front.
2. Tail: triangle at the rear (0..0.28W), notched (fishtail) — apex forward at body.
3. Top + bottom fins: small triangles on the body mid.
4. Gill: one short curved line behind the head.
5. Eye: dot near the nose (0.62W); optional smile arc.
- Body is a teardrop point-forward; tail is a notched triangle behind it. No ground
  line — floats on the page mid-line m.

---

## Playground & furniture

### swing_set  (W wide, feet on g)
1. Left A-frame: two lines from apex (0.14W, g−0.9W) splaying to g at 0.02W and 0.26W.
2. Right A-frame: mirror at 0.86W.
3. Top beam: horizontal line joining the two apexes at g−0.9W.
4. Swing ropes: two parallel vertical lines from the beam center down to g−0.22W.
5. Seat: short flat bar (rrect) across the rope bottoms.
- Two A-frames + a beam + a hanging seat. Rope pair stays parallel; seat bar
  bridges them. A-frame feet tangent to g.

### slide  (W wide, feet on g)
1. Ladder legs: two lines at 0.08W/0.20W from g up to the platform (g−0.55W).
2. Rungs: 3–4 short horizontal lines between the ladder legs.
3. Platform: short flat top at g−0.55W.
4. Slide surface: a curved line (P) sweeping from the platform down-right to g at 0.95W.
5. Slide side rail: a parallel curve just above the surface (the lip).
- Ladder rises on the left, slide sweeps down to the right, both meeting at the
  platform. Slide bottom flattens as it touches g.

### table_chair  (W = table width, tops relative to g)
1. Tabletop: flat rect (slab) at g−0.5W, x[0..W].
2. Table legs: two vertical lines from the slab ends down to g (or 4 with inner pair).
3. Chair seat: rect at g−0.30W beside the table, ~0.35W wide.
4. Chair back: two verticals + a top rail rising from the seat rear to g−0.6W.
5. Chair legs: verticals from the seat corners to g.
- Everything stands ON g; chair seat lower than the tabletop; back taller than table.
- Keep chair legs and table legs ≥0.05W apart so strokes don't merge into a slab.
</content>
</invoke>

## Priority skeleton sources for future helpers (surveyed 2026-07)

When adding new objects, these permissively-licensed assets were measured as clean
skeletons (low path counts, no transform soup). Use as PROPORTION REFERENCE and
redraw in charlib idiom — do not paste path data. Twemoji: use the maintained
`jdecked/twemoji` repo (main branch), NOT the archived `twitter/twemoji` (stale,
serves wrong content for some glyphs, lacks post-2022 assets).

Top gaps worth building, best-first (source · elements):
1. excavator — phosphor-icons/core raw/regular/bulldozer.svg (MIT, 6 stroke elements,
   already in our visual style; also crane.svg)
2. rocket — jdecked/twemoji 1f680.svg (6)   3. elephant — 1f418.svg (3)
4. fire truck — 1f692.svg (~10; police 1f693 / ambulance 1f691 share the body kit)
5. rainbow — 1f308.svg (6 arcs)             6. present — 1f381.svg (5)
7. pumpkin — 1f383.svg (3)                  8. airplane — 2708.svg (5)
9. giraffe — 1f992.svg (~5)                 10. penguin — 1f427.svg (5)
11. ringed planet — 1fa90.svg (3)           12. balloon (dup for bunch) — 1f388.svg (4)
13. pig — 1f437.svg (5)                     14. anchor — 2693.svg (2)
15. octopus — 1f419.svg (7)
Also clean: school bus, helicopter, shooting star, telescope, egg, sheep, chicken,
cow, monkey, kite, whale-with-spout (1f433, 6), shield (1f6e1, 3), parrot, frog.
NO clean permissive skeleton exists for: dragon, unicorn, fairy, pirate ship,
treasure chest, seahorse, submarine, dump truck, astronaut, owl — hand-draw from
primitives or use dense emoji as pose reference only.
