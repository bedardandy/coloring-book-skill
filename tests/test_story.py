"""Story bible + continuity linter (lib/story.py): every rule fires on a
constructed violation and stays silent on a clean bible; JSON and SVG
record round trips; the bundled example has no HIGH findings."""
import ast
import json
import os
import subprocess
import sys

import story as S
import validate as V
from charlib import G, kid_stand, dog_sit, spage, matted

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXAMPLE = os.path.join(REPO, "examples", "where-is-button")
EXAMPLE_BIBLE = os.path.join(EXAMPLE, "story.json")
PY = sys.executable

MIA = {"name": "Mia", "age": 5, "hair": "pigtails", "glasses": True,
       "freckles": False, "height": 1.0, "outfit": "overalls"}
REX = {"coat": "spots", "floppy_ears": True, "collar": True}
GRANDPA = {"name": "Grandpa", "hair": "long_wavy", "glasses": True,
           "beard": True, "height": 1.25, "outfit": "tee"}


def clean_dict():
    """A 12-page story bible that passes every rule."""
    def sc(page, beat, loc, time, caption, actor="Mia", cast=("Mia", "Rex"),
           props=None, anchors=None, kind="scene"):
        b = {"page": page, "kind": kind, "beat": beat, "location": loc,
             "time": time, "cast": list(cast), "actor": actor,
             "caption": caption}
        if props:
            b["props"] = props
        if anchors:
            b["anchors"] = anchors
        return b

    bed = {"window": "left wall", "bed": "right"}
    return {
        "title": "Where Is Bun?", "age_band": "3-6", "mode": "story",
        "trope": "The Lost Treasure",
        "refrain": "Mia and Rex look everywhere",
        "cast": {"Mia": {"role": "hero", "traits": MIA},
                 "Rex": {"role": "pet", "species": "dog", "traits": REX},
                 "Grandpa": {"role": "adult", "traits": GRANDPA}},
        "locations": {"bedroom": {"kit": "room", "anchors": bed},
                      "kitchen": {"kit": "room"},
                      "garden": {"kit": "scene_meadow", "variant": 1,
                                 "anchors": {"tree": "left"}}},
        "props": {"Bun": {"desc": "Mia's toy bunny", "timeline": [
            {"beat": 1, "state": "present"}, {"beat": 2, "state": "missing"},
            {"beat": 8, "state": "found"}]}},
        "beats": [
            {"page": "01-cover", "kind": "cover", "cast": ["Mia", "Rex"],
             "title": "Where Is Bun?",
             "props": {"Bun": {"state": "held", "holder": "Mia"}}},
            {"page": "02-names", "kind": "names",
             "caption": "Trace the letters. M-I-A spells Mia."},
            sc("03-intro", 1, "bedroom", "morning",
               "This is Mia. Mia lives in a little blue house with Rex the "
               "dog. Mia loves her bunny Bun very much.",
               props={"Bun": "present"}, anchors=bed),
            sc("04-problem", 2, "bedroom", "morning",
               "Oh no! Bun is not on the bed. Mia looks at the empty "
               "pillow. Where is Bun today?", props={"Bun": "missing"},
               anchors={"bed": "right"}),
            sc("05-decide", 3, "bedroom", "morning",
               "Mia and Rex look everywhere! Rex wags his tail and sniffs "
               "the floor. Mia and Rex start the big search.",
               actor=["Mia", "Rex"]),
            sc("06-kitchen", 4, "kitchen", "morning",
               "Mia peeks in the kitchen cupboard. Rex finds a red sock, "
               "not Bun. Mia and Rex look everywhere!"),
            sc("07-garden", 5, "garden", "midday",
               "Mia checks under the garden bench. Rex digs a tiny hole in "
               "the soft dirt. Bun is not here yet."),
            sc("08-clue", 6, "garden", "afternoon",
               "Mia and Rex look everywhere! Rex points his nose at a small "
               "fuzzy tail behind the flower pot.", actor="Rex",
               props={"Bun": "hidden"}, anchors={"tree": "left"},
               kind="activity"),
            sc("09-almost", 7, "bedroom", "afternoon",
               "Mia reaches for the tail. Bun slips under the big bed. Mia "
               "and Rex look everywhere for Bun!", props={"Bun": "hidden"}),
            sc("10-solve", 8, "bedroom", "afternoon",
               "Mia crawls under the bed. Mia pulls Bun out with both hands. "
               "Rex wags and wags. Hooray, Mia!",
               props={"Bun": {"state": "held", "holder": "Mia"}}),
            sc("11-picnic", 9, "garden", "evening",
               "Mia, Rex and Grandpa have a picnic with Bun. Everyone eats "
               "apple slices. Mia gives Bun a big hug.",
               actor=["Mia", "Grandpa"], cast=("Mia", "Rex", "Grandpa"),
               props={"Bun": "present"}),
            sc("12-goodnight", 10, "bedroom", "night",
               "Mia snuggles into bed with Bun. Rex curls up on the rug. "
               "Goodnight, Mia. Goodnight, Rex. The End.",
               props={"Bun": "present"}),
        ],
    }


