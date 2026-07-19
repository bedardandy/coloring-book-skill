#!/usr/bin/env python3
"""Harper family story-mode coloring book — "Where Is Button?"

10 pages, ages 3-6, story arc: Button the teddy goes missing -> the family
searches the house -> Biscuit finds him -> celebrate -> bedtime.

Characters are PARAMETRIC trait vectors (charlib), never photo-likeness.
Partial rebuild:  python make_book.py 05      (substring filter on page name)
"""
import os, sys

SKILL_LIB = "../../lib"
sys.path.insert(0, SKILL_LIB)
from charlib import *          # primitives, motifs, figures, page/build/render_tiles, W,H,SW
import charlib

OUTDIR = os.path.dirname(os.path.abspath(__file__))
FLOOR = 908                    # floor line y for scenes
FEET = 905                     # figure feet y

# ---------------------------------------------------------------- cast traits
MAX    = {"name": "Max",  "age": 6, "hair": "buzz",      "glasses": False,
          "freckles": False, "height": 1.05, "outfit": "tee"}
LILY   = {"name": "Lily", "age": 4, "hair": "bob_bangs", "glasses": False,
          "freckles": False, "height": 0.82, "outfit": "dress"}
BISCUIT = {"coat": "plain", "floppy_ears": True, "collar": True}

MAX_S, LILY_S = MAX["height"], LILY["height"]

# ---------------------------------------------------------------- helpers
def rrect(x, y, w, h, r=8, sw=SW, fill="white"):
    return (f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
            f'rx="{r}" fill="{fill}" stroke="black" stroke-width="{sw}"/>')


def otext(x, y, s, size, sw=3, anchor="middle"):
    """Hollow (outline) block letters for tracing."""
    return (f'<text x="{x}" y="{y}" font-family="DejaVu Sans" font-size="{size}" '
            f'font-weight="bold" text-anchor="{anchor}" fill="white" stroke="black" '
            f'stroke-width="{sw}" letter-spacing="10">{s}</text>')


def wrap_words(text, maxchars=54):
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 <= maxchars:
            cur = (cur + " " + w).strip()
        else:
            lines.append(cur); cur = w
    if cur:
        lines.append(cur)
    return lines


def spage(title, body, num=None, caption=None, title_size=42):
    """Whole page: border, optional title, body, wrapped multi-line caption, page #."""
    parts = [f'<rect x="0" y="0" width="{W}" height="{H}" fill="white"/>',
             f'<rect x="28" y="28" width="{W-56}" height="{H-56}" rx="26" '
             f'fill="none" stroke="black" stroke-width="6"/>']
    if title:
        parts.append(TXT(W / 2, 102, title, title_size))
        parts.append(P(f"M {W/2-270} 124 Q {W/2} 142 {W/2+270} 124", 4))
    parts.append(body)
    if caption:
        lines = wrap_words(caption, 54)
        start = 1058 - (len(lines) - 1) * 28
        for i, ln in enumerate(lines):
            parts.append(TXT(W / 2, start + i * 28, ln, 22, weight="normal"))
    if num:
        parts.append(TXT(72, 1058, str(num), 20, weight="normal"))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
            f'viewBox="0 0 {W} {H}">' + "".join(parts) + "</svg>")


