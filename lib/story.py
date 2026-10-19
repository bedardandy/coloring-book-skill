"""Story bible + deterministic continuity linter for story-mode books.

lib/validate.py turned the drawing guide's LAYOUT rules into arithmetic on
one page. This module does the same for the STORY rules in
reference/story-mode.md, across the whole book: write the bible (cast,
locations, props, the page-by-page beat plan with captions) BEFORE drawing,
show bible.outline() to the user, then run check() on the bible alone and
again on the rendered pages.

    from story import StoryBible, check
    bible = StoryBible.load("story.json")
    print(bible.outline())
    rep = check(bible)                       # bible only
    rep = check(bible, ["pages/03-intro.svg", ...])   # + rendered cross-checks
    if not rep["ok"]: ...

Rules (findings use lib/validate.py's {severity, check, msg} shape, plus the
page id they concern; HIGH = ship-blocker, MED = likely-visible story
violation, LOW = lint):

  caption_length   story scene captions hold 15-25 words (MED outside)
  cast_name        a scene caption names at least one cast member (MED);
                   the hero, when on the page, is named (LOW)
  pronoun_only     pronouns outnumber cast-name mentions (LOW)
  past_tense       a short list of unambiguous past-tense verbs (LOW)
  rhyme            adjacent sentence endings rhyme (LOW; repeats are fine)
  cozy_words       scary vocabulary: monster, scary, dark forest, hurt,
                   cry... (MED; bible.allow_words opts a word back in, e.g.
                   "monster" for the Very Shy Monster trope)
  refrain_drift    a caption paraphrases the refrain instead of quoting it
                   word for word (LOW)
  refrain          the refrain is declared, appears, is introduced by beat 3
                   and recurs at least every 2 story pages until the solve
                   beat (MED; late introduction LOW)
  solve_actor      a child (hero/sibling) ACTS on the solve beat: HIGH when
                   the actor is an adult, undeclared or not on the page; MED
                   when only the pet acts
  cast_presence    every cast member named in a caption is on that page, and
                   the declared actor is too (MED)
  actor            a story scene beat declares who acts (LOW)
  prop_state       HIGH: a prop drawn (present/found/held) on a beat inside
                   its missing window; MED: a held prop whose holder is not
                   on the page
  location         the same location drawn with a different scene-kit
                   variant, or a continuity anchor (window, bed, tree) on
                   the other side (MED)
  time_of_day      time runs backwards without a declared time_jump (LOW)
  arc_coverage     story mode covers every beat of the 10-beat arc (MED);
                   beats out of order (LOW)
  trait_drift      a page overrides a cast member's trait — outfit, hair,
                   glasses... — the skill says never override per page (HIGH)
  bible_ref        unknown cast/prop/location/kind references (MED/LOW)

With rendered pages (read_pages: annotate() embeds each page's beat as a
<metadata data-story="..."> record that cairosvg does not draw and
lib/validate.py does not see):

  annotation       a page carries no story record (LOW) or a record that no
                   longer matches the bible (MED stale_annotation)
  caption_mismatch the caption drawn on the page differs from the bible (MED)
  title_mismatch   the drawn title differs from a declared beat title (LOW)
  figure_count     fewer data-el="figure" groups than people the beat puts
                   on the page (MED; pets are not counted — dog_sit/dog_sleep
                   are not figure-tagged)
  scene_variant    pages of one location carry different data-scene values
                   (MED; only when the art emits data-scene)

CLI: `python3 -m lib.story story.json [pages/*.svg] [--outline]` prints the
findings like `python3 -m lib.validate` and exits 1 on any HIGH.
"""
import copy
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape as _xml_escape

# ------------------------------------------------------------------ the arc
ARC_10 = (
    {"beat": 1, "name": "Intro",
     "purpose": "the child + home/setting"},
    {"beat": 2, "name": "Problem",
     "purpose": "the problem or invitation appears (lost toy, surprise note, "
                "shy new pet)"},
    {"beat": 3, "name": "Decide",
     "purpose": "the cast decides to act (sibling/pet joins); refrain "
                "introduced"},
    {"beat": 4, "name": "First try",
     "purpose": "first look/try: a small discovery, not the answer"},
    {"beat": 5, "name": "Second try",
     "purpose": "a different room/place; repeatable page pattern"},
    {"beat": 6, "name": "Third try",
     "purpose": "a pet or sibling contributes the key clue"},
    {"beat": 7, "name": "Almost there",
     "purpose": "a gentle setback (it rolled under the bed; the kitten "
                "hides)"},
    {"beat": 8, "name": "Solve",
     "purpose": "the child does the solving action themselves"},
    {"beat": 9, "name": "Celebrate",
     "purpose": "the full cast together (dance, picnic, high-five)"},
    {"beat": 10, "name": "Cozy end",
     "purpose": "home/bedtime/\"The End\" wave; dedication line"},
)
SOLVE_BEAT = 8
REFRAIN_BY = 3             # the refrain is introduced on beat 3

# ------------------------------------------------------------------ vocab
KINDS = ("cover", "names", "scene", "activity", "creative", "back")
STORY_KINDS = ("scene", "activity", "creative")   # narrative caption pages
ROLES = ("hero", "sibling", "pet", "adult")
CHILD_ROLES = ("hero", "sibling")
WORDS_MIN, WORDS_MAX = 15, 25   # story-mode.md: 15-25 words per page
REFRAIN_EVERY = 2               # ... a refrain every 1-2 pages