def run(d=None, pages=None):
    return S.check(S.StoryBible.from_dict(d or clean_dict()), pages)


def hits(rep, check_, sev=None):
    return [f for f in rep["findings"] if f["check"] == check_
            and (sev is None or f["severity"] == sev)]


def mutated(fn):
    d = clean_dict()
    fn(d)
    return run(d)


def beat(d, page):
    return next(b for b in d["beats"] if b["page"] == page)


# ---------------------------------------------------------------- clean
def test_clean_bible_is_silent():
    rep = run()
    assert rep["findings"] == [], rep["findings"]
    assert rep["ok"] and all(rep["arc"][n] for n in range(1, 11))


def test_clean_caption_is_silent():
    cap = beat(clean_dict(), "03-intro")["caption"]
    assert S.lint_caption(cap, ["Mia", "Rex"], "Mia and Rex look everywhere",
                          hero="Mia", present=["Mia", "Rex"]) == []


def test_findings_use_validate_vocabulary():
    rep = mutated(lambda d: beat(d, "03-intro").update(caption="Hi Mia."))
    f = hits(rep, "caption_length")[0]
    assert set(f) >= {"severity", "check", "msg"}
    assert f["severity"] in ("HIGH", "MED", "LOW") and f["page"] == "03-intro"
    assert set(rep["counts"]) == {"HIGH", "MED", "LOW"}


# ---------------------------------------------------------------- captions
def test_caption_length_fires_outside_15_25():
    short = S.lint_caption("Mia runs. Rex runs.", ["Mia", "Rex"])
    long_ = S.lint_caption(" ".join(["Mia hops."] * 13), ["Mia"])
    assert hits({"findings": short}, "caption_length", "MED")
    assert hits({"findings": long_}, "caption_length", "MED")
    # non-scene pages are not held to the scene length
    assert not hits({"findings": S.lint_caption(
        "Mia runs.", ["Mia"], kind="activity")}, "caption_length")


def test_cast_name_med_when_no_name_and_low_for_unnamed_hero():
    cap = "The bunny is not on the bed. Where is the bunny? Look under the " \
          "big soft pillow and the blue blanket now."
    f = S.lint_caption(cap, ["Mia", "Rex"])
    assert hits({"findings": f}, "cast_name", "MED")
    cap2 = "Rex sniffs the floor. Rex wags his tail. Rex looks under the " \
           "big soft pillow and the blue blanket."
    f2 = S.lint_caption(cap2, ["Mia", "Rex"], hero="Mia",
                        present=["Mia", "Rex"])
    assert hits({"findings": f2}, "cast_name", "LOW")


def test_pronoun_only_fires():
    cap = "Mia finds a box. She opens it. She looks inside. He wags. They " \
          "smile at the little red box together."
    assert hits({"findings": S.lint_caption(cap, ["Mia", "Rex"])},
                "pronoun_only", "LOW")