# ---------------------------------------------------------------- prop-characters
def teddy(cx, byy, s=1.0, sw=5):
    """Button the teddy bear, sitting. cx = center x, byy = bottom (feet) y."""
    out = []
    # legs
    out.append(E(cx - 20 * s, byy - 13 * s, 18 * s, 14 * s, sw, "white"))
    out.append(E(cx + 20 * s, byy - 13 * s, 18 * s, 14 * s, sw, "white"))
    out.append(DOT(cx - 30 * s, byy - 13 * s, 3 * s))   # paw pad
    out.append(DOT(cx + 30 * s, byy - 13 * s, 3 * s))
    # body
    out.append(E(cx, byy - 58 * s, 34 * s, 40 * s, sw, "white"))
    out.append(E(cx, byy - 52 * s, 18 * s, 22 * s, 3, "white"))  # tummy patch
    # arms
    out.append(E(cx - 40 * s, byy - 62 * s, 13 * s, 22 * s, sw, "white"))
    out.append(E(cx + 40 * s, byy - 62 * s, 13 * s, 22 * s, sw, "white"))
    # ears (behind head)
    out.append(C(cx - 26 * s, byy - 142 * s, 13 * s, sw, "white"))
    out.append(C(cx + 26 * s, byy - 142 * s, 13 * s, sw, "white"))
    # head (white, drawn after ears so it caps them)
    out.append(C(cx, byy - 118 * s, 32 * s, sw, "white"))
    # muzzle + face
    out.append(E(cx, byy - 108 * s, 15 * s, 11 * s, 3.5, "white"))
    out.append(P(f"M {cx-6*s} {byy-116*s} L {cx+6*s} {byy-116*s} "
                 f"L {cx} {byy-108*s} Z", 3.5, "black"))          # nose
    out.append(P(f"M {cx} {byy-108*s} Q {cx-5*s} {byy-101*s} {cx-9*s} {byy-103*s}", 3))  # mouth
    out.append(P(f"M {cx} {byy-108*s} Q {cx+5*s} {byy-101*s} {cx+9*s} {byy-103*s}", 3))
    out.append(DOT(cx - 12 * s, byy - 124 * s, 3.5 * s))         # eyes
    out.append(DOT(cx + 12 * s, byy - 124 * s, 3.5 * s))
    return "".join(out)


def dino(cx, cy, s=1.0, sw=4):
    """Side-view dinosaur facing right, origin at feet center. ~90*s tall, ~175*s
    wide: tapered curved tail, 4 legs, back plates on the spine, head with jaw."""
    out = []
    # tail first (body drawn after covers the joint)
    out.append(P(f"M {cx-32*s} {cy-56*s} Q {cx-88*s} {cy-58*s} {cx-94*s} {cy-14*s} "
                 f"Q {cx-64*s} {cy-34*s} {cx-28*s} {cy-22*s} Z", sw, "white"))
    # neck (head drawn after covers the top joint)
    out.append(P(f"M {cx+22*s} {cy-60*s} Q {cx+38*s} {cy-74*s} {cx+52*s} {cy-78*s} "
                 f"L {cx+56*s} {cy-64*s} Q {cx+42*s} {cy-52*s} {cx+30*s} {cy-44*s} Z", sw, "white"))
    # 4 legs with feet
    for lx in (-26, -10, 12, 28):
        out.append(P(f"M {cx+lx*s} {cy-16*s} L {cx+lx*s} {cy}", sw))
        out.append(P(f"M {cx+(lx-5)*s} {cy} L {cx+(lx+5)*s} {cy}", max(2.5, sw - 0.5)))
    # body
    out.append(E(cx, cy - 40 * s, 40 * s, 28 * s, sw, "white"))
    # back plates along the spine
    for px in (-26, -8, 10):
        py = -40 - 28 * math.sqrt(max(0.0, 1 - (px / 40) ** 2))
        out.append(P(f"M {cx+(px-8)*s} {cy+(py+3)*s} L {cx+px*s} {cy+(py-15)*s} "
                     f"L {cx+(px+8)*s} {cy+(py+3)*s}", max(2.5, sw - 0.5)))
    # head with jaw line + eye
    out.append(E(cx + 62 * s, cy - 74 * s, 17 * s, 13 * s, sw, "white"))
    out.append(P(f"M {cx+58*s} {cy-70*s} L {cx+77*s} {cy-70*s}", 3))
    out.append(DOT(cx + 60 * s, cy - 79 * s, 2.6))
    return "".join(out)