# prop states a page can show. VISIBLE ones put the prop in the art; HINT
# ones are allowed while it is missing (a peeking silhouette, a thought
# bubble, the empty spot it used to sit in)
VISIBLE_STATES = ("present", "found", "held")
HINT_STATES = ("missing", "hidden", "imagined")
TIMELINE_STATES = ("present", "missing", "found")

# trait keys that make a character recognisable (charlib kid_stand /
# face_traits / dog read these); a per-page override of any of them is drift
IDENTITY_KEYS = ("name", "hair", "glasses", "freckles", "outfit", "height",
                 "headband", "beard", "face_seed", "motif", "coat",
                 "floppy_ears", "collar", "species")

TIME_RANK = {"dawn": 0, "morning": 1, "day": 2, "midday": 2, "noon": 2,
             "afternoon": 3, "evening": 4, "dusk": 4, "sunset": 4,
             "night": 5, "bedtime": 5}

# kept SHORT on purpose: each entry must be past tense in every reading a
# picture-book caption would use ("lost", "left", "thought", "felt" are
# adjectives/nouns/directions too often and are deliberately absent)
PAST_TENSE = frozenset("""
was were went saw found looked said came ran got had did took gave ate sat
fell hid heard told knew played jumped walked searched peeked giggled laughed
smiled waved hugged danced cheered clapped opened rolled climbed wanted tried
slept woke flew swam drew began brought caught kept
""".split())
PRONOUNS = frozenset("he she they him her them his hers their".split())

# scary vocabulary: obstacles stay hidden/shy/sleepy/wobbly, never threats
SCARY_WORDS = frozenset("""
monster monsters scary scared scare frightened afraid terrified ghost ghosts
witch danger dangerous hurt hurts cry cries crying cried scream screams
screaming dead die dies kill blood trapped nightmare
""".split())
SCARY_PHRASES = ("dark forest", "lost forever", "never come back",
                 "all alone in the dark")
RHYME_SKIP = frozenset(("ing", "ings"))   # -ing endings are grammar, not rhyme

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'’-]*")
_SENT_RE = re.compile(r"[^.!?]+[.!?]*")
_META_RE = re.compile(r"<metadata data-story=\"[^\"]*\"\s*/>")
_SVG_OPEN_RE = re.compile(r"<svg\b[^>]*>")
_SVG_NS = "{http://www.w3.org/2000/svg}"
_SIDES = {"left": "left", "right": "right", "center": "center",
          "centre": "center", "middle": "center", "back": "back"}

# beat fields carried in a page's embedded record (and compared for staleness)
RECORD_KEYS = ("page", "kind", "beat", "location", "cast", "actor", "props",
               "caption", "title", "time", "time_jump", "variant", "anchors",
               "traits")


# ------------------------------------------------------------------ helpers
def _as_list(v):
    if v is None:
        return []
    if isinstance(v, (list, tuple)):
        return list(v)
    return [v]


def _words(text):
    return _WORD_RE.findall(text or "")


def _norm(text):
    """Lowercase letters-only form with single spaces, padded so phrase
    matching is whole-word: ' max and lily look everywhere '."""
    return " " + " ".join(re.sub(r"[^a-z]+", " ",
                                 (text or "").lower()).split()) + " "


def _bare(word):
    """Word without a possessive tail: "Max's" -> "Max"."""
    return re.sub(r"['’]s?$", "", word)


