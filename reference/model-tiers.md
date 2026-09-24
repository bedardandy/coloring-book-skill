# Model-tier guidance — calibrated by three benchmarks (2026-07-19, 2026-07-23, 2026-09-24)

The identical 3-page task (helper scene / cookbook-recipe objects / custom kneeling pose)
was run on Haiku 4.5, Sonnet 5 and Opus 4.8 (r1), re-run on those plus three GPT-5.6
variants via codex CLI (r2), and run cold on Opus 5.5 against the 2026-09 library (r3).
Findings below are observed, not assumed. Tiers are keyed by CAPABILITY CLASS, not by
model name — pick the class whose observed behaviour matches yours, honestly.

| Class | Operating mode | Observed in that class |
|---|---|---|
| Strong | full creative | Opus 5.5 (r3); Fable-class. Opus 4.8 (r2) behaved mid-class on composition. |
| Mid | standard | Sonnet 5; GPT-5.6 sol/terra/luna (codex) |
| Small / fast | conservative | Haiku 4.5 |

## Universal finding (every tier, every first draft — with one procedural exception)
**Models bottom-cram their first draft**: figures small on the ground line, 60% dead
sky. The one run that did NOT (r3) wrote a layout plan BEFORE drawing and ran the
validator while drafting — so the fix is procedural, not talent. Before drawing, write
the plan: ground line ~905; at least one midground element (tree/house/furniture) whose
top reaches y≈450-550; sky fillers distributed; main figures ~300-380 px tall
(kid_stand scale 1.2-1.5). Then verify NUMERICALLY after render — `python3 -m
lib.validate pages/*.svg` does all of these:
- scene (non-sky ink) spans ≥330 px and reaches down to y≥900 (`scene_span`)
- middle band y430-715 holds ≥40% of the heavier outer band's ink (`mass_distribution`)
- every element ≥12 px inside the border rect (compute extremes, don't eyeball)
- main figures ≥180 px tall; faces ≥ r28 (trait features crowd below that)

**Do not game the span check.** In r2, models at EVERY tier — including the strongest —
satisfied the bbox arithmetic with a corner sun and a high cloud while the scene sat in
the bottom third (one model's own report admitted doing this knowingly). That hole is
closed: every part of a sky motif is tagged `data-sky` and excluded, rows holding a lone
thin stroke don't extend the span, and a hollow middle band is flagged even when the
span passes. Numbers you report must come from the validator's report (`span`, `mass`)
on the render — never estimated, and never quoted from your plan. r3 went further and
measured coverage from rendered pixels (the connected component containing the ground
line); that is the gold standard when a page is borderline.

## Tier profiles & operating modes

### Strong models (Opus 5.5 / Fable class): FULL CREATIVE MODE
Observed (r3): pre-flight layout plan written into make_book.py; validator run while
drafting (nine findings caught before the first full build, which was then clean);
composition from the first draft; coverage measured from pixels; tile reviewers PLUS
blind forced-choice raters ("what is the dog doing?") to test whether a custom pose
READS; when a pose failed, switched pose TYPE (pooled-skirt kneel → side kneel →
occlusion → frontal squat) instead of iterating the same one; stopped after four
attempts on one element and shipped a STATED compromise; candid report that named seven
real skill/validator defects. Earlier strong-class runs (r1/r2 Opus 4.8) anticipated
gotchas and invented sound compromises (implied kneel via bell skirt + knee bumps, hand
ON the dog) but still bottom-crammed and gamed the span in r2 — the procedure above is
what separates the two.
Allowed: custom poses (build them from the PUBLIC parts `kid_top()` + `arm()` /
`limb()`, never by re-implementing the figure), novel objects beyond the cookbook,
dense scenes. Still required: the universal pre-flight + numeric checks, and a
blind-rater test for any custom pose before it ships.

### Mid models (Sonnet-class, capable non-Claude models): STANDARD MODE
Observed: reliable after 2-3 fix rounds, BUT fixes introduce regressions (enlarged tree →
clipped canopy; moved swing → seat landed on the dog). Rules:
- After ANY fix round, re-render and re-inspect the WHOLE page, not just the fixed region.
- Use render_tiles() crops for verification (worked well at this tier).
- Custom poses: allowed with a compromise bias — prefer implied poses (bent arm, bell
  skirt, seated) over explicit articulated limbs.
- Composition fixes: prefer ADDING mid-ground elements over INFLATING one element
  (a giant empty canopy reads worse than a tree + a bush + a cloud).

### Small/fast models (Haiku-class): CONSERVATIVE MODE
Observed: builds run and helpers assemble, but self-QA is unreliable — reported
"composition fixed / guide-compliant" while shipping 60%-empty pages, a missing tree,
border-clipped swing set, and a kneel that read as standing on a pedestal. Confidence
statements were badly miscalibrated (70-80% claimed on failed elements). Rules:
- **Helpers and cookbook recipes ONLY. No custom poses, no novel objects.** Reframe the
  scene so a stock pose works: "kneeling to pet" → kid_stand(pose="down") beside the dog
  with the hand circle overlapping the dog's back; "climbing" → standing on/near;
  "digging dog" → `dog_dig()`, etc.
- If arm/limb rendering misbehaves, `charlib.use_legacy_figures(True)` rebinds
  kid_stand/dog to the pre-smoothing wire-limb geometry (the 2026-07 originals).
- Max ~8 elements/page; one background anchor + figures + 2-3 fillers.
- **Run `python3 -m lib.validate pages/*.svg` after every build** — it converts the
  numeric layout checklist above into exact arithmetic and exits nonzero on HIGH
  findings. Fix findings by MOVING/SCALING elements per the message; do not
  eyeball-argue with it.
- QA is MANDATORY and external: spawn a stronger-model reviewer per page if the Agent
  tool is available. If it is not, tell the user plainly that page quality is unverified
  and recommend a review pass with a stronger model.

## Blind-rater test for custom poses (any tier that draws one)
A pose that YOU know is "kneeling" may read as "a girl in a poofy dress" to everyone
else — r3 found this on three kneel variants in a row. Before shipping a custom pose or
a staged action, spawn two reviewers who see ONLY a crop of the element and a
forced-choice list ("sniffing / digging / walking / drinking / other"), with no caption
and no hint. Ship only when both pick the intended action. If they don't, change the pose
TYPE (not the same pose again), or use the escalation ladder.

## Escalation & compromise ladder (any tier)
If the SAME approach fails two fix attempts, or a custom pose/object still doesn't read
after two tries — STOP iterating that approach (more rounds at the same capability
rarely converge). A different pose TYPE or staging counts as a new approach and is worth
one more try when a blind test can judge it. In order of preference:
1. **Compromise**: swap to a stock pose / helper object / simpler staging that removes
   the failing element entirely. A simple page that reads beats an ambitious page that
   doesn't. Proven compromises for hard poses: implied kneel (bell skirt + knee bumps),
   the frontal "diamond" squat (knees above hips, shins angled in — r3), and
   **occlusion staging** — place the figure BEHIND an object (garden bed, fence, table)
   so the hard lower body is simply hidden. Beware: occlusion behind a raised bed read as
   "sitting in a sandbox" to blind raters — test it.
2. **Delegate the element**: spawn a stronger-model subagent to draw just the failing
   helper/figure and return the SVG fragment. If no Agent tool is available in your
   run, this rung still applies — as a RECOMMENDATION: name the failing element in
   your report and suggest a stronger-model pass. Don't silently skip from rung 1 to 3.
3. **Escalate the build**: recommend the user re-run the book with a stronger model,
   stating specifically which pages/elements are below bar and why.
Never ship a page you could not verify numerically + visually; say so instead. If you
ship a compromise, SAY it is one in the report (r3: "Pip sniffs the hole with a heap of
dug dirt behind him — he never read as digging").

## Non-Claude agents (observed: GPT-5.6 sol/terra/luna via codex CLI)
All three completed the task and honestly self-reported earlier environment failures —
the skill's fail-loud instructions transfer. Calibration notes:
- Composition instructions transferred WELL (one variant produced the best-composed
  pages of the r2 run). Treat capable non-Claude models as mid-class (standard mode)
  unless they demonstrate otherwise.
- Guide rules that live only in prose get missed: one variant drew custom canopy
  texture with two same-height paired arcs — the documented "reads as a pair of
  closed eyes" gotcha — because it never connected the foliage section to its own
  custom marks. When you write custom texture/marks on ANY helper shape, re-check
  the drawing-guide section for that shape family first.
- `qa_page()` and `render_tiles()` were used unprompted by one variant and caught
  real defects — wire them into your build loop regardless of model family.

## When a reported defect "persists" after your fix
Before iterating again, re-diagnose WHICH stroke the reviewer is actually seeing — it
may not be the one you changed. (Case study: a "too-big mouth" survived two smile
shrinks because the offending stroke was the beard's inner edge, not the mouth.) Render
the isolated element large, identify every stroke in the flagged region, and only then
fix. Two blind retries on the wrong stroke = escalate per the ladder above.