def soccer_ball(cx, cy, r, sw=4):
    """Soccer ball: circle + central pentagon + short seam lines to the rim."""
    out = [C(cx, cy, r, sw, "white")]
    pts = []
    for i in range(5):
        a = math.pi / 2 + i * 2 * math.pi / 5
        pts.append((cx + 0.40 * r * math.cos(a), cy - 0.40 * r * math.sin(a)))
    out.append('<polygon points="' + " ".join(f"{x:.1f},{y:.1f}" for x, y in pts) +
               '" fill="black" stroke="black" stroke-width="2"/>')
    for x, y in pts:
        dx, dy = x - cx, y - cy
        n = math.hypot(dx, dy) or 1
        out.append(LINE(x, y, cx + dx / n * 0.85 * r, cy + dy / n * 0.85 * r,
                        max(2.5, sw - 1.5)))
    return "".join(out)


def wall_clock(cx, cy, r=40):
    """Wall clock: rim, 4 hour ticks, two hands, center dot."""
    out = [C(cx, cy, r, 5, "white")]
    for i in range(4):
        a = i * math.pi / 2
        out.append(LINE(cx + (r - 11) * math.cos(a), cy + (r - 11) * math.sin(a),
                        cx + (r - 4) * math.cos(a), cy + (r - 4) * math.sin(a), 3.5))
    out.append(LINE(cx, cy, cx, cy - r * 0.58, 4))          # minute hand
    out.append(LINE(cx, cy, cx + r * 0.40, cy + r * 0.12, 4))  # hour hand
    out.append(DOT(cx, cy, 4))
    return "".join(out)


def dotline(x1, y1, x2, y2, sw=4):
    """Dotted guide line (round dots)."""
    return (f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="black" stroke-width="{sw}" stroke-linecap="round" '
            f'stroke-dasharray="0.1 16"/>')


def hold_teddy(x, feet, ks):
    """Button held at CHEST by a kid drawn with kid_stand(..., pose='hold') at
    (x, feet, scale=ks). Bear top stays fully below the chin (face and bangs
    visible); the hold-pose hand circles are redrawn OVER the bear at their
    original spots so the hands visibly grasp the bear's arms (no doubling)."""
    ts = 0.85 * ks
    out = teddy(x, feet - 20 * ks, ts)
    for sx in (-1, 1):
        out += C(x + sx * 47 * ks, feet - 96 * ks, 8 * ks, 4, "white")
    return out


def kid_reach(t, outfit=None):
    """Kid reaching BOTH arms to the RIGHT at chest height (searching / lifting
    cushions / peeking behind furniture). Origin at feet center like kid_stand;
    mirror with GM(x, y, kid_reach(t), s) to reach left. Hands overlap arm ends
    and stay well clear of the head radius."""
    out = []
    outfit = outfit or t.get("outfit", "tee")
    head_y = -196 if outfit == "dress" else -188
    if outfit == "dress":
        out.append(P("M -18 -160 L 18 -160 L 30 -108 L 62 -18 "
                     "Q 48 -28 38 -14 Q 28 -26 16 -12 Q 4 -26 -8 -12 Q -20 -26 -30 -14 Q -42 -28 -55 -16 "
                     "L -28 -108 Z", 5, "white"))
        out.append(P("M -26 -100 L 26 -100", 4))
        out.append(DOT(-20, -58, 3) + DOT(4, -42, 3) + DOT(24, -62, 3) + DOT(0, -78, 3))
        out.append(P("M -18 -14 L -18 0 Q -18 6 -10 6 L -6 6", 4.5))
        out.append(P("M 18 -14 L 18 0 Q 18 6 26 6 L 30 6", 4.5))
        sh = (-20, -150), (20, -150)
    else:
        out.append(P("M -12 -70 L -12 -8 Q -12 0 -4 0 L 4 0", 5))
        out.append(P("M 14 -70 L 14 -8 Q 14 0 22 0 L 30 0", 5))
        out.append(P("M -18 -152 L 18 -152 L 26 -70 L -26 -70 Z", 5, "white"))
        out.append(P("M -22 -96 L 22 -96", 4))
        sh = (-18, -142), (18, -142)
    (lsx, lsy), (rsx, rsy) = sh
    out.append(P(f"M {lsx} {lsy} Q 10 -120 52 -108", 5))
    out.append(C(58, -106, 8, 4, "white"))
    out.append(P(f"M {rsx} {rsy} Q 40 -132 66 -124", 5))
    out.append(C(72, -122, 8, 4, "white"))
    out.append(face_traits(0, head_y, 37, t))
    return "".join(out)


