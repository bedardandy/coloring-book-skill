# Spatial guide — depth with `lib/space3d.py`

Read this when a page needs real depth: "Max in front, Lily behind the table, the
house far away", a room interior, a road or path running into the distance, a row
of trees or fence posts shrinking with distance. A single scene kit with everyone on
one ground line is still right for simple "kids in a meadow" pages. Once the request
says *in front of / behind / far away*, place things by world depth instead of
guessing page coordinates. Then size, ground contact, overlap order and slivers all
come out of the arithmetic.

## The model in five lines
- `cam = Camera()`: a one-point-perspective pinhole camera. Horizon (eye level) at
  page y 520, vanishing point at x 425. Ground at `z = near_z = 800` lands on y 940
  (`SCENE_GROUND`) with figures at scale 1.3, which is the recipe's foreground.
- World units are **charlib figure units** (a `kid_stand` is about 250 tall). `x`
  runs sideways (0 = page centre, + = page right), `y` up (0 = ground), `z` is
  depth (bigger = farther).
- `px = vp_x + f·x/z`, `py = horizon_y + f·(eye_h − y)/z`, `scale_at(z) = f/z`, where
  `f = near_scale·near_z` and `eye_h = (near_ground_y − horizon_y)/near_scale`.
  **Doubling z halves the size**, and the farther ground sits closer to the horizon.
- `cam.place(x, z[, y])` returns `(px, feet_py, scale)` for `G()`. Inverses:
  `cam.z_for_ground_y(py)`, `cam.x_for_page_x(px, z)`, `cam.unproject_ground(px, py)`.
- `Stage(cam)` draws everything far to near. **Use the Stage**, not hand `G()` calls.

Default camera, z → scale / ground y / kid height / face r:

| z | scale | ground y | kid px | face r |
|---|---|---|---|---|
| 800 | 1.30 | 940 | 325 | 48 |
| 1000 | 1.04 | 856 | 260 | 38 |
| 1300 | 0.80 | 778 | 200 | 30 |
| 1600 | 0.65 | 730 | 162 | 24 |
| 2400 | 0.43 | 660 | 108 | 16 |
| 4000 | 0.26 | 604 | 65 | 10 |

Named characters belong at **z ≤ ~1350** (1.7 × near_z). Beyond that the face drops
under the validator's r ≥ 28 floor (MED), and the main figure must still be ≥ 180 px.
Things farther back should be faceless: trees, houses, a distant car.

## Three-layer recipe → z bands
`cam.band(name)` gives each band as multiples of `near_z`:
- **foreground** `z ≈ 800-960`: main figures, scale 1.3-1.08, standing at y 940-870.
- **midground** `z ≈ 1080-1600`: the anchor (table, toy box, tree, house), scale
  0.96-0.65. Tops should still reach y ≈ 450-550 (a `tree_round(h=380)` at z 1250).
- **background** `z ≈ 1800-4000`: rows of trees, the far house, hills at the horizon.

Receding lines are thin, so they carry **no scene mass** (the validator ignores rows
with less than 2% ink). A room or a road with a lone figure is still a hollow page:
the midground anchor stays mandatory.

## Stage
```python
from space3d import Camera, Stage, room_box, look_toward
cam = Camera()
st = Stage(cam)                                   # pad=9 mats, contact lines on
st.add(lambda: kid_stand(T2, "wave"), x=-170, z=830, name="Max")
st.add_table(x=60, z=1020, w=250, d=190, h=80, name="table")
st.add(lambda: kid_stand(T1, "wave_high"), x=60, z=1300, name="Lily")
st.add(lambda: dog_sit(P1), x=230, z=880, name="dog", flip=True)   # GM mirror
body = room_box(cam, height=640, door=True) + st.render()
```
- `add(art, x, z, name=, mat=True, contact=True, y=0, flip=False)`. `art` is a
  feet-origin fragment (`kid_stand`, `dog_sit`, `tree_round(0, 0, h=…)`, `house(0,
  0)`), or a **zero-argument callable** that is evaluated at render time. `y > 0` stands
  it on a surface (a cup on the table, a lamp hanging at y=520). `contact` can be True
  (auto width from the feet), a half-width in world units, or False (houses, hanging
  things).
- Solids: `add_box(x, z, w, d, h)` and `add_table(x, z, w, d, h)`. Both occupy the depth
  range `z..z+d`. For any other projected fragment use
  `add_solid(art, z, z_far, x0, x1, top)`.
- `add_row(make, x, z0, z1, n)` adds one billboard per row item, so a figure can stand
  between two trees.
- `render()` sorts far to near (ties keep insertion order) with two extra rules: a
  billboard standing *beside* a solid on its camera-facing side draws after the solid
  (it is in front of the visible side face), and so does anything resting on the
  solid's top. Each item is `matted()`. Each billboard's contact line is drawn
  **after** its own matted art, so the halo never dashes it. Nearer items still cover
  it correctly.
- Every item is wrapped in `<g data-depth data-depth-name data-depth-scale
  data-depth-ground [data-depth-far]>`, which the validator reads.