def _stem(word):
    w = word.lower()
    for suf in ("ing", "es", "ed", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            return w[:-len(suf)]
    return w


def _rime(word):
    """Crude rhyme key: the last vowel group plus trailing consonants, with
    a silent final e reaching back one group (here/there -> 'ere')."""
    w = re.sub(r"[^a-z]", "", word.lower())
    if len(w) < 3:
        return ""

    def vowel(i):
        return w[i] in "aeiou" or (w[i] == "y" and i == len(w) - 1)

    end = len(w) - 1
    if w[-1] == "e" and not vowel(len(w) - 2):
        end = len(w) - 2              # silent e: skip it, find the real vowel
    i = end
    while i >= 0 and not vowel(i):
        i -= 1
    if i < 0:
        i = len(w) - 1
        while i >= 0 and not vowel(i):
            i -= 1
        if i < 0:
            return ""
    while i > 0 and vowel(i - 1):
        i -= 1
    return w[i:]


def _side(pos):
    """Normalise an anchor position ("left wall", "on the right") to
    left/right/center/back, or the lowercased text when no side word."""
    for tok in re.findall(r"[a-z]+", str(pos).lower()):
        if tok in _SIDES:
            return _SIDES[tok]
    return str(pos).strip().lower()


def _names_in(text, names):
    """Cast names mentioned in text (whole word, possessive-tolerant), in
    first-mention order, plus the total mention count."""
    seen, total = [], 0
    names = set(names)
    for w in _words(text):
        b = _bare(w)
        if b in names:
            total += 1
            if b not in seen:
                seen.append(b)
    return seen, total


def _finding(sev, check_, msg, page=None):
    return {"severity": sev, "check": check_, "msg": msg, "page": page}


def _report(findings, **extra):
    counts = {"HIGH": 0, "MED": 0, "LOW": 0}
    for f_ in findings:
        counts[f_["severity"]] += 1
    rep = {"ok": counts["HIGH"] == 0, "findings": findings, "counts": counts}
    rep.update(extra)
    return rep


# ------------------------------------------------------------------ the bible
class StoryBible:
    """The book's single source of truth for story continuity.

    cast       {name: {"role": hero|sibling|pet|adult, "traits": {...}}} —
               traits are the SAME dicts charlib's kid_stand()/face_traits()
               /dog() consume (copy them verbatim from make_book.py; a flat
               trait dict with a "role" key is accepted too)
    locations  {id: {"kit": scene kit or "room", "variant": n,
               "anchors": {"window": "left", "bed": "left"}, "desc": ...}} —
               anchors are the persistent things every page of the place
               draws in the same spot
    props      {id: {"desc": ..., "timeline": [{"beat": 1, "state":
               "present"}, {"beat": 2, "state": "missing"}, {"beat": 8,
               "state": "found"}]}}
    beats      one dict per PAGE, in book order: page (builder id), kind
               (cover/names/scene/activity/creative/back), beat (arc number,
               or a list when one page carries two beats), location, cast
               (names on the page), actor (who ACTS), props ({id: state} or
               {id: {"state": "held", "holder": name}}), caption, title,
               time (dawn..night), time_jump, variant / anchors (as drawn on
               this page), traits (per-page overrides — always a finding)
    """

    def __init__(self, title, *, age_band="3-6", mode="story", trope=None,
                 refrain=None, refrain_variants=(), cast=None, locations=None,
                 props=None, beats=None, allow_words=(), notes=None):
        self.title = title
        self.age_band = age_band
        self.mode = mode
        self.trope = trope
        self.refrain = refrain
        self.refrain_variants = list(refrain_variants or ())
        self.cast = {n: self._norm_cast(e) for n, e in (cast or {}).items()}
        self.locations = {k: dict(v) for k, v in (locations or {}).items()}
        self.props = {k: self._norm_prop(v) for k, v in (props or {}).items()}
        self.beats = [dict(b) for b in (beats or [])]
        self.allow_words = list(allow_words or ())
        self.notes = notes

    @staticmethod
    def _norm_cast(entry):
        e = copy.deepcopy(entry)
        if "traits" not in e:                    # flat trait dict + role
            role = e.pop("role", None)
            e = {"role": role, "traits": e}
        return e

    @staticmethod
    def _norm_prop(entry):
        e = copy.deepcopy(entry)
        tl = e.get("timeline") or []
        if isinstance(tl, dict):                 # {beat: state}
            tl = [{"beat": int(b), "state": s} for b, s in tl.items()]
        else:                                    # [[beat, state], ...] too
            tl = [x if isinstance(x, dict) else {"beat": int(x[0]),
                                                  "state": x[1]} for x in tl]
        e["timeline"] = sorted(tl, key=lambda x: x["beat"])
        return e

    # ---- serialisation -----------------------------------------------------
    def to_dict(self):
        out = {"title": self.title, "age_band": self.age_band,
               "mode": self.mode, "trope": self.trope,
               "refrain": self.refrain}
        if self.refrain_variants:
            out["refrain_variants"] = list(self.refrain_variants)
        if self.allow_words:
            out["allow_words"] = list(self.allow_words)
        if self.notes:
            out["notes"] = self.notes
        out.update(cast=copy.deepcopy(self.cast),
                   locations=copy.deepcopy(self.locations),
                   props=copy.deepcopy(self.props),
                   beats=copy.deepcopy(self.beats))
        return out

    @classmethod
    def from_dict(cls, d):
        d = dict(d)
        title = d.pop("title")
        known = ("age_band", "mode", "trope", "refrain", "refrain_variants",
                 "cast", "locations", "props", "beats", "allow_words", "notes")
        return cls(title, **{k: d[k] for k in known if k in d})

    @classmethod
    def load(cls, path):
        with open(path, encoding="utf-8") as fh:
            return cls.from_dict(json.load(fh))

    def save(self, path):
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=2, ensure_ascii=False)
            fh.write("\n")

    # ---- lookups make_book.py can use (one source of truth) ----------------
    def beat(self, page):
        """The beat dict for a page id (exact, else unique substring)."""
        hits = [b for b in self.beats if b.get("page") == page]
        if not hits:
            hits = [b for b in self.beats if page in str(b.get("page"))]
        if len(hits) != 1:
            raise KeyError(f"no unique beat for page {page!r}")
        return hits[0]

    def caption(self, page):
        """The page's caption, so make_book.py passes spage(caption=
        bible.caption("05-search")) instead of retyping it."""
        return self.beat(page).get("caption")

    def traits(self, name):
        """A COPY of a cast member's trait dict for kid_stand()/dog()."""
        return copy.deepcopy(self.cast[name]["traits"])

    def role(self, name):
        return (self.cast.get(name) or {}).get("role")

    def annotate(self, svg, page):
        """annotate(svg, bible.beat(page)) — embed the page's story record."""
        return annotate(svg, self.beat(page))

    def check(self, pages=None):
        return check(self, pages)

    # ---- the approval table -------------------------------------------------
    def outline(self):
        """Compact text table of the whole plan — show it to the user and get
        a yes BEFORE drawing (cast, props, arc, every caption)."""
        arc_names = {a["beat"]: a["name"] for a in ARC_10}
        head = [f'"{self.title}" - {self.mode} mode, ages {self.age_band}'
                + (f", trope: {self.trope}" if self.trope else "")]
        if self.refrain:
            head.append(f'Refrain: "{self.refrain}"')
        cast = []
        for n, e in self.cast.items():
            t = e.get("traits", {})
            bits = []
            if e.get("species"):
                bits.append(e["species"])
            for k in ("hair", "outfit", "coat"):
                if t.get(k):
                    bits.append(f"{t[k]} {k}" if k != "outfit" else t[k])
            for k in ("glasses", "freckles", "collar", "beard"):
                if t.get(k):
                    bits.append(k)
            if t.get("height"):
                bits.append(f"height {t['height']}")
            cast.append(f"{n} ({e.get('role') or '?'}: {', '.join(bits)})")
        head.append("Cast: " + " | ".join(cast))
        for pid, p in self.props.items():
            tl = " -> ".join(f"{x['state']}@{x['beat']}"
                             for x in p.get("timeline", []))
            head.append(f"Prop: {pid} ({p.get('desc', '')}): {tl}")
        for lid, loc in self.locations.items():
            anc = ", ".join(f"{k} {v}" for k, v in
                            (loc.get("anchors") or {}).items())
            kit = loc.get("kit") or "?"
            if loc.get("variant") is not None:
                kit += f" v{loc['variant']}"
            head.append(f"Place: {lid} ({kit}" + (f"; {anc})" if anc else ")"))

        rows = [("#", "page", "kind", "beat", "where", "time", "on page",
                 "acts", "props")]
        for i, b in enumerate(self.beats, 1):
            bn = _as_list(b.get("beat"))
            props = []
            for pid, st in (b.get("props") or {}).items():
                st = st if isinstance(st, dict) else {"state": st}
                props.append(f"{pid}:{st.get('state')}"
                             + (f"({st['holder']})" if st.get("holder") else ""))
            rows.append((str(i), str(b.get("page", "?")),
                         b.get("kind", "scene"),
                         "+".join(f"{n} {arc_names.get(n, '?')}" for n in bn)
                         or "-",
                         b.get("location") or "-", b.get("time") or "-",
                         " ".join(_as_list(b.get("cast"))) or "-",
                         " ".join(_as_list(b.get("actor"))) or "-",
                         " ".join(props) or "-"))
        widths = [max(len(r[c]) for r in rows) for c in range(len(rows[0]))]
        body = []
        for r_i, r in enumerate(rows):
            body.append("  ".join(v.ljust(widths[c])
                                  for c, v in enumerate(r)).rstrip())
            if r_i == 0:
                continue
            b = self.beats[r_i - 1]
            if b.get("caption"):
                n = len(_words(b["caption"]))
                tag = (", refrain" if self.refrain and _has_refrain(
                    b["caption"], self) else "")
                body.append(f'      "{b["caption"]}" ({n} words{tag})')
        covered = {}
        for b in self.beats:
            for n in _as_list(b.get("beat")):
                covered.setdefault(n, []).append(str(b.get("page")))
        arc = [f"{a['beat']} {a['name']}: "
               + (", ".join(covered[a["beat"]]) if a["beat"] in covered
                  else "MISSING") for a in ARC_10]
        tail = ["Arc: " + " | ".join(arc)] if self.mode == "story" else []
        return "\n".join(head + [""] + body + [""] + tail).rstrip() + "\n"