# ---------------------------------------------------------------- furniture
def floor_line(y=FLOOR):
    return LINE(46, y, 804, y, 5)


def bed(x, floor=FLOOR, w=240, foot=True):
    """Side-view bed, left end = headboard. x = left of mattress."""
    leg_h, mat_h = 24, 34
    mat_top = floor - leg_h - mat_h
    out = [LINE(x + 18, mat_top + mat_h, x + 18, floor, 5),
           LINE(x + w - 18, mat_top + mat_h, x + w - 18, floor, 5),
           rrect(x, mat_top, w, mat_h, 10),
           rrect(x - 26, mat_top - 70, 26, 70 + mat_h, 10)]          # headboard
    if foot:
        out.append(rrect(x + w, mat_top - 30, 22, 30 + mat_h, 10))   # footboard
    out.append(rrect(x + 10, mat_top - 20, 74, 26, 12))              # pillow
    out.append(LINE(x + 120, mat_top, x + w - 8, mat_top, 4))        # blanket edge
    out.append(P(f"M {x+120} {mat_top} L {x+120} {mat_top+mat_h}", 4))
    return "".join(out)


def toybox(x, floor=FLOOR, w=124, h=92):
    y = floor - h
    return (rrect(x, y, w, h, 10) + LINE(x, y + 24, x + w, y + 24, 4) +
            star(x + w / 2, y + 58, 17, 4, "white"))


def window(x, y, w=150, h=120):
    # plain grid pane + curtain rod (no valance — the old valance read as a gift bow)
    return (rrect(x, y, w, h, 6, 5, "white") +
            LINE(x + w / 2, y, x + w / 2, y + h, 4) +
            LINE(x, y + h / 2, x + w, y + h / 2, 4) +
            LINE(x - 14, y - 9, x + w + 14, y - 9, 5) +
            C(x - 14, y - 9, 4, 3, "white") + C(x + w + 14, y - 9, 4, 3, "white"))


def wall_picture(x, y, w=100, h=80, motif="heart"):
    """Framed wall picture — a mid-band filler that is clearly wall-mounted."""
    cx, cy = x + w / 2, y + h / 2
    out = [P(f"M {cx-16} {y} L {cx} {y-13} L {cx+16} {y}", 3),           # hanger
           rrect(x, y, w, h, 6, 5, "white"),
           rrect(x + 9, y + 9, w - 18, h - 18, 3, 3, "white")]          # inner mat
    if motif == "heart":
        out.append(heart(cx, cy - 2, 15, 4))
    elif motif == "star":
        out.append(star(cx, cy, 17, 4, "white"))
    elif motif == "butterfly":
        out.append(butterfly(cx, cy, 1.4))
    elif motif == "sun":
        out.append(sun(cx, cy - 2, 16, 4))
    return "".join(out)


def bookshelf(x, floor=FLOOR, w=112, h=290):
    """Tall shelf unit — fills the vertical middle band on room pages."""
    y = floor - h
    out = [rrect(x, y, w, h, 6)]
    for sy in (y + 72, y + 144, y + 216):
        out.append(LINE(x, sy, x + w, sy, 4))
    out += [rrect(x + 12, y + 18, 13, 52, 2), rrect(x + 30, y + 18, 13, 52, 2),
            rrect(x + 48, y + 24, 13, 46, 2), soccer_ball(x + 86, y + 50, 15)]
    out += [rrect(x + 14, y + 90, 15, 52, 2), rrect(x + 33, y + 94, 15, 48, 2),
            star(x + 86, y + 120, 15, 3, "white")]
    out += [heart(x + 32, y + 192, 13, 3), butterfly(x + 84, y + 190, 1.2)]
    return "".join(out)


def rug(cx, cy, rx=160, ry=26):
    return E(cx, cy, rx, ry, 4, "white") + E(cx, cy, rx * 0.66, ry * 0.6, 3, "white")


