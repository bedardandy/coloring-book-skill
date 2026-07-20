# Model-tier guidance — calibrated by a 3-tier benchmark (2026-07-19)

The identical 3-page task (helper scene / cookbook-recipe objects / custom kneeling pose)
was run on Haiku 4.5, Sonnet 5, and Opus 4.8. Findings below are observed, not assumed.

## Universal finding (every tier, every first draft)
**All models bottom-cram their first draft**: figures small on the ground line, 60% dead
sky. Fix is procedural, not talent — BEFORE drawing, write a layout plan: ground line
~905; at least one background element (tree/house/furniture) reaching up into y 300-600;
sky fillers distributed; main figures ≥180px tall. Then verify NUMERICALLY after render:
- scene bounding box spans ≥55% of page height (y from ≤450 to ≥900)
- every element ≥12px inside the border rect (compute extremes, don't eyeball)
- main figures ≥180px tall; faces ≥ r28 (trait features crowd below that)

## Tier profiles & operating modes

### Strong models (Opus-class): FULL CREATIVE MODE
Observed: anticipates gotchas pre-render, invents sound compromises (implied kneel via
bell skirt + knee bumps instead of risky folded legs), stages real interactions (hand ON
the dog), accurate self-assessment. Allowed: custom poses, novel objects beyond the
cookbook, dense scenes. Still required: the universal pre-flight + numeric checks.

### Mid models (Sonnet-class): STANDARD MODE
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
  with the hand circle overlapping the dog's back; "climbing" → standing on/near, etc.
- Max ~8 elements/page; one background anchor + figures + 2-3 fillers.
- Apply the numeric layout checklist as arithmetic on your own coordinates BEFORE
  rendering (bounding boxes are trustworthy; your visual judgment of renders is not).
- QA is MANDATORY and external: spawn a stronger-model reviewer per page if the Agent
  tool is available. If it is not, tell the user plainly that page quality is unverified
  and recommend a review pass with a stronger model.

## Escalation & compromise ladder (any tier)
If the SAME defect survives two fix attempts, or a custom pose/object still doesn't read
after two tries — STOP iterating (more rounds at the same capability rarely converge).
In order of preference:
1. **Compromise**: swap to a stock pose / helper object / simpler staging that removes
   the failing element entirely. A simple page that reads beats an ambitious page that doesn't.
2. **Delegate the element**: spawn a stronger-model subagent to draw just the failing
   helper/figure and return the SVG fragment.
3. **Escalate the build**: recommend the user re-run the book with a stronger model,
   stating specifically which pages/elements are below bar and why.
Never ship a page you could not verify numerically + visually; say so instead.

## When a reported defect "persists" after your fix
Before iterating again, re-diagnose WHICH stroke the reviewer is actually seeing — it
may not be the one you changed. (Case study: a "too-big mouth" survived two smile
shrinks because the offending stroke was the beard's inner edge, not the mouth.) Render
the isolated element large, identify every stroke in the flagged region, and only then
fix. Two blind retries on the wrong stroke = escalate per the ladder above.