def test_past_tense_fires_and_present_is_silent():
    cap = "Mia looked under the bed. Rex found a sock. Mia and Rex keep " \
          "looking for the little bunny today."
    f = hits({"findings": S.lint_caption(cap, ["Mia", "Rex"])}, "past_tense")
    assert f and f[0]["severity"] == "LOW" and "found" in f[0]["msg"]
    cap2 = cap.replace("looked", "looks").replace("found", "finds")
    assert not hits({"findings": S.lint_caption(cap2, ["Mia", "Rex"])},
                    "past_tense")


def test_rhyme_fires_on_adjacent_endings_only():
    cap = "Mia finds a big red ball. Rex the dog is very tall. Mia and Rex " \
          "play in the sunny garden."
    assert hits({"findings": S.lint_caption(cap, ["Mia", "Rex"])},
                "rhyme", "LOW")
    # repeating the same word is repetition, not rhyme; -ing is grammar
    rep = "Mia looks for Bun. Rex looks for Bun. Mia is looking. Rex is " \
          "sniffing. Mia and Rex keep going."
    assert not hits({"findings": S.lint_caption(rep, ["Mia", "Rex"])},
                    "rhyme")


def test_cozy_words_fire_and_allow_words_opt_back_in():
    cap = "Mia hears a monster in the dark forest. Rex is scared. Mia and " \
          "Rex hold hands and wait."
    f = hits({"findings": S.lint_caption(cap, ["Mia", "Rex"])}, "cozy_words")
    assert f and f[0]["severity"] == "MED"
    assert "monster" in f[0]["msg"] and "dark forest" in f[0]["msg"]
    shy = "Mia meets a shy little monster. The monster wants to play. Mia " \
          "and Rex teach the monster tag."
    assert not hits({"findings": S.lint_caption(
        shy, ["Mia", "Rex"], allow_words=["monster"])}, "cozy_words")
    rep = mutated(lambda d: beat(d, "04-problem").update(
        title="The Scary Night"))
    assert hits(rep, "cozy_words", "MED")


def test_refrain_drift_fires_on_paraphrase():
    cap = "Mia and Rex look all over everywhere! Rex sniffs the rug. Mia " \
          "peeks under the blue chair."
    f = S.lint_caption(cap, ["Mia", "Rex"], "Mia and Rex look everywhere")
    assert hits({"findings": f}, "refrain_drift", "LOW")


# ---------------------------------------------------------------- book rules
def test_refrain_gap_fires():
    def drop(d):
        beat(d, "08-clue")["caption"] = (
            "Mia waits by the garden gate. Rex points his nose at a small "
            "fuzzy tail behind the flower pot.")
    rep = mutated(drop)            # 07-garden + 08-clue both lack it
    f = hits(rep, "refrain", "MED")
    assert f and "07-garden" in f[0]["msg"] and "08-clue" in f[0]["msg"]


def test_refrain_missing_or_never_used():
    assert hits(mutated(lambda d: d.update(refrain=None)), "refrain", "MED")
    assert hits(mutated(lambda d: d.update(refrain="Hop hop hooray")),
                "refrain", "MED")


def test_refrain_late_introduction_is_low():
    def late(d):
        for p in ("05-decide", "06-kitchen", "08-clue", "09-almost"):
            b = beat(d, p)
            b["caption"] = b["caption"].replace(
                "Mia and Rex look everywhere", "Mia and Rex search")
        d["refrain_variants"] = []
        beat(d, "09-almost")["caption"] = (
            "Mia reaches for the tail. Bun slips under the big bed. Mia and "
            "Rex look everywhere for Bun!")
    rep = mutated(late)
    assert hits(rep, "refrain", "LOW")


def test_solve_actor_rules():
    rep = mutated(lambda d: beat(d, "10-solve").update(
        actor="Grandpa", cast=["Mia", "Rex", "Grandpa"]))
    assert hits(rep, "solve_actor", "HIGH") and not rep["ok"]
    rep = mutated(lambda d: beat(d, "10-solve").pop("actor"))
    assert hits(rep, "solve_actor", "HIGH")
    rep = mutated(lambda d: beat(d, "10-solve").update(cast=["Rex"]))
    assert hits(rep, "cast_presence", "HIGH")     # the solver is not drawn
    rep = mutated(lambda d: beat(d, "10-solve").update(actor="Rex"))
    f = hits(rep, "solve_actor")
    assert f and f[0]["severity"] == "MED"