def couch(x, floor=FLOOR, w=260):
    seat_h, back_h = 58, 78
    y = floor - seat_h
    out = [rrect(x, y - back_h, w, back_h, 12),                       # back
           rrect(x, y, w, seat_h, 10),                               # seat
           rrect(x - 16, y - 34, 30, seat_h + 34, 10),               # left arm
           rrect(x + w - 14, y - 34, 30, seat_h + 34, 10),           # right arm
           LINE(x + w / 3, y - back_h + 8, x + w / 3, y, 3),
           LINE(x + 2 * w / 3, y - back_h + 8, x + 2 * w / 3, y, 3)]
    return "".join(out)


def armchair(x, floor=FLOOR, w=120):
    seat_h, back_h = 58, 78
    y = floor - seat_h
    out = [rrect(x, y - back_h, w, back_h, 12),
           rrect(x, y, w, seat_h, 10),
           rrect(x - 14, y - 32, 26, seat_h + 32, 10),
           rrect(x + w - 12, y - 32, 26, seat_h + 32, 10)]
    return "".join(out)


def floor_lamp(x, floor=FLOOR, h=250):
    top = floor - h
    return (LINE(x, floor, x, top + 28, 4) + P(f"M {x-20} {floor} L {x+20} {floor}", 5) +
            P(f"M {x-34} {top+28} L {x-22} {top} L {x+22} {top} L {x+34} {top+28} Z", 4, "white"))


def toy_shelf(x, y, w=150):
    """Wall shelf with toys, anchored by two wall brackets underneath."""
    out = [LINE(x, y, x + w, y, 5),
           P(f"M {x+24} {y+2} L {x+24} {y+20} L {x+42} {y+2} Z", 3.5, "white"),
           P(f"M {x+w-24} {y+2} L {x+w-24} {y+20} L {x+w-42} {y+2} Z", 3.5, "white")]
    out.append(soccer_ball(x + 26, y - 16, 15))
    out.append(C(x + 74, y - 16, 15, 4, "white"))
    out.append(star(x + 122, y - 16, 15, 4, "white"))
    return "".join(out)


def butterfly_wall(cx_list):
    """Row of butterflies (Lily's wall). cx_list = list of (x,y)."""
    return "".join(butterfly(x, y, 1.4) for x, y in cx_list)


# ---------------------------------------------------------------- pages
def cover():
    b = []
    b.append(TXT(W / 2, 168, "A Harper Family Story", 30, weight="normal"))
    # scattered motifs (balanced L/R), kept in the sky band above the cast
    b.append(butterfly(135, 225, 1.7) + butterfly(710, 300, 1.7))
    b.append(star(230, 210, 20, 4, "white") + star(640, 200, 20, 4, "white"))
    b.append(heart(410, 210, 16, 4) + sparkle(320, 300, 11) + sparkle(560, 280, 11))
    b.append(dino(155, 375, 1.0))
    b.append(sparkle(730, 430, 11) + sparkle(120, 470, 11))
    # mid-band fillers so the page doesn't read empty between motifs and cast
    b.append(butterfly(415, 452, 1.5) + heart(190, 500, 14, 4) + heart(660, 500, 14, 4))
    b.append(sparkle(300, 470, 11) + sparkle(560, 486, 11) + star(430, 560, 15, 4, "white"))
    # cast on the floor, with the Harper house behind them (it's a house story)
    b.append(floor_line())
    b.append(house(390, FEET + 2, w=200))
    b.append(matted(G(232, FEET, kid_stand(MAX, pose="wave"), MAX_S)))
    b.append(matted(G(462, FEET, kid_stand(LILY, pose="hold"), LILY_S) +
                    hold_teddy(462, FEET, LILY_S)))      # Button at chest, below chin
    b.append(matted(G(650, FEET, dog(BISCUIT), 1.02)))
    b.append(matted(soccer_ball(300, 892, 22)))          # soccer ball by Max
    b.append(bone(748, 884, 0.9))                        # bone by Biscuit
    # name banner
    b.append(rrect(205, 940, 440, 46, 22, 5, "white"))
    b.append(TXT(W / 2, 972, "Max • Lily • Biscuit • Button", 24, weight="normal"))
    return spage("Where Is Button?", "".join(b), title_size=52)