# ------------------------------------------------------------------ captions
def _has_refrain(text, bible_or_refrain):
    if isinstance(bible_or_refrain, StoryBible):
        forms = [bible_or_refrain.refrain] + bible_or_refrain.refrain_variants
    else:
        forms = _as_list(bible_or_refrain)
    t = _norm(text)
    return any(f and _norm(f) in t for f in forms)


def lint_caption(text, cast, refrain=None, *, kind="scene", hero=None,
                 present=None, allow_words=(), story=True, page=None):
    """Single-caption story rules. Returns a list of findings.

    cast: cast names (iterable, or the bible's cast dict). refrain: the
    refrain line (or a list of accepted forms) — used to spot paraphrases.
    kind: the page kind (length/name rules judge "scene" captions; tense,
    pronoun and rhyme lint judge every narrative kind). hero: the hero's
    name, judged only when `present` (names on the page) includes them.
    present: names on the page; enables the cast_presence rule.
    story=False (themed books) keeps only the cozy and presence rules."""
    out = []

    def add(sev, check_, msg):
        out.append(_finding(sev, check_, msg, page))

    where = f"{page}: " if page else ""
    text = text or ""
    names = list(cast.keys()) if isinstance(cast, dict) else list(cast or ())
    words = _words(text)
    lower = [w.lower() for w in words]
    allow = {w.lower() for w in allow_words}
    named, mentions = _names_in(text, names)
    narrative = story and kind in STORY_KINDS

    # ---- cozy vocabulary (every caption, every mode) ------------------------
    scary = sorted({_bare(w) for w in lower if _bare(w) in SCARY_WORDS}
                   - allow)
    t_norm = _norm(text)
    scary += [p for p in SCARY_PHRASES
              if _norm(p) in t_norm and p not in allow]
    if scary:
        add("MED", "cozy_words",
            f"{where}scary wording {scary} — obstacles stay hidden, shy, "
            f"sleepy or wobbly, never a threat; reword (or list the word in "
            f"the bible's allow_words when the trope needs it)")

    # ---- named cast members must be on the page -----------------------------
    if present is not None and kind in STORY_KINDS:
        absent = [n for n in named if n not in present]
        if absent:
            add("MED", "cast_presence",
                f"{where}caption names {absent} but the beat does not put "
                f"them on the page — draw them, add them to the beat's cast, "
                f"or reword")

    if not narrative:
        return out

    # ---- length + names (scene pages) ---------------------------------------
    if kind == "scene":
        n = len(words)
        if not WORDS_MIN <= n <= WORDS_MAX:
            add("MED", "caption_length",
                f"{where}caption has {n} words; story scene pages want "
                f"{WORDS_MIN}-{WORDS_MAX} — "
                + ("trim a sentence" if n > WORDS_MAX
                   else "add one simple present-tense sentence"))
        if not named:
            add("MED", "cast_name",
                f"{where}caption names no cast member — repeat the child's "
                f"name at least once per page instead of pronouns")
        elif (hero and present is not None and hero in present
              and hero not in named):
            add("LOW", "cast_name",
                f"{where}{hero} (the hero) is on the page but not named in "
                f"the caption")

    # ---- conservative grammar lint -------------------------------------------
    pron = sum(1 for w in lower if w in PRONOUNS)
    if pron and pron > mentions:
        add("LOW", "pronoun_only",
            f"{where}{pron} pronoun(s) vs {mentions} name mention(s) — swap "
            f"a he/she/they for the name (pre-readers track names, not "
            f"pronouns)")
    past = sorted({w for w in lower if w in PAST_TENSE})
    if past:
        add("LOW", "past_tense",
            f"{where}past tense {past} — captions use simple present "
            f"(\"finds\", not \"found\")")

    # ---- rhyme: adjacent sentence endings -------------------------------------
    ends = []
    for s_ in _SENT_RE.findall(text):
        ws = _words(s_)
        if ws:
            ends.append(ws[-1])
    for a, b in zip(ends, ends[1:]):
        ra, rb = _rime(a), _rime(b)
        if (len(ra) >= 2 and ra == rb and ra not in RHYME_SKIP
                and a.lower() != b.lower()):
            add("LOW", "rhyme",
                f"{where}adjacent sentences end in rhyme ('{a}' / '{b}') — "
                f"story mode is rhyme-free (templated rhyme reads clunky)")

    # ---- refrain paraphrase ----------------------------------------------------
    forms = [f for f in _as_list(refrain) if f]
    if forms and not _has_refrain(text, forms):
        for f in forms:
            key = {_stem(w) for w in _words(f)
                   if _bare(w) not in names and len(w) > 3}
            have = {_stem(w) for w in words}
            if key and key <= have:
                add("LOW", "refrain_drift",
                    f"{where}caption paraphrases the refrain — quote it word "
                    f"for word (\"{f}\") so kids can chant along")
                break
    return out


