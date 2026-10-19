# Likeness guide — keeping a real person's individual features

The kids in the book are PARAMETRIC: a trait dict draws the same face on every page,
so a character cannot drift. Likeness comes from putting the RIGHT traits in that dict —
the ones that make this child this child — not from reproducing a photo. Code:
`charlib.face()` (the vocabulary) and `lib/likeness.py` (measure, describe, check,
model sheet). For tracing a photo of a person into line art, see `photo-guide.md`
("Preserving facial features").

## Workflow (do it before any scene page)
1. **Collect** per person: what the user tells you + what you see in any photo.
   Photos stay on the machine (see Privacy).
2. **Measure** (optional, needs a frontal photo): `photolib.face_landmarks(photo)` (local
   YuNet: box + eyes, nose, mouth corners) or your own vision pass written as hints —
   then `likeness.traits_from_face(face)` returns measured `eye_spacing`, `smile_width`,
   `face_shape` (only when clearly off the population centre), `yaw`, and maps feature
   words you saw (`glasses`, `gap_tooth`, `freckles`, `dimples`, `{"name": "mole", "at":
   (x, y)}` …) to trait keys. A turned head is noted, not measured.
3. **Read it back**: `likeness.describe_traits(t)` gives the plain-language list in
   salience order ("pigtails hair, glasses, gap-tooth grin, a mole on the image-right
   cheek"). The user corrects it — they know the child; you know a photo.
4. **Show the model sheet**: `likeness.model_sheet(t)` → a "Meet Harper!" page (big front
   face, 3/4 turnaround, standing figure, traits caption). Render it and ask "is this
   Harper?" before drawing the book. It also works as an "All about me" page.
5. **Check and freeze**: `likeness.check_traits(t, poses=[...])` (typos draw the classic
   default silently; wide hair hides stock-pose hands) and
   `likeness.cast_distinctness(cast)`; then the dict is frozen — copy it verbatim into
   every page and the story bible. Never override a trait per page (expressions like
   `dict(t, mouth="open")` and staging like `look` are the exceptions).

## Salience — what makes a kid recognisable at coloring-book size
hair silhouette / headwear > glasses > height > signature outfit > face shape >
distinctive marks (gap tooth, freckles, mole, dimples) > eye / nose style.
Spend the user's attention in that order; two kids who differ only below "outfit" read
as the same kid in a thumbnail (`cast_distinctness` flags them).

## Photo cue → trait
| You see | Trait |
|---|---|
| hair outline (the strongest cue) | `hair`: bob_bangs, bob (+`headband`), tousled, long_wavy, pigtails, curly, buzz, ponytail, afro, bun, braids, side_part, bald (fringe tufts) |
| parting / which side a ponytail falls | `hair_part`: left \| right (ponytail, side_part) |
| head scarf | `headwear="hijab"` (replaces the hair silhouette) |
| face proportions | `face_shape`: round (default), oval, long, heart, square |
| eyes far apart / close together | `eye_spacing` 0.30-0.46 (classic 0.38) — measure it |
| big eyes / long lashes / almond eyes / always-smiling eyes | `eye_size` 0.8-1.4, `lashes`, `eyes`: dot, round, almond, smile |
| a nose worth drawing | `nose`: button, round, long (default none — most kids' faces read better without) |
| ears that stick out | `ears`: small \| big |
| missing front tooth / big grin | `mouth`: gap_tooth \| grin (`open` for celebration pages) |
| wide smile | `smile_width` 0.8-1.3 |
| dimples, freckles, moles | `dimples`, `freckles`: True \| light \| heavy, `moles=[(dx, dy)]` in head radii from the face centre (+x image-right, +y down) |
| strong eyebrows | `brows="thick"` (default off — see anti-eerie) |
| glasses, beard | `glasses`, `beard` |

## Rendering rules learned the hard way (2026-10 visual pass)
- **Anti-eerie still rules.** Lashes are flicks off the OUTER corner — ticks on the top
  lid read as a scowl, and two flicks on a dot eye read as a squint `><`, so dot eyes
  get one. Almond eyes have a high top lid and a big pupil — a flat lid reads sly.
- **Round eyes behind glasses fall back to dots** automatically: rings in lenses read as
  hypnotic spirals.
- **Dimples sit on the cheek**, clear of the mouth corners — beside the corner they read
  as smirk brackets, touching it as a wavy mouth.
- **Small features need size**: gap tooth, dimples, lashes and moles read at figure
  scale ≥1.2; on a distant (≤1.0) figure they are noise. Big features carry the likeness
  on small figures; small marks carry it on the model sheet and close-ups.
- **Wide hair hides hands**: pigtails (1.7r), ponytail (1.7r, its side), afro (1.62r), hijab (1.5r), long_wavy
  (1.45r), braids (1.42r) reach past the head-kill radius — use `kid_stand` poses
  `wave_high` / `cheer` (`check_traits(t, poses=...)` warns; the validator's
  `hand_hidden` check measures it on the page).
- **Gaze is staging, not identity**: `look` (-1..1) turns the head to a 3/4 view —
  features slide toward the gaze and the far ear hides. Set it per page so characters
  look at each other or at the thing the caption names (`space3d.look_toward`).
- Explicit proportions (`eye_spacing`, `eye_size`, `smile_width`) win over the
  name-seeded micro-variation, so a measured child keeps measured eyes.

## Respect
- Represent what the family identifies with (headwear, hair texture, glasses, a
  wheelchair via `kid_wheelchair`) — ask, don't assume from a photo.
- Proportions are clamped to friendly ranges on purpose: likeness, never caricature.
- Ask before drawing marks a child may be self-conscious about (a birthmark, a mole);
  the parent decides. Celebrate the ones kids love (a gap tooth at 6).

## Privacy
Photos of real children are processed locally (OpenCV + the bundled YuNet model) and
never committed; the trait dict keeps only coarse buckets and three clamped ratios — no
image, no embedding. Sending a photo to any hosted image model needs the parent's
explicit consent (photolib refuses remote backends without `allow_remote=True`).