def names():
    b = []
    b.append(TXT(W / 2, 172, "Trace each letter, then color your motif!", 24, weight="normal"))
    # MAX row
    b.append(otext(W / 2, 400, "MAX", 175, 4))
    b.append(dino(135, 480, 0.9))
    b.append(soccer_ball(700, 430, 26))
    # LILY row
    b.append(otext(W / 2, 700, "LILY", 155, 4))
    b.append(butterfly(150, 760, 2.4))
    b.append(butterfly(700, 760, 2.4))
    b.append(P("M 120 500 L 730 500", 3))                # faint divider
    return spage("Trace Your Names!", "".join(b), num=2,
                 caption="Trace the letters. M-A-X spells Max. L-I-L-Y spells Lily. "
                         "Color a dinosaur for Max and a butterfly for Lily!")


def intro():
    b = []
    b.append(floor_line())
    b.append(window(470, 300, 150, 120))
    b.append(wall_picture(140, 320, 104, 82, "heart"))              # Lily's wall
    b.append(butterfly(272, 288, 1.3) + butterfly(150, 460, 1.3))  # Lily's wall butterflies
    b.append(bookshelf(668, FLOOR))                                # fills right mid-band
    b.append(rug(360, 900, 180, 26))
    b.append(bed(70, FLOOR, w=200))
    b.append(teddy(148, FLOOR - 58, 0.58))                # Button on the bed
    # cast
    b.append(matted(G(330, FEET, kid_stand(MAX, pose="wave"), MAX_S)))
    b.append(matted(G(470, FEET, kid_stand(LILY, pose="down"), LILY_S)))
    b.append(matted(G(570, FEET, dog(BISCUIT), 0.92)))
    # name labels under the two kids
    b.append(TXT(330, 952, "Max", 24, weight="normal"))
    b.append(TXT(470, 952, "Lily", 24, weight="normal"))
    return spage("Meet the Harpers", "".join(b), num=3,
                 caption="This is Max. This is Lily. This is Biscuit the dog. Max and "
                         "Lily love their teddy bear Button, who goes everywhere with them.")


def problem():
    b = []
    b.append(floor_line())
    b.append(window(70, 300, 140, 116))
    b.append(wall_picture(300, 316, 104, 82, "star"))
    b.append(bed(470, FLOOR, w=270))                     # empty bed, no teddy
    # gentle question raised over the empty bed, dotted guide down to it
    b.append(TXT(575, 470, "?", 76))
    b.append(sparkle(520, 430, 12) + sparkle(640, 440, 12))
    b.append(dotline(585, 505, 618, 838))
    # mid-band fillers between wall decor and the scene
    b.append(heart(150, 570, 13, 4) + butterfly(690, 570, 1.3))
    b.append(rug(300, 902, 150, 24))
    # Lily points at the empty bed, Max beside, Biscuit clear to the left
    b.append(matted(G(255, FEET, kid_stand(LILY, pose="wave"), LILY_S)))
    b.append(matted(G(370, FEET, kid_stand(MAX, pose="down"), MAX_S)))
    b.append(matted(G(118, FEET, dog(BISCUIT), 0.85)))
    return spage("Where Is Button?", "".join(b), num=4,
                 caption="Oh no! Button is not on the bed. Where is Button? Max and Lily "
                         "and Biscuit look everywhere. Come and help Max and Lily search!")