# ------------------------------------------------------------------ book check
def _norm_props(b):
    out = {}
    for pid, st in (b.get("props") or {}).items():
        out[pid] = dict(st) if isinstance(st, dict) else {"state": st}
    return out


def _beat_cast(b):
    c = b.get("cast")
    if isinstance(c, dict):
        return list(c.keys())
    return _as_list(c)


def _prop_state_at(prop, beat_no):
    """(state, since_beat, until_beat) from the timeline at beat_no."""
    tl = prop.get("timeline") or []
    state, since, until = None, None, None
    for i, x in enumerate(tl):
        if x["beat"] <= beat_no:
            state, since = x["state"], x["beat"]
            until = tl[i + 1]["beat"] if i + 1 < len(tl) else None
    return state, since, until


def check(bible, pages=None):
    """Lint a StoryBible (and optionally its rendered pages: SVG paths or
    read_pages() records). Returns {ok, findings, counts, arc}."""
    if isinstance(bible, (str, os.PathLike)):
        bible = StoryBible.load(bible)
    elif isinstance(bible, dict):
        bible = StoryBible.from_dict(bible)
    findings = []

    def add(sev, check_, msg, page=None):
        findings.append(_finding(sev, check_, msg, page))

    story = bible.mode == "story"
    heroes = [n for n, e in bible.cast.items() if e.get("role") == "hero"]
    hero = heroes[0] if heroes else None

    # ---- cast entries --------------------------------------------------------
    for n, e in bible.cast.items():
        if e.get("role") not in ROLES:
            add("MED", "bible_ref",
                f"cast {n}: role {e.get('role')!r} is not one of {list(ROLES)}")
        tn = (e.get("traits") or {}).get("name")
        if tn and tn != n:
            add("MED", "bible_ref",
                f"cast {n}: traits say name={tn!r} — key the cast by the "
                f"name the captions use")
    if story and not heroes:
        add("MED", "bible_ref", "no cast member has role 'hero' — the child "
            "who acts and solves")

    seen_pages = {}
    arc = {}
    loc_first = {}          # location -> {anchor: (side, page)}, variant
    last_time = None        # (rank, page)
    last_beat = None        # (max beat, page)
    refrain_seen = False
    refrain_first = None
    misses = []             # consecutive quest pages without the refrain

    for b in bible.beats:
        pid = str(b.get("page") or "?")
        kind = b.get("kind", "scene")
        beats = _as_list(b.get("beat"))
        cast = _beat_cast(b)
        actors = _as_list(b.get("actor"))
        props = _norm_props(b)
        tag = f"{pid}" + (f" (beat {'+'.join(map(str, beats))})"
                          if beats else "")

        if pid in seen_pages:
            add("MED", "bible_ref", f"{pid}: page id used twice", pid)
        seen_pages[pid] = b
        if kind not in KINDS:
            add("MED", "bible_ref",
                f"{pid}: kind {kind!r} is not one of {list(KINDS)}", pid)
        for n in beats:
            if n not in range(1, len(ARC_10) + 1):
                add("MED", "bible_ref",
                    f"{pid}: beat {n!r} is not on the 10-beat arc", pid)
            else:
                arc.setdefault(n, []).append(pid)
        for n in cast + actors:
            if n not in bible.cast:
                add("MED", "bible_ref",
                    f"{pid}: {n!r} is not in the cast — add a trait dict for "
                    f"them or fix the spelling", pid)
        loc = b.get("location")
        if loc and loc not in bible.locations:
            add("MED", "bible_ref",
                f"{pid}: location {loc!r} is not declared in the bible", pid)

        # ---- arc order ------------------------------------------------------
        if beats and story:
            if last_beat and min(beats) < last_beat[0]:
                add("LOW", "arc_coverage",
                    f"{tag}: comes after {last_beat[1]} (beat "
                    f"{last_beat[0]}) — beats run out of arc order", pid)
            last_beat = (max(beats), pid)

        # ---- trait drift ---------------------------------------------------
        over = dict(b.get("traits") or {})
        if isinstance(b.get("cast"), dict):
            for n, o in b["cast"].items():
                if o:
                    over.setdefault(n, {}).update(o)
        for n, o in over.items():
            base = (bible.cast.get(n) or {}).get("traits", {})
            for k, v in (o or {}).items():
                if k in base and base[k] == v:
                    continue
                if k in base or k in IDENTITY_KEYS:
                    add("HIGH", "trait_drift",
                        f"{pid}: overrides {n}'s {k} ({base.get(k)!r} -> "
                        f"{v!r}) — never override a trait per page; the same "
                        f"dict on every page is what makes {n} recognisable",
                        pid)

        # ---- captions ---------------------------------------------------------
        cap = b.get("caption")
        if cap:
            findings.extend(lint_caption(
                cap, bible.cast, bible.refrain and
                [bible.refrain] + bible.refrain_variants, kind=kind,
                hero=hero, present=cast, allow_words=bible.allow_words,
                story=story, page=pid))
        title = b.get("title")
        if title:
            for f_ in lint_caption(title, bible.cast, kind="cover",
                                   allow_words=bible.allow_words,
                                   page=pid):
                f_["msg"] = f_["msg"].replace("scary wording",
                                              "scary title wording")
                findings.append(f_)

        # ---- actor ----------------------------------------------------------
        if story and kind == "scene" and beats and not actors:
            add("LOW", "actor",
                f"{tag}: no actor declared — name who ACTS on this page (the "
                f"child acts, never watches)", pid)
        for a in actors:
            if a in bible.cast and a not in cast:
                sev = "HIGH" if story and SOLVE_BEAT in beats else "MED"
                add(sev, "cast_presence",
                    f"{tag}: {a} acts but is not on the page — add {a} to the "
                    f"beat's cast and draw them", pid)
        if story and SOLVE_BEAT in beats:
            roles = [bible.role(a) for a in actors if a in cast]
            if not any(r in CHILD_ROLES for r in roles):
                if roles and all(r == "pet" for r in roles):
                    add("MED", "solve_actor",
                        f"{tag}: only the pet acts on the solve beat — let the "
                        f"pet bring the clue and the child do the final "
                        f"action (pull it out, open the box)", pid)
                else:
                    who = ", ".join(actors) or "nobody"
                    add("HIGH", "solve_actor",
                        f"{tag}: the solve beat's actor is {who} — the child "
                        f"(hero/sibling) does the solving action themselves; "
                        f"adults stay background", pid)

        # ---- props ------------------------------------------------------------
        for prid, st in props.items():
            if prid not in bible.props:
                add("LOW", "bible_ref",
                    f"{pid}: prop {prid!r} is not declared in the bible", pid)
                continue
            state = st.get("state")
            if state not in VISIBLE_STATES + HINT_STATES:
                add("LOW", "bible_ref",
                    f"{pid}: {prid} state {state!r} is not one of "
                    f"{list(VISIBLE_STATES + HINT_STATES)}", pid)
            if state == "held":
                h = st.get("holder")
                if not h:
                    add("LOW", "prop_state",
                        f"{pid}: {prid} is held but no holder is declared",
                        pid)
                elif h not in cast:
                    add("MED", "prop_state",
                        f"{pid}: {prid} is held by {h}, who is not on the "
                        f"page — draw {h} or set the prop down", pid)
            if beats and state in VISIBLE_STATES:
                for n in beats:
                    tl_state, since, until = _prop_state_at(
                        bible.props[prid], n)
                    if tl_state == "missing":
                        add("HIGH", "prop_state",
                            f"{tag}: {prid} is drawn ({state}) but it is "
                            f"missing from beat {since} until "
                            + (f"it is found on beat {until}" if until
                               else "the end")
                            + " — remove it from the art, or show only a "
                              "hint (state 'hidden': a peeking silhouette; "
                              "'imagined': a thought bubble)", pid)
                        break

        # ---- location continuity ---------------------------------------------
        if loc and loc in bible.locations:
            spec = bible.locations[loc]
            first = loc_first.setdefault(loc, {"anchors": {}, "variant": None})
            v = b.get("variant")
            want, ref = spec.get("variant"), None
            if v is not None and want is not None:
                ref = None if v == want else f"the bible says variant {want}"
            elif v is not None and first["variant"] is None:
                first["variant"] = (v, pid)       # first page sets the look
            elif v is not None and v != first["variant"][0]:
                ref = (f"{first['variant'][1]} drew variant "
                       f"{first['variant'][0]}")
            if ref:
                add("MED", "location",
                    f"{pid}: {loc} is drawn with scene variant {v} but {ref}"
                    f" — keep one variant per location across the book", pid)
            moved = []
            for name, pos in (b.get("anchors") or {}).items():
                side = _side(pos)
                canon = (spec.get("anchors") or {}).get(name)
                if canon is not None:
                    if _side(canon) != side:
                        moved.append(f"{name} on the {side} (bible: "
                                     f"{_side(canon)})")
                elif name in first["anchors"]:
                    s0, p0 = first["anchors"][name]
                    if s0 != side:
                        moved.append(f"{name} on the {side} ({p0}: {s0})")
                else:
                    first["anchors"][name] = (side, pid)
            if moved:
                add("MED", "location",
                    f"{pid}: the {loc} draws " + ", ".join(moved)
                    + " — a recurring place keeps its window/furniture/tree "
                      "in the same spot on every page (GM() the furniture "
                      "or move it)", pid)

        # ---- time of day ---------------------------------------------------------
        t = b.get("time")
        if t:
            rank = TIME_RANK.get(str(t).lower())
            if rank is None:
                add("LOW", "time_of_day",
                    f"{pid}: time {t!r} is not one of {sorted(TIME_RANK)}",
                    pid)
            else:
                if (last_time and rank < last_time[0]
                        and not b.get("time_jump")):
                    add("LOW", "time_of_day",
                        f"{pid}: time goes back to {t} after {last_time[1]} "
                        f"— set time_jump: true on a deliberate jump (next "
                        f"morning) or fix the sky/lamps", pid)
                last_time = (rank, pid)

        # ---- refrain recurrence ----------------------------------------------------
        if story and bible.refrain and cap and kind in STORY_KINDS:
            has = _has_refrain(cap, bible)
            if has and not refrain_seen:
                refrain_seen, refrain_first = True, (pid, beats)
            quest = not beats or max(beats) < SOLVE_BEAT
            if refrain_seen and quest:
                if has:
                    misses = []
                else:
                    misses.append(pid)
                    if len(misses) >= REFRAIN_EVERY:
                        add("MED", "refrain",
                            f"{', '.join(misses)}: {len(misses)} story pages "
                            f"in a row without the refrain \"{bible.refrain}\""
                            f" — repeat it word for word every 1-2 pages "
                            f"until the solve", pid)
                        misses = []

    # ---- book-level rules -----------------------------------------------------------
    if story:
        if not bible.refrain:
            add("MED", "refrain", "story mode declares no refrain — add a "
                "chant-along line (\"[Name] and [Pet] look everywhere!\")")
        elif not refrain_seen:
            add("MED", "refrain",
                f"the refrain \"{bible.refrain}\" appears in no caption")
        elif refrain_first[1] and min(refrain_first[1]) > REFRAIN_BY:
            add("LOW", "refrain",
                f"{refrain_first[0]}: the refrain first appears on beat "
                f"{min(refrain_first[1])}; introduce it by beat {REFRAIN_BY}",
                refrain_first[0])
        for a in ARC_10:
            if a["beat"] not in arc:
                add("MED", "arc_coverage",
                    f"beat {a['beat']} ({a['name']}: {a['purpose']}) has no "
                    f"page — give a page that beat (or merge it into a "
                    f"neighbour with beat: [n, m])")
    for prid, p in bible.props.items():
        for x in p.get("timeline", []):
            if x["state"] not in TIMELINE_STATES:
                add("LOW", "bible_ref",
                    f"prop {prid}: timeline state {x['state']!r} is not one "
                    f"of {list(TIMELINE_STATES)}")

    if pages:
        findings.extend(_check_pages(bible, pages))
    return _report(findings, arc={n: arc.get(n, []) for n in
                                  range(1, len(ARC_10) + 1)})


