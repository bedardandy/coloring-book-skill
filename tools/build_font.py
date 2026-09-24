#!/usr/bin/env python3
"""Build lib/letters.json from the bundled Andika font (SIL OFL — see
assets/fonts/OFL.txt and CREDITS.md).

Glyph outlines are converted to absolute SVG path data in FONT units
(y-UP); charlib.letter()/word()/text_path() apply the size scale and
y-flip at draw time so the JSON stays resolution-independent. Only glyph
OUTLINES and metrics are stored (shape data, not the font program) — pages
need no font engine and no installed fonts at render time, so the SVG is
byte-identical on every machine and renders never depend on which fonts the
host happens to have (the old <text> pages came out Helvetica on a Mac and
DejaVu Sans on Linux).

Path data uses ONLY absolute M/L/Q/C/Z commands (no H/V shorthands, no
implicit repeats): lib/validate.py pairs path numbers even/odd to measure
bboxes, which one-coordinate H/V commands would silently misalign.

Stored per glyph: "d" (outline), "adv" (advance width — the ONLY spacing
data text layout needs: Andika ships no kerning, its GPOS carries mark/mkmk
attachment only, and the accented letters in CHARSET are composite glyphs
that the pen decomposes into plain outlines), "ymin"/"ymax" (ink bounds).
Characters the font lacks are skipped with a note; charlib falls back to
the unaccented base letter at draw time.

Usage:
    python tools/build_font.py [path/to/Andika-Regular.ttf]

Deterministic output (sorted keys, fixed 1-decimal precision — TrueType
coords are integers, implied on-curve midpoints are exact .5) so re-runs
diff clean.
"""
import json
import os
import sys

DEFAULT_TTF = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                           "assets", "fonts", "Andika-Regular.ttf")
OUT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "..", "lib", "letters.json"))

# printable ASCII (space..~) + Latin-1 Supplement letters/punctuation
# (U+00A0..U+00FF minus the invisible soft hyphen) + Latin Extended-A
# (U+0100..U+017F: Œ œ plus the Polish/Czech/Hungarian/Turkish/... letters
# kids' names need — Łucja, Dvořák, Şule) + Ÿ and the typographic
# characters that show up in captions.
CHARSET = ("".join(chr(c) for c in range(0x20, 0x7F))
           + "".join(chr(c) for c in range(0xA0, 0x100) if c != 0xAD)
           + "".join(chr(c) for c in range(0x100, 0x180))
           + "\u2018\u2019\u201C\u201D"      # curly quotes
           + "\u2013\u2014\u2026\u2022")     # en/em dash, ellipsis, bullet


def _num(v):
    s = f"{round(float(v), 1):.1f}"
    s = s[:-2] if s.endswith(".0") else s
    return "0" if s == "-0" else s


def _pt(p):
    return _num(p[0]) + " " + _num(p[1])


def _pen_class():
    from fontTools.pens.basePen import BasePen

    class AbsPathPen(BasePen):
        """Absolute M/L/Q/C/Z only (see module docstring)."""

        def __init__(self, glyph_set):
            super().__init__(glyph_set)
            self.cmds = []

        def _moveTo(self, pt):
            self.cmds.append("M" + _pt(pt))

        def _lineTo(self, pt):
            self.cmds.append("L" + _pt(pt))

        def _qCurveToOne(self, p1, p2):
            self.cmds.append("Q" + _pt(p1) + " " + _pt(p2))

        def _curveToOne(self, p1, p2, p3):
            self.cmds.append("C" + _pt(p1) + " " + _pt(p2) + " " + _pt(p3))

        def _closePath(self):
            self.cmds.append("Z")

        def _endPath(self):
            pass

    return AbsPathPen


def main(ttf_path, out_path=OUT):
    from fontTools.ttLib import TTFont
    from fontTools.pens.boundsPen import BoundsPen

    AbsPathPen = _pen_class()
    font = TTFont(ttf_path)
    glyph_set = font.getGlyphSet()
    cmap = font.getBestCmap()
    upem = font["head"].unitsPerEm

    letters, missing = {}, []
    for ch in CHARSET:
        gname = cmap.get(ord(ch))
        if gname is None:
            missing.append(ch)
            continue
        pen = AbsPathPen(glyph_set)
        glyph_set[gname].draw(pen)
        bp = BoundsPen(glyph_set)
        glyph_set[gname].draw(bp)
        adv = glyph_set[gname].width
        letters[ch] = {
            "d": "".join(pen.cmds),
            "adv": int(adv) if float(adv).is_integer() else round(adv, 1),
            "ymin": round(bp.bounds[1], 1) if bp.bounds else 0,
            "ymax": round(bp.bounds[3], 1) if bp.bounds else round(upem * 0.7, 1),
        }
    if missing:
        print("  !! Andika has no glyph for "
              + " ".join(f"U+{ord(c):04X}" for c in missing) + " — skipped")
    out = {"font": "Andika", "license": "SIL-OFL-1.1",
           "upem": upem, "letters": letters}
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, sort_keys=True, separators=(",", ":"),
                  ensure_ascii=True)  # ASCII-safe on any locale
        fh.write("\n")
    print(f"wrote {out_path}: {len(letters)} glyphs, upem={upem}, "
          f"{os.path.getsize(out_path) // 1024}KB")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_TTF)