def search_bedroom():
    b = []
    b.append(floor_line())
    b.append(bed(66, FLOOR, w=196))                      # bed spans headboard 40 .. footboard ~284
    b.append(sparkle(150, 895, 8))                       # nothing-under-bed sparkle
    b.append(P("M 200 884 L 236 884 L 218 906 Z", 4, "white"))  # blanket corner peeking down
    b.append(toybox(680, FLOOR, w=110))
    # wall decor across the middle band (window top-right, framed picture top-left)
    b.append(window(560, 300, 150, 120))
    b.append(wall_picture(120, 316, 100, 80, "butterfly"))
    b.append(butterfly(300, 300, 1.3) + butterfly(390, 360, 1.3))
    # Max peers down beside the bed, Biscuit sniffs mid-room, Lily at the toy box
    b.append(G(346, FEET, kid_stand(MAX, pose="down"), MAX_S))
    b.append(G(486, FEET, dog(BISCUIT), 0.9))
    b.append(G(622, FEET, kid_stand(LILY, pose="hold"), LILY_S))
    b.append(car_side(715, 950, w=85))                   # toy car spilled from the toy box
    return spage("Look in the Bedroom", "".join(b), num=5,
                 caption="Max looks under the bed. Lily peeks in the toy box. Biscuit "
                         "sniffs the soft blanket. Button is not here! Max and Lily keep looking.")


def search_living():
    b = []
    b.append(floor_line())
    b.append(window(80, 300, 150, 120))
    b.append(wall_clock(480, 352, 40))                   # wall clock above the couch
    b.append(rug(300, 902, 150, 24))                     # rug FIRST so furniture covers it
    b.append(armchair(120, FLOOR, w=120))
    b.append(couch(360, FLOOR, w=250))
    b.append(floor_lamp(720, FLOOR, h=300))
    # Lily reaches LEFT behind the big chair; Max reaches onto the couch cushions
    b.append(matted(GM(290, FEET, kid_reach(LILY), LILY_S)))
    b.append(matted(G(470, FEET, kid_reach(MAX), MAX_S)))
    b.append(matted(G(640, FEET, dog(BISCUIT), 0.85)))
    return spage("Look in the Living Room", "".join(b), num=6,
                 caption="Now Max and Lily look in the living room. Lily checks behind the "
                         "big chair. Max lifts the couch cushions. Where is Button hiding?")


def find_activity():
    b = []
    b.append(floor_line())
    # a hallway wall lined with butterflies to find & color
    bfly = [(150, 250), (330, 210), (520, 250), (680, 210), (250, 400)]
    b.append(butterfly_wall(bfly))
    b.append(toy_shelf(430, 470, 160))
    # hallway door on the right (with knob) — anchors the scene as a hallway
    b.append(P("M 664 908 L 664 424 Q 664 410 678 410 L 778 410 Q 792 410 792 424 L 792 908", 5))
    b.append(C(680, 660, 7, 4, "white"))                 # doorknob
    # cast: Biscuit sniffs toward the door, kids follow
    b.append(G(220, FEET, kid_stand(LILY, pose="wave"), LILY_S))
    b.append(G(360, FEET, kid_stand(MAX, pose="hold"), MAX_S))
    b.append(G(540, FEET, dog(BISCUIT), 1.0))
    # scent-trail sniff arcs between Biscuit's nose and the door
    b.append(P("M 634 798 Q 641 806 634 814", 3))
    b.append(P("M 645 794 Q 654 804 645 816", 3))
    b.append(P("M 656 790 Q 667 803 656 819", 3))
    b.append(TXT(W / 2, 300, "Find 5 butterflies!", 26, weight="normal"))
    return spage("Follow Biscuit!", "".join(b), num=7,
                 caption="Max and Lily and Biscuit look everywhere! Biscuit points his nose "
                         "down the hallway. Can you find five butterflies on Lily's wall to color?")