# ------------------------------------------------------------------ SVG records
def story_record(beat):
    """The compact machine-readable record of one beat: its RECORD_KEYS with
    empty fields dropped, plus a schema version."""
    rec = {"v": 1}
    for k in RECORD_KEYS:
        v = beat.get(k)
        if v not in (None, "", [], {}):
            rec[k] = copy.deepcopy(v)
    return rec


def story_attrs(beat):
    """The record as an XML attribute: data-story="{...json...}" (ASCII,
    sorted keys, XML-escaped) — what annotate() puts on <metadata>."""
    js = json.dumps(story_record(beat), sort_keys=True,
                    separators=(",", ":"), ensure_ascii=True)
    return 'data-story="' + _xml_escape(js, {'"': "&quot;"}) + '"'


def annotate(svg, beat):
    """Embed the beat's story record right after the root <svg> tag as
    <metadata data-story="..."/>. cairosvg draws nothing for <metadata> and
    lib/validate.py never walks it, so renders and validator reports are
    unchanged. Idempotent: an existing record is replaced."""
    svg = strip_annotation(svg)
    m = _SVG_OPEN_RE.search(svg)
    if not m:
        raise ValueError("annotate(): no <svg> root tag")
    if m.group(0).endswith("/>"):
        raise ValueError("annotate(): empty <svg/> root")
    return (svg[:m.end()] + f"<metadata {story_attrs(beat)}/>"
            + svg[m.end():])


