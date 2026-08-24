#!/usr/bin/env python3
"""Build lib/letters.json from the bundled Andika font (SIL OFL — see
assets/fonts/OFL.txt and CREDITS.md).

Glyph outlines are converted to absolute SVG path data in FONT units
(y-UP); charlib.letter()/word() apply the size scale and y-flip at draw
time so the JSON stays resolution-independent. Only glyph OUTLINES are
stored (shape data, not the font program) — this keeps the repo clean of
any font-engine dependency at render time: pages need only Python.

Usage:
    python tools/build_font.py [path/to/Andika-Regular.ttf]

Deterministic output (sorted keys, fixed precision) so re-runs diff clean.
"""
import json
import os
import sys

DEFAULT_TTF = os.path.join(os.path.dirname(__file__), "..",
                           "assets", "fonts", "Andika-Regular.ttf")
OUT = os.path.join(os.path.dirname(__file__), "..", "lib", "letters.json")

CHARSET = ("ABCDEFGHIJKLMNOPQRSTUVWXYZ"
           "abcdefghijklmnopqrstuvwxyz"
           "0123456789"
           " !?'.,-&")


def main(ttf_path):
    from fontTools.ttLib import TTFont
    from fontTools.pens.svgPathPen import SVGPathPen
    from fontTools.pens.boundsPen import BoundsPen

    font = TTFont(ttf_path)
    glyph_set = font.getGlyphSet()
    cmap = font.getBestCmap()
    upem = font["head"].unitsPerEm

    letters = {}
    for ch in CHARSET:
        gname = cmap.get(ord(ch))
        if gname is None:
            print(f"  !! no glyph for {ch!r}, skipping")
            continue
        pen = SVGPathPen(glyph_set)
        glyph_set[gname].draw(pen)
        d = pen.getCommands()
        bp = BoundsPen(glyph_set)
        glyph_set[gname].draw(bp)
        letters[ch] = {
            "d": d,
            "adv": round(glyph_set[gname].width, 1),
            "ymin": round(bp.bounds[1], 1) if bp.bounds else 0,
            "ymax": round(bp.bounds[3], 1) if bp.bounds else upem * 0.7,
        }
    out = {"font": "Andika", "license": "SIL-OFL-1.1",
           "upem": upem, "letters": letters}
    with open(OUT, "w") as fh:
        json.dump(out, fh, sort_keys=True, separators=(",", ":"))
    print(f"wrote {OUT}: {len(letters)} glyphs, upem={upem}, "
          f"{os.path.getsize(OUT) // 1024}KB")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_TTF)