def solve():
    b = []
    b.append(floor_line())
    b.append(window(120, 300, 140, 116))
    b.append(wall_picture(360, 316, 104, 82, "heart"))
    b.append(bed(70, FLOOR, w=220))
    b.append(sparkle(150, 895, 8))                       # the now-empty spot under the bed
    b.append(rug(370, 902, 90, 18))
    # celebration sparkles/hearts balanced L/R across the middle band
    b.append(sparkle(560, 470, 12) + sparkle(650, 500, 12) + heart(610, 545, 14, 4))
    b.append(sparkle(250, 520, 12) + heart(300, 470, 14, 4))
    # Max reaches toward the bed (he pulled Button out); Lily hugs Button tight
    b.append(matted(GM(375, FEET, kid_reach(MAX), MAX_S)))
    b.append(matted(G(515, FEET, kid_stand(LILY, pose="hold"), LILY_S) +
                    hold_teddy(515, FEET, LILY_S)))      # Button hugged at Lily's chest
    b.append(matted(G(660, FEET, dog(BISCUIT), 0.95)))
    return spage("Biscuit Found Him!", "".join(b), num=8,
                 caption="Biscuit found him! Button is under Max's bed. Max reaches down and "
                         "pulls Button out. Lily hugs Button tight. Good dog, Biscuit!")


def celebrate():
    b = []
    b.append(floor_line())
    # party sky: hearts, stars, sparkles balanced
    b.append(heart(150, 240, 18, 4) + heart(700, 240, 18, 4))
    b.append(star(280, 210, 18, 4, "white") + star(560, 210, 18, 4, "white"))
    b.append(sparkle(430, 200, 12) + sparkle(120, 340, 11) + sparkle(730, 340, 11))
    b.append(butterfly(430, 300, 1.6))
    # bridge the mid-band between the party sky and the cast
    b.append(heart(250, 430, 15, 4) + heart(620, 430, 15, 4))
    b.append(sparkle(150, 470, 11) + sparkle(720, 470, 11) + star(430, 440, 15, 4, "white"))
    # full cast celebrating: Max arms up, Lily hugs Button at her chest
    b.append(G(250, FEET, kid_stand(MAX, pose="up"), MAX_S))
    b.append(G(470, FEET, kid_stand(LILY, pose="hold"), LILY_S))
    b.append(hold_teddy(470, FEET, LILY_S))              # Button below Lily's chin, grasped
    b.append(G(640, FEET, dog(BISCUIT), 1.0))
    return spage("Hooray for Button!", "".join(b), num=9,
                 caption="Max and Lily and Biscuit found Button! Everyone dances in a happy "
                         "circle. Now Max and Lily snuggle into bed with Button and Biscuit.")


def back_cover():
    b = []
    b.append(TXT(W / 2, 300, "The End", 64))
    b.append(P(f"M {W/2-150} 330 Q {W/2} 350 {W/2+150} 330", 4))
    # cozy sleeping scene: moon, stars, Button + Biscuit resting on a rug
    b.append(C(660, 210, 42, 5, "white") + C(678, 200, 34, 5, "white"))  # crescent moon
    b.append(star(165, 200, 18, 4, "white") + star(300, 168, 14, 4, "white") +
             star(560, 190, 14, 4, "white"))
    b.append(rug(W / 2, 720, 220, 34))
    b.append(teddy(370, 715, 0.7))
    b.append(matted(G(520, 720, dog(BISCUIT), 0.8)))
    b.append(sparkle(300, 616, 11) + sparkle(600, 600, 11))
    b.append(TXT(W / 2, 830, "Goodnight, Max. Goodnight, Lily.", 26, weight="normal"))
    b.append(TXT(W / 2, 866, "Goodnight, Biscuit and Button.", 26, weight="normal"))
    b.append(heart(W / 2, 928, 18, 4))
    b.append(TXT(W / 2, 985, "Made with love for Max and Lily", 26, weight="normal"))
    return spage("", "".join(b))


# ---------------------------------------------------------------- build
BUILDERS = [
    ("01-cover",          cover),
    ("02-names",          names),
    ("03-intro",          intro),
    ("04-problem",        problem),
    ("05-search-bedroom", search_bedroom),
    ("06-search-living",  search_living),
    ("07-find-activity",  find_activity),
    ("08-solve",          solve),
    ("09-celebrate",      celebrate),
    ("10-back-cover",     back_cover),
]

if __name__ == "__main__":
    build(BUILDERS, OUTDIR, only=sys.argv[1:] or None,
          pdf_name="Harper-Coloring-Book.pdf")