def test_cast_presence_named_but_absent():
    rep = mutated(lambda d: beat(d, "11-picnic").update(cast=["Mia", "Rex"],
                                                        actor="Mia"))
    f = hits(rep, "cast_presence", "MED")
    assert f and "Grandpa" in f[0]["msg"]


def test_actor_not_present_and_actor_missing():
    rep = mutated(lambda d: beat(d, "06-kitchen").update(actor="Grandpa"))
    assert hits(rep, "cast_presence", "MED")
    rep = mutated(lambda d: beat(d, "06-kitchen").pop("actor"))
    assert hits(rep, "actor", "LOW")


def test_prop_shown_while_missing_is_high():
    rep = mutated(lambda d: beat(d, "07-garden").update(
        props={"Bun": "present"}))
    f = hits(rep, "prop_state", "HIGH")
    assert f and "beat 8" in f[0]["msg"] and not rep["ok"]
    # hints are fine while it is missing; the find beat itself is fine
    rep = mutated(lambda d: beat(d, "07-garden").update(
        props={"Bun": "imagined"}))
    assert not hits(rep, "prop_state")


def test_held_prop_holder_absent_is_med():
    def away(d):
        b = beat(d, "11-picnic")
        b["props"] = {"Bun": {"state": "held", "holder": "Grandpa"}}
        b.update(cast=["Mia", "Rex"], actor="Mia",
                 caption=b["caption"].replace("Mia, Rex and Grandpa",
                                              "Mia and Rex"))
    f = hits(mutated(away), "prop_state", "MED")
    assert f and "Grandpa" in f[0]["msg"]


def test_location_anchor_flip_and_variant_change():
    rep = mutated(lambda d: beat(d, "04-problem").update(
        anchors={"bed": "left"}))
    f = hits(rep, "location", "MED")
    assert f and "bed on the left" in f[0]["msg"]
    rep = mutated(lambda d: beat(d, "07-garden").update(variant=2))
    assert hits(rep, "location", "MED")
    # without a declared kit variant the first page sets it
    def undeclared(d):
        d["locations"]["kitchen"]["anchors"] = {}
        beat(d, "06-kitchen").update(variant=0, anchors={"sink": "left"})
        d["beats"].insert(6, dict(beat(d, "06-kitchen"), page="06b-kitchen",
                                  variant=1, anchors={"sink": "right"}))
    rep = mutated(undeclared)
    msgs = " ".join(f["msg"] for f in hits(rep, "location"))
    assert "variant 1" in msgs and "sink on the right" in msgs


def test_time_of_day_backwards_and_jump():
    rep = mutated(lambda d: beat(d, "11-picnic").update(time="morning"))
    assert hits(rep, "time_of_day", "LOW")
    def jump(d):
        beat(d, "11-picnic").update(time="morning", time_jump=True)
        beat(d, "12-goodnight").update(time="night")
    assert not hits(mutated(jump), "time_of_day")


def test_arc_coverage_missing_beat_and_order():
    rep = mutated(lambda d: d["beats"].remove(beat(d, "09-almost")))
    f = hits(rep, "arc_coverage", "MED")
    assert f and "beat 7" in f[0]["msg"]
    def swap(d):
        beat(d, "06-kitchen")["beat"], beat(d, "07-garden")["beat"] = 5, 4
    assert hits(mutated(swap), "arc_coverage", "LOW")
    # a merged page covers both beats
    def merge(d):
        d["beats"].remove(beat(d, "05-decide"))
        beat(d, "04-problem")["beat"] = [2, 3]
    assert not hits(mutated(merge), "arc_coverage")


def test_trait_drift_is_high():
    rep = mutated(lambda d: beat(d, "07-garden").update(
        traits={"Mia": {"outfit": "dress"}}))
    f = hits(rep, "trait_drift", "HIGH")
    assert f and "outfit" in f[0]["msg"] and not rep["ok"]
    rep = mutated(lambda d: beat(d, "07-garden").update(
        traits={"Mia": {"glasses": True}}))           # same value: no drift
    assert not hits(rep, "trait_drift")
    rep = mutated(lambda d: beat(d, "07-garden").update(
        cast={"Mia": {"hair": "bob"}, "Rex": {}}))
    assert hits(rep, "trait_drift", "HIGH")