def strip_annotation(svg):
    """The page without its story record — e.g. before lint_book()'s
    duplicate-page comparison, which compares whole SVG strings."""
    return _META_RE.sub("", svg)


def _local(tag):
    return tag.replace(_SVG_NS, "") if isinstance(tag, str) else ""


def read_page(svg_str, path=None):
    """Recover what the rendered page says about the story: its embedded
    record, the drawn caption/title (glyph-run aria-labels in the page
    chrome), the number of character figure groups (outside knockout
    mats, outermost only) and any data-scene values."""
    root = ET.fromstring(svg_str)
    rec, figures, scenes, cap, title = None, 0, set(), [], []

    def walk(node, in_fig, chrome):
        nonlocal rec, figures
        tag = _local(node.tag)
        if tag == "metadata" and node.get("data-story"):
            try:
                rec = json.loads(node.get("data-story"))
            except ValueError:
                rec = {"error": "unparseable data-story"}
            return
        if node.get("data-scene"):
            scenes.add(node.get("data-scene"))
        if node.get("data-mat") == "1":
            return                         # invisible halo copy of real art
        chrome = chrome or node.get("data-chrome") == "1"
        if tag == "g" and node.get("data-text") == "1":
            if chrome:
                y = float(node.get("data-y") or 0)
                s = node.get("aria-label") or ""
                if y >= 990 and not s.strip().isdigit():
                    cap.append(s)
                elif y < 145:
                    title.append(s)
            return
        fig = tag == "g" and node.get("data-el") == "figure"
        if fig and not in_fig:
            figures += 1
        for ch in node:
            walk(ch, in_fig or fig, chrome)

    walk(root, False, False)
    stem = os.path.splitext(os.path.basename(path))[0] if path else None
    return {"path": path, "page": (rec or {}).get("page") or stem,
            "stem": stem, "story": rec, "figures": figures,
            "scene": sorted(scenes),
            "caption": " ".join(cap) if cap else None,
            "title": " ".join(title) if title else None}