## Primitives (all white-filled back to front, clipped to `SAFE`)
`SAFE = (42, 152, 808, 988)`: 12 px or more inside the border, below the title zone,
above the caption band.
- `room_box(cam, width=760, z_back=2000, height=520, ceiling=True,
  floor="boards"|"tiles"|None, boards=6, tile_depth=160, window=True, door=False)`
  draws a one-point interior: back wall, receding floor/ceiling edges, floorboards,
  and a window/door on the back wall. Pass `window=(x, y_bottom, w, h)` or
  `door=(x, w, h)` in world units. Use `height > cam.eye_h` (about 323) for a
  ceiling, lower for an open dollhouse set. Draw it FIRST, as the background.
- `wall_quad(cam, x, z0, z1, y0, y1, inset=16)` draws a picture, side window or door
  on a side wall (`x = ±width/2`). `inset` is the inner frame band in **page px**,
  solved on the page because a world-unit inset foreshortens to a sliver.
- `path_recede(cam, x, width, z0, z1, curve=0, dashes=False)` draws a path or road
  narrowing toward the horizon as ONE closed white shape (it knocks out what's behind).
  `curve` bends it by `curve·sin(πt)`. Put a house or hill at its far end.
- `box3d(cam, x, z, w, d, h, base=0)` draws a crate, block, bed, counter or building.
  Only the visible faces are drawn: the top shows when it is below eye level, and the
  inner side shows when the box is off-axis.
- `table3d(cam, x, z, w, d, h)` draws four legs and a top slab.
- `receding_row(cam, make, x, z0, z1, n)` draws trees, posts or lampposts evenly
  spaced in depth (`x` may be `callable(i)` to zig-zag). The far items fade out.
- `ground_grid(cam, x0, x1, z0, z1, dx, dz)` draws floor tiles or garden plots.
  `ground_ellipse(cam, x, z, rx, rz)` draws a rug, pond or sandpit.

## The vanishing-point sliver rule (why primitives stop lines early)
Lines that run into the depth all meet at the vanishing point, so near it any two of
them get closer than the validator's 11 px `sliver_gap`. That leaves wedge regions
no crayon fits into. Every primitive stops converging lines where their
**perpendicular** spacing drops below `CONVERGE_GAP = 14` px, which is
`cam.converge_z(off_a, off_b)` (exact). It also skips tile rows closer than that,
omits box faces, slabs and back table legs thinner than that, drops row items that
crowd, and caps a path's far end while it is still ≥ 14 px wide. For your own
receding lines, compute the stop with `cam.converge_z` and emit them **near end
first** (`LINE(near…, far…)`). `sliver_gap` measures a pair at the second line's
first endpoint.

## Gaze
`look_toward(x_from, x_to)` returns a yaw in [-1, 1] (+ = toward page right). Pass it
as the face trait `look` (`kid_stand(dict(t, look=v))`). This needs the face's
`look` parameter. Inside a Stage, compute it at render time:
`st.add(lambda: kid_stand(dict(T1, look=st.gaze("Lily", "Max"))), x=60, z=1300,
name="Lily")`. Two kids looking at each other turn the page from "posed" into "playing
together".

## Gotchas
- **Behind a table**: the far figure's feet must land inside the table top's page
  band. Otherwise its shoes and hem peek out under the slab as fragments and slivers.
  With the default camera a kid at z 1300 (feet y 778) behind `h=80` at z 1020
  works. `h=95` does not.
- **Fit**: a billboard's page half-width is its local half-width × scale. Near trees
  at `x=±330` leave the page, and `border_clearance` will say so. Pull side rows
  inward, or start them farther back.
- **No flat kit ground line in a perspective scene.** A full-width `LINE(50, 940, …)`
  claims the world is flat at one depth. Use `room_box`, `path_recede`, or a horizon
  line and hills at `cam.horizon_y`. Kit skies (sun, clouds) are fine.
- Keep the horizon at y ≈ 470-560. Higher pushes ceiling lines into the title zone
  (they're clipped at y 152). Lower squeezes the background band.
- `y` lifts an item onto a surface and its ground tag stays the floor point below it.
  Do not fake height by moving `z`.

## Validator: `depth_order`
On pages with `data-depth` groups (Stage output, or hand-tagged), the validator adds
these checks:
- MED when a farther group is drawn at a **larger scale** or stands **lower on the
  page** than a nearer one. Fix: place both with `cam.place()` or the Stage.
- MED `farther object painted over nearer one` when a group that lies wholly behind
  another is drawn after it and their boxes overlap. Fix: let `Stage.render()` order
  them.
- `head_clearance` exempts art from a strictly farther depth group that is drawn
  before a nearer head (a distant tree trunk behind a kid is correct occlusion).
- `report["depth"] = {groups, order, scale_conflicts, inversions}`. The CLI prints a
  `depth groups …` line. Pages without depth groups produce exactly the same report
  as before.

## Worked example
`tools/showcase.py` → `depth_room()` renders `examples/showcase/pages/20-depth.png`:
a one-point playroom (`room_box(height=640, door=True)`), a framed picture on the
left wall (`wall_quad`), and a rug (`ground_ellipse`). On the Stage: Max in front
(z 830), the dog front-right (z 880, flipped), the table (z 1020-1210), Lily behind it
(z 1300), a toy box (`add_box`) on the right whose top and inner side show, and a lamp
hanging from the ceiling (`y=520`, no contact line). It validates clean, and the
raster `qa_page` sliver count is 18: cheeks, hand circles, knobs, with none from
receding lines.