def test_bible_ref_unknowns():
    rep = mutated(lambda d: beat(d, "07-garden").update(
        cast=["Mia", "Rex", "Zed"], location="moon", kind="poster"))
    msgs = " ".join(f["msg"] for f in hits(rep, "bible_ref"))
    assert "'Zed'" in msgs and "'moon'" in msgs and "'poster'" in msgs


def test_themed_mode_skips_story_rules():
    def themed(d):
        d["mode"] = "themed"
        d["refrain"] = None
        d["beats"] = [b for b in d["beats"] if b.get("beat") != 8]
        beat(d, "03-intro")["caption"] = "Mia rides a bike."
    rep = mutated(themed)
    for rule in ("refrain", "arc_coverage", "caption_length", "solve_actor"):
        assert not hits(rep, rule), rule


# ---------------------------------------------------------------- outline + io
def test_outline_lists_pages_captions_and_gaps():
    out = S.StoryBible.from_dict(clean_dict()).outline()
    for b in clean_dict()["beats"]:
        assert b["page"] in out
    assert '"Mia and Rex look everywhere"' in out and "MISSING" not in out
    d = clean_dict()
    d["beats"].remove(beat(d, "09-almost"))
    assert "7 Almost there: MISSING" in S.StoryBible.from_dict(d).outline()


def test_json_round_trip(tmp_path):
    b = S.StoryBible.from_dict(clean_dict())
    p = tmp_path / "story.json"
    b.save(p)
    b2 = S.StoryBible.load(p)
    assert b2.to_dict() == b.to_dict()
    assert json.loads(p.read_text()) == b.to_dict()
    assert b2.traits("Mia") == MIA and b2.traits("Mia") is not MIA


def test_python_constructor_accepts_shorthand():
    b = S.StoryBible("T", cast={"Mia": dict(MIA, role="hero")},
                     props={"Bun": {"timeline": {"8": "found", "2": "missing"}}})
    assert b.cast["Mia"] == {"role": "hero", "traits": MIA}
    assert [x["beat"] for x in b.props["Bun"]["timeline"]] == [2, 8]
    assert S.StoryBible.from_dict(b.to_dict()).to_dict() == b.to_dict()


def test_arc_data():
    assert [a["beat"] for a in S.ARC_10] == list(range(1, 11))
    assert S.ARC_10[S.SOLVE_BEAT - 1]["name"] == "Solve"


# ---------------------------------------------------------------- SVG records
def _page(caption, kids=2, title="T"):
    body = "".join(matted(G(200 + 220 * i, 935, kid_stand(MIA), 1.3))
                   for i in range(kids))
    body += matted(G(700, 935, dog_sit(REX), 1.2))   # not a figure group
    return spage(title, body, num=3, caption=caption)


def test_annotate_read_round_trip(tmp_path):
    bible = S.StoryBible.from_dict(clean_dict())
    b = bible.beat("10-solve")
    svg = _page(b["caption"], kids=1)
    a = S.annotate(svg, b)
    assert S.annotate(a, b) == a                   # idempotent
    assert S.strip_annotation(a) == svg
    p = tmp_path / "10-solve.svg"
    p.write_text(a)
    r = S.read_pages([str(p)])[0]
    assert r["story"] == S.story_record(b) and r["page"] == "10-solve"
    assert r["caption"] == b["caption"] and r["title"] == "T"
    assert r["figures"] == 1                       # mats + dog_sit excluded


def test_annotation_leaves_validator_and_render_unchanged():
    import cairosvg
    b = clean_dict()["beats"][2]
    svg = _page(b["caption"] + ' & <tag> "quoted"')
    a = S.annotate(svg, dict(b, caption=b["caption"] + ' & <tag> "q"'))
    assert V.validate_svg(a) == V.validate_svg(svg)
    assert V.lint_book([a, a]) == V.lint_book([svg, svg])
    assert (cairosvg.svg2png(bytestring=a.encode(), output_width=200) ==
            cairosvg.svg2png(bytestring=svg.encode(), output_width=200))


