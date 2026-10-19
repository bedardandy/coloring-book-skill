# Story mode — ages 3-6

Story SELECTION: see `story-tropes.md` for a menu of proven structures (classic +
creative), engagement mechanics, and age-fit notes — offer the user 2-3 matched options.
The chosen trope instantiates onto this arc:

10-page quest arc (low-stakes, child is always the actor):
1. Intro: child + home/setting. "This is Mia. Mia lives in a little blue house with Rex."
2. Problem/invitation appears (lost toy, surprise note, shy new pet, party to prepare).
3. Cast decides to act (sibling/cousin/pet joins). Refrain introduced.
4. First look/try — small discovery, not the answer.
5. Second try — different room/place; repeatable page pattern.
6. Third try — a pet or sibling contributes the key clue.
7. Almost there — gentle setback (it rolled under the bed; the kitten hides).
8. Solve — the child does the solving action themselves.
9. Celebrate — full cast together (dance, picnic, high-five page).
10. Cozy resolution — home/bedtime/"The End" wave. Dedication line.

## Caption rules
- 15-25 words/page, ~150-250 total. Simple present tense, subject-verb-object.
- Repeat the child's name instead of pronouns at least once per page.
- A chant-along refrain every 1-2 pages: "[Name] and [Pet] look everywhere!"
- NO rhyme (templated rhyme reads clunky — the #1 complaint about commercial books).
- Obstacles must be cozy: hidden, shy, sleepy, wobbly — never scary, dark, or threat-based.

## Page-type variety (makes it feel like a real book)
- Cover with names + motifs; name-tracing page (large outline letters to color/trace);
  one find-the-X activity page mid-book ("Can you find 5 stars on this page?");
  back cover "Made with love for ...".

## Continuity: the story bible
Story rules are code too: `lib/story.py` lints the whole book the way `lib/validate.py`
lints one page. Write the bible FIRST, as `story.json` next to `make_book.py`
(`examples/where-is-button/story.json` is a complete one):
- `cast` — `{name: {"role": hero|sibling|pet|adult, "traits": {...}}}`. The traits are
  the exact dicts `kid_stand()`/`face_traits()`/`dog()` take; make_book uses
  `bible.traits("Mia")` so every page draws the same dict.
- `locations` — `{id: {"kit", "variant", "anchors": {"window": "left", "bed": "right"}}}`:
  the things that stay put every time the place is drawn.
- `props` — the lost/key object and its timeline: `present@1 -> missing@2 -> found@8`.
- `beats` — one entry per page in book order: `page` (builder id), `kind`
  (cover/names/scene/activity/creative/back), `beat` (arc number, or `[2, 3]` for a
  merged page), `location`, `cast` (who is drawn), `actor` (who ACTS), `props`
  (`{"Bun": "missing"}` / `{"Bun": {"state": "held", "holder": "Mia"}}`; while missing a
  page may show `hidden` or `imagined`, never `present`), `caption`, `title`, `time`
  (dawn/morning/day/afternoon/evening/night; `time_jump: true` for "the next morning"),
  `anchors` (where THIS page puts the location's anchors).

Workflow:
1. Draft the bible, then show `print(StoryBible.load("story.json").outline())` to the
   user — cast, prop timeline, arc coverage and every caption with its word count in one
   table — and get a yes before drawing.
2. `python3 -m lib.story story.json` — fix every HIGH, read the MEDs.
3. Builders (`from story import StoryBible, annotate` after the `lib` path insert) take
   captions and traits from the bible and return
   `story.annotate(spage(..., caption=bible.caption(p)), bible.beat(p))` (or
   `bible.annotate(svg, p)`); the record is a `<metadata>` element: renders and
   `lib.validate` reports are unchanged.
4. After `build()`: `python3 -m lib.story story.json pages/*.svg` alongside
   `python3 -m lib.validate pages/*.svg`. Both exit 1 on HIGH.

| rule | sev | fires when | fix |
|---|---|---|---|
| trait_drift | HIGH | a beat overrides a cast trait (outfit, hair, glasses...) | delete the override; change the cast dict if the change is book-wide |
| solve_actor | HIGH/MED | the solve beat's actor is an adult, nobody, or off the page (HIGH); only the pet (MED) | the pet brings the clue, the child does the last action |
| prop_state | HIGH/MED | prop drawn while missing (HIGH); held by someone not on the page (MED) | remove it or draw a hint (`hidden` tail, `imagined` cloud); draw the holder |
| cast_presence | MED | caption names someone not on the page, or the actor isn't on it | draw them / add to `cast` / reword |
| location | MED | a recurring place uses another kit variant or an anchor changes side | `GM()` the furniture back to its side; one variant per place |
| refrain | MED/LOW | missing, never used, 2 story pages in a row without it before the solve; LOW if introduced after beat 3 | quote it word for word every 1-2 pages |
| arc_coverage | MED/LOW | an arc beat has no page (MED); beats out of order (LOW) | add the page or merge with `beat: [n, m]` |
| caption_length | MED | a scene caption is outside 15-25 words | trim, or add one present-tense sentence |
| cast_name | MED/LOW | no cast name in a scene caption (MED); hero drawn but not named (LOW) | say the name instead of "she" |
| cozy_words | MED | monster, scary, dark forest, hurt, cry... | hidden/shy/sleepy/wobbly; `allow_words` for a trope that needs one (Shy Monster) |
| pronoun_only / past_tense / rhyme / refrain_drift | LOW | more pronouns than names; was/found/looked...; adjacent sentence endings rhyme; refrain paraphrased | lint, read and decide |
| actor / time_of_day / bible_ref | LOW-MED | no actor on a scene beat; time runs backwards; unknown names/props/places | declare it |
| page checks | MED/LOW | with SVGs: stale record, drawn caption differs from the bible, fewer `data-el="figure"` groups than people in `cast` (pets don't count), two `data-scene` values for one place | rebuild after editing the bible |

## Coherence craft (what the linter can't see)
- **Continuity anchors.** Pick 2-3 anchors per location (window, bed, rug, the big tree)
  and keep each on the same side at about the same size on every page of that place;
  record them in `anchors`. Vary the camera with WHAT is in front, not by moving the room.
  If one page needs the bed on the other side, flip the whole room with `GM()`, or
  state the new view in the caption.
- **Seed the find.** Show the lost item's silhouette early (the cover, the intro) and
  reuse that exact silhouette as the hint: a peeking ear on the beat-6 clue page and the
  outline to look for on the find-the-X page. The hint is drawn the same way every time.
- **Echo the refrain in the picture.** The page carrying the chant gets the same
  staging cue each time (the whole cast in a row, hands up to look); kids learn to say
  the line when they see the pose.
- **Gaze and staging follow the caption.** Whoever the caption says looks, points or
  reaches faces that thing: side-profile helpers face right, so `GM()` them to face
  left; heads and hands point toward the target; the target sits between or in front of
  the characters, never behind their backs. The actor stands nearest the thing they act
  on.
- **One change per page.** Between two pages of the same place, change only what the
  story changed (the bed is empty now); everything else stays where it was, so the
  change is what the child sees.