def read_pages(svg_paths):
    """read_page() for each SVG path, in the order given."""
    out = []
    for p in svg_paths:
        with open(p, encoding="utf-8") as fh:
            out.append(read_page(fh.read(), path=str(p)))
    return out


def _check_pages(bible, pages):
    """Conservative cross-checks between the bible and rendered pages."""
    findings = []

    def add(sev, check_, msg, page=None):
        findings.append(_finding(sev, check_, msg, page))

    recs = [read_pages([p])[0] if isinstance(p, (str, os.PathLike)) else p
            for p in pages]
    by_id = {str(b.get("page")): b for b in bible.beats}
    scene_vals = {}                        # location -> {value: page}
    bare = []                              # pages without a story record
    for r in recs:
        name = r.get("path") or r.get("page")
        b = by_id.get(str(r.get("page"))) or by_id.get(str(r.get("stem")))
        if b is None:
            add("LOW", "annotation",
                f"{name}: page {r.get('page')!r} is not in the bible", None)
            continue
        pid = str(b.get("page"))
        rec = r.get("story")
        if rec is None:
            bare.append(pid)
        else:
            want = story_record(b)
            diff = sorted(k for k in set(want) | set(rec)
                          if want.get(k) != rec.get(k))
            if diff:
                add("MED", "stale_annotation",
                    f"{pid}: the page's story record differs from the bible "
                    f"in {diff} — rebuild the page after editing the bible",
                    pid)
        cap = b.get("caption")
        if cap and r.get("caption") is not None and \
                " ".join(cap.split()) != " ".join(r["caption"].split()):
            add("MED", "caption_mismatch",
                f"{pid}: the drawn caption \"{r['caption']}\" differs from "
                f"the bible's — pass caption=bible.caption(...) to spage()",
                pid)
        elif cap and r.get("caption") is None:
            add("LOW", "caption_mismatch",
                f"{pid}: the bible has a caption but none is drawn on the "
                f"page", pid)
        t = b.get("title")
        if t is not None and r.get("title") is not None and \
                " ".join(t.split()) != " ".join(r["title"].split()):
            add("LOW", "title_mismatch",
                f"{pid}: drawn title \"{r['title']}\" vs the bible's "
                f"\"{t}\"", pid)
        people = [n for n in _beat_cast(b)
                  if bible.role(n) in ("hero", "sibling", "adult")]
        if b.get("kind", "scene") in STORY_KINDS + ("cover",) and \
                r.get("figures", 0) < len(people):
            add("MED", "figure_count",
                f"{pid}: the beat puts {len(people)} people on the page "
                f"({', '.join(people)}) but the art has {r.get('figures', 0)}"
                f" figure group(s) — someone the caption promises is not "
                f"drawn", pid)
        loc = b.get("location")
        for v in r.get("scene") or ():
            seen = scene_vals.setdefault(loc, {})
            if loc and seen and v not in seen:
                other = next(iter(seen.items()))
                add("MED", "scene_variant",
                    f"{pid}: {loc} renders data-scene={v!r} but "
                    f"{other[1]} renders {other[0]!r} — one variant per "
                    f"location", pid)
            seen.setdefault(v, pid)
    if bare:
        add("LOW", "annotation",
            f"{len(bare)} rendered page(s) carry no story record "
            f"({', '.join(bare)}) — return story.annotate(svg, "
            f"bible.beat(page)) from each builder so stale pages are caught",
            bare[0] if len(bare) == 1 else None)
    return findings


# ------------------------------------------------------------------ CLI
def _main(argv):
    args = [a for a in argv if a != "--outline"]
    if not args or not args[0].endswith(".json"):
        print(__doc__)
        return 2
    bible = StoryBible.load(args[0])
    if "--outline" in argv:
        print(bible.outline())
    rep = check(bible, args[1:] or None)
    arc = rep["arc"]
    covered = sum(1 for v in arc.values() if v)
    print(f"== {args[0]}: {'OK' if rep['ok'] else 'FAIL'} {rep['counts']}")
    print(f"   {len(bible.beats)} pages, {len(bible.cast)} cast, arc "
          f"{covered}/{len(ARC_10)} beats covered"
          + (f"; {len(args) - 1} rendered page(s) cross-checked"
             if len(args) > 1 else ""))
    for f_ in rep["findings"]:
        print(f"   [{f_['severity']}] {f_['check']}: {f_['msg']}")
    return 1 if rep["counts"]["HIGH"] else 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