def test_page_cross_checks(tmp_path):
    bible = S.StoryBible.from_dict(clean_dict())
    b = bible.beat("11-picnic")                    # Mia + Grandpa + Rex
    paths = []
    # one person drawn for two people; caption differs; record is stale
    stale = dict(b, caption="Old words.")
    svg = S.annotate(_page("Old words.", kids=1), stale)
    p = tmp_path / "11-picnic.svg"
    p.write_text(svg)
    paths.append(str(p))
    rep = run(pages=paths)
    assert hits(rep, "figure_count", "MED")
    assert hits(rep, "caption_mismatch", "MED")
    assert hits(rep, "stale_annotation", "MED")
    # unannotated page found by file name: one LOW, nothing else
    q = tmp_path / "10-solve.svg"
    q.write_text(_page(bible.caption("10-solve"), kids=1))
    rep = run(pages=[str(q)])
    assert [f["check"] for f in rep["findings"]] == ["annotation"]
    # data-scene disagreement between two pages of one location
    s1 = S.annotate(_page(bible.caption("03-intro")),
                    bible.beat("03-intro")).replace(
        "<g data-chrome", '<g data-scene="room:0"></g><g data-chrome', 1)
    s2 = S.annotate(_page(bible.caption("04-problem")),
                    bible.beat("04-problem")).replace(
        "<g data-chrome", '<g data-scene="room:1"></g><g data-chrome', 1)
    recs = [S.read_page(s1, "03-intro.svg"), S.read_page(s2, "04-problem.svg")]
    rep = run(pages=recs)
    assert hits(rep, "scene_variant", "MED")
    assert not hits(rep, "figure_count") and not hits(rep, "caption_mismatch")


# ---------------------------------------------------------------- the example
def test_example_bible_has_no_high_findings():
    rep = S.check(S.StoryBible.load(EXAMPLE_BIBLE))
    assert rep["ok"], [f for f in rep["findings"] if f["severity"] == "HIGH"]
    assert all(rep["arc"][n] for n in range(1, 11))


def test_example_bible_captions_match_make_book():
    src = open(os.path.join(EXAMPLE, "make_book.py")).read()
    caps = sorted(ast.literal_eval(k.value) for k in ast.walk(ast.parse(src))
                  if isinstance(k, ast.keyword) and k.arg == "caption")
    bible = json.load(open(EXAMPLE_BIBLE))
    assert caps == sorted(b["caption"] for b in bible["beats"]
                          if b.get("caption"))


def test_example_pages_cross_check(tmp_path):
    sys.path.insert(0, EXAMPLE)
    try:
        import make_book
    finally:
        sys.path.remove(EXAMPLE)
    bible = S.StoryBible.load(EXAMPLE_BIBLE)
    paths = []
    for name, fn in make_book.BUILDERS:
        p = tmp_path / (name + ".svg")
        p.write_text(bible.annotate(fn(), name))
        paths.append(str(p))
    rep = S.check(bible, paths)
    assert rep["ok"]
    for rule in ("figure_count", "caption_mismatch", "title_mismatch",
                 "stale_annotation", "annotation"):
        assert not hits(rep, rule), hits(rep, rule)


# ---------------------------------------------------------------- CLI
def test_cli_exit_codes(tmp_path):
    ok = subprocess.run([PY, "-m", "lib.story", EXAMPLE_BIBLE, "--outline"],
                        cwd=REPO, capture_output=True, text=True)
    assert ok.returncode == 0, ok.stdout + ok.stderr
    assert "== " in ok.stdout and "Arc:" in ok.stdout
    d = clean_dict()
    beat(d, "07-garden")["traits"] = {"Mia": {"outfit": "cape"}}
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(d))
    r = subprocess.run([PY, "-m", "lib.story", str(bad)], cwd=REPO,
                       capture_output=True, text=True)
    assert r.returncode == 1 and "[HIGH] trait_drift" in r.stdout
    usage = subprocess.run([PY, "-m", "lib.story"], cwd=REPO,
                           capture_output=True, text=True)
    assert usage.returncode == 2
