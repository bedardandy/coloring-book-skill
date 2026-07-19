"""charlib — parametric line-art library for kids' coloring books.

Battle-tested geometry extracted from real production coloring books (2026-07).
All output is bold black-outline SVG on white, ages ~3-7.

Coordinate system: letter page 850x1100 (100dpi). Figures are drawn in local
coords with origin at the FEET CENTER, ~250 units tall at scale 1.0; place
with G(x, y_feet, inner, scale).

CRITICAL GOTCHAS (learned the hard way):
- Heads (white fill) are drawn LAST in figure helpers — raised hands/props
  must sit OUTSIDE the head+hair radius (~1.3*r) or they get covered.
- Never mirror with a negative uniform scale in G() (turns art upside-down);
  use GM() which flips x only.
- Keep raised-hand circles OVERLAPPING their arm-line ends (no gaps).
- Web/rope/leash lines must END AT a hand circle, offset well clear of the head.
"""
import math

W, H = 850, 1100
SW = 5


# ---------------------------------------------------------------- primitives
def P(d, sw=SW, fill="none"):
    return (f'<path d="{d}" fill="{fill}" stroke="black" stroke-width="{sw}" '
            f'stroke-linecap="round" stroke-linejoin="round"/>')


def C(cx, cy, r, sw=SW, fill="none"):
    return f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{fill}" stroke="black" stroke-width="{sw}"/>'


def DOT(cx, cy, r=3.5):
    return f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="black"/>'


def E(cx, cy, rx, ry, sw=SW, fill="none"):
    return f'<ellipse cx="{cx:.1f}" cy="{cy:.1f}" rx="{rx:.1f}" ry="{ry:.1f}" fill="{fill}" stroke="black" stroke-width="{sw}"/>'


def LINE(x1, y1, x2, y2, sw=SW):
    return f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="black" stroke-width="{sw}" stroke-linecap="round"/>'


def TXT(x, y, s, size=40, anchor="middle", weight="bold"):
    return (f'<text x="{x}" y="{y}" font-family="DejaVu Sans" font-size="{size}" '
            f'font-weight="{weight}" text-anchor="{anchor}" fill="black">{s}</text>')


def G(x, y, inner, scale=1.0, rot=0):
    return f'<g transform="translate({x},{y}) rotate({rot}) scale({scale})">{inner}</g>'


def GM(x, y, inner, scale=1.0):
    """Mirror horizontally (flip left-right) WITHOUT turning upside-down."""
    return f'<g transform="translate({x},{y}) scale(-{scale},{scale})">{inner}</g>'


# ---------------------------------------------------------------- motifs
def star(cx, cy, r, sw=SW, fill="none"):
    pts = []
    for i in range(10):
        rr = r if i % 2 == 0 else r * 0.45
        a = math.pi / 2 + i * math.pi / 5
        pts.append(f"{cx + rr * math.cos(a):.1f},{cy - rr * math.sin(a):.1f}")
    return f'<polygon points="{" ".join(pts)}" fill="{fill}" stroke="black" stroke-width="{sw}" stroke-linejoin="round"/>'


def sparkle(cx, cy, r=10, sw=3.5):
    return LINE(cx - r, cy, cx + r, cy, sw) + LINE(cx, cy - r, cx, cy + r, sw)


def heart(cx, cy, s, sw=SW, fill="none"):
    d = (f"M {cx} {cy + s * 0.9} C {cx - s * 1.4} {cy - s * 0.1}, {cx - s * 0.7} {cy - s}, {cx} {cy - s * 0.35} "
         f"C {cx + s * 0.7} {cy - s}, {cx + s * 1.4} {cy - s * 0.1}, {cx} {cy + s * 0.9} Z")
    return P(d, sw, fill)


def cloud(cx, cy, s, sw=SW):
    d = (f"M {cx - s * 1.5} {cy} Q {cx - s * 1.6} {cy - s * 0.8} {cx - s * 0.8} {cy - s * 0.8} "
         f"Q {cx - s * 0.6} {cy - s * 1.5} {cx + s * 0.1} {cy - s * 1.1} "
         f"Q {cx + s * 0.7} {cy - s * 1.6} {cx + s * 1.1} {cy - s * 0.8} "
         f"Q {cx + s * 1.7} {cy - s * 0.8} {cx + s * 1.5} {cy} Z")
    return P(d, sw, "white")


def sun(cx, cy, r=42, sw=SW):
    s = C(cx, cy, r, sw, "white")
    for i in range(8):
        a = i * math.pi / 4
        s += LINE(cx + (r + 12) * math.cos(a), cy + (r + 12) * math.sin(a),
                  cx + (r + 32) * math.cos(a), cy + (r + 32) * math.sin(a), sw)
    return s


def strawberry(cx, cy, s, sw=4):
    body = (f"M {cx - s * 0.75} {cy - s * 0.35} Q {cx} {cy - s * 0.75} {cx + s * 0.75} {cy - s * 0.35} "
            f"Q {cx + s * 0.8} {cy + s * 0.45} {cx} {cy + s} Q {cx - s * 0.8} {cy + s * 0.45} {cx - s * 0.75} {cy - s * 0.35} Z")
    leaves = (f"M {cx - s * 0.55} {cy - s * 0.42} L {cx - s * 0.28} {cy - s * 0.62} L {cx - s * 0.12} {cy - s * 0.42} "
              f"L {cx} {cy - s * 0.68} L {cx + s * 0.12} {cy - s * 0.42} L {cx + s * 0.28} {cy - s * 0.62} L {cx + s * 0.55} {cy - s * 0.42}")
    seeds = "".join(DOT(cx + dx * s, cy + dy * s, 2.2) for dx, dy in
                    [(-0.35, 0), (0, -0.1), (0.35, 0), (-0.18, 0.35), (0.18, 0.35), (0, 0.65)])
    return P(body, sw, "white") + P(leaves, sw) + seeds + LINE(cx, cy - s * 0.66, cx, cy - s * 0.95, sw)


def crown(cx, cy, w, h, sw=4):
    d = (f"M {cx - w / 2} {cy} L {cx - w / 2} {cy - h * 0.55} L {cx - w * 0.25} {cy - h * 0.2} "
         f"L {cx} {cy - h} L {cx + w * 0.25} {cy - h * 0.2} L {cx + w / 2} {cy - h * 0.55} L {cx + w / 2} {cy} Z")
    g = h * 0.16
    gem = P(f"M {cx - g} {cy - h * 0.32} L {cx} {cy - h * 0.32 - g} L {cx + g} {cy - h * 0.32} L {cx} {cy - h * 0.32 + g} Z", 3, "white")
    return P(d, sw, "white") + gem + DOT(cx, cy - h - 5, 4)


def wand(x, y, angle, ln=70, sw=4, r=14):
    a = math.radians(angle)
    x2, y2 = x + ln * math.cos(a), y - ln * math.sin(a)
    return LINE(x, y, x2, y2, sw) + star(x2, y2 - 2, r, sw, "white") + sparkle(x2 + r + 14, y2 - r, 8)


def flower(cx, cy, s=1.0, sw=3.5):
    out = [C(cx, cy, 5 * s, sw, "white")]
    for dx, dy in [(0, -9), (8.5, -3), (5.5, 8), (-5.5, 8), (-8.5, -3)]:
        out.append(E(cx + dx * s, cy + dy * s, 5 * s, 4.5 * s, sw, "white"))
    return "".join(out)


def music_note(cx, cy, s=1.0, sw=4):
    return (E(cx, cy, 7 * s, 5 * s, sw, "black") + LINE(cx + 7 * s, cy, cx + 7 * s, cy - 30 * s, sw) +
            P(f"M {cx + 7 * s} {cy - 30 * s} Q {cx + 20 * s} {cy - 26 * s} {cx + 16 * s} {cy - 14 * s}", sw))


def butterfly(cx, cy, s=1.0, sw=4):
    b = E(cx, cy, 3 * s, 12 * s, sw, "black")
    w = (P(f"M {cx - 2 * s} {cy - 4 * s} Q {cx - 26 * s} {cy - 22 * s} {cx - 20 * s} {cy - 2 * s} Q {cx - 16 * s} {cy + 4 * s} {cx - 2 * s} {cy}", sw, "white") +
         P(f"M {cx + 2 * s} {cy - 4 * s} Q {cx + 26 * s} {cy - 22 * s} {cx + 20 * s} {cy - 2 * s} Q {cx + 16 * s} {cy + 4 * s} {cx + 2 * s} {cy}", sw, "white") +
         P(f"M {cx - 2 * s} {cy + 2 * s} Q {cx - 20 * s} {cy + 18 * s} {cx - 8 * s} {cy + 8 * s}", sw) +
         P(f"M {cx + 2 * s} {cy + 2 * s} Q {cx + 20 * s} {cy + 18 * s} {cx + 8 * s} {cy + 8 * s}", sw))
    ant = P(f"M {cx - 2 * s} {cy - 11 * s} Q {cx - 8 * s} {cy - 20 * s} {cx - 10 * s} {cy - 18 * s}", 3) + \
          P(f"M {cx + 2 * s} {cy - 11 * s} Q {cx + 8 * s} {cy - 20 * s} {cx + 10 * s} {cy - 18 * s}", 3)
    return w + b + ant


def balloon(cx, cy, s=1.0, sw=4):
    return (E(cx, cy, 22 * s, 28 * s, sw, "white") +
            P(f"M {cx - 4 * s} {cy + 27 * s} L {cx + 4 * s} {cy + 27 * s} L {cx} {cy + 33 * s} Z", 3, "white") +
            P(f"M {cx} {cy + 33 * s} Q {cx + 8 * s} {cy + 55 * s} {cx - 4 * s} {cy + 75 * s}", 3))


def ball(cx, cy, r, sw=4):
    return (C(cx, cy, r, sw, "white") +
            P(f"M {cx - r} {cy} Q {cx} {cy - r * 0.55} {cx + r} {cy}", 3) +
            P(f"M {cx - r} {cy} Q {cx} {cy + r * 0.55} {cx + r} {cy}", 3))


def bone(cx, cy, s=1.0, sw=4):
    return (P(f"M {cx - 18 * s} {cy - 5 * s} L {cx + 18 * s} {cy - 5 * s} "
              f"Q {cx + 30 * s} {cy - 14 * s} {cx + 34 * s} {cy - 4 * s} Q {cx + 44 * s} {cy - 6 * s} {cx + 40 * s} {cy + 4 * s} "
              f"Q {cx + 30 * s} {cy + 12 * s} {cx + 18 * s} {cy + 5 * s} L {cx - 18 * s} {cy + 5 * s} "
              f"Q {cx - 30 * s} {cy + 12 * s} {cx - 40 * s} {cy + 4 * s} Q {cx - 44 * s} {cy - 6 * s} {cx - 34 * s} {cy - 4 * s} "
              f"Q {cx - 30 * s} {cy - 14 * s} {cx - 18 * s} {cy - 5 * s} Z", sw, "white"))


def stones(coords, sw=3):
    return "".join(P(f"M {x - 12} {y} Q {x} {y - 9} {x + 12} {y}", sw) for x, y in coords)


def grass_tuft(gx, gy, sw=3):
    return P(f"M {gx} {gy} Q {gx+4} {gy-16} {gx+8} {gy-2} M {gx+10} {gy-1} Q {gx+14} {gy-14} {gx+18} {gy}", sw)


# ---------------------------------------------------------------- faces
HAIR_STYLES = ("bob_bangs", "bob", "tousled", "long_wavy", "pigtails", "curly", "buzz")


def face(cx, cy, r=38, hair="tousled", glasses=False, freckles=False,
         headband=False, extras=True, brows=False, mouth="smile", cheeks=True,
         beard=False):
    """Head with parametric hair/glasses/freckles. Draw AFTER body & arms.
    Hair+face occupy roughly a 1.3*r radius — keep props outside it.
    Friendliness defaults (anti-eerie): brows OFF (brows close to dot eyes read
    as scheming), smile is a narrow deep U, mouth="open" gives an unambiguous
    happy D-mouth, cheeks adds small colorable blush circles."""
    s = C(cx, cy, r, SW, "white")
    ey, ex = cy + r * 0.08, r * 0.38
    hairsvg = ""
    if hair == "tousled":
        d = (f"M {cx - r * 1.02} {cy + r * 0.05} Q {cx - r * 1.15} {cy - r * 0.9} {cx - r * 0.35} {cy - r * 1.12} "
             f"Q {cx} {cy - r * 1.3} {cx + r * 0.45} {cy - r * 1.08} Q {cx + r * 1.15} {cy - r * 0.85} {cx + r * 1.0} {cy + r * 0.05} "
             f"Q {cx + r * 0.95} {cy - r * 0.35} {cx + r * 0.72} {cy - r * 0.3} "
             f"Q {cx + r * 0.55} {cy - r * 0.55} {cx + r * 0.3} {cy - r * 0.38} "
             f"Q {cx + r * 0.05} {cy - r * 0.6} {cx - r * 0.22} {cy - r * 0.36} "
             f"Q {cx - r * 0.5} {cy - r * 0.58} {cx - r * 0.7} {cy - r * 0.3} "
             f"Q {cx - r * 0.95} {cy - r * 0.35} {cx - r * 1.02} {cy + r * 0.05} Z")
        hairsvg = P(d, 4.5, "white")
    elif hair == "bob_bangs":
        d = (f"M {cx - r * 1.14} {cy + r * 0.62} Q {cx - r * 1.3} {cy - r * 0.9} {cx - r * 0.4} {cy - r * 1.18} "
             f"Q {cx + r * 0.4} {cy - r * 1.35} {cx + r * 1.05} {cy - r * 0.6} Q {cx + r * 1.28} {cy - r * 0.1} {cx + r * 1.14} {cy + r * 0.62} "
             f"Q {cx + r * 0.98} {cy + r * 0.75} {cx + r * 0.88} {cy + r * 0.55} "
             f"L {cx + r * 0.86} {cy - r * 0.28} "
             f"Q {cx + r * 0.45} {cy - r * 0.5} {cx + r * 0.1} {cy - r * 0.34} "
             f"Q {cx - r * 0.3} {cy - r * 0.52} {cx - r * 0.86} {cy - r * 0.3} "
             f"L {cx - r * 0.88} {cy + r * 0.55} Q {cx - r * 0.98} {cy + r * 0.75} {cx - r * 1.14} {cy + r * 0.62} Z")
        hairsvg = P(d, 4.5, "white")
    elif hair == "bob":
        d = (f"M {cx - r * 1.16} {cy + r * 0.85} Q {cx - r * 1.32} {cy - r * 0.85} {cx - r * 0.4} {cy - r * 1.2} "
             f"Q {cx + r * 0.45} {cy - r * 1.38} {cx + r * 1.1} {cy - r * 0.55} Q {cx + r * 1.3} {cy} {cx + r * 1.16} {cy + r * 0.85} "
             f"Q {cx + r * 1.0} {cy + r * 1.0} {cx + r * 0.9} {cy + r * 0.75} "
             f"L {cx + r * 0.88} {cy - r * 0.2} "
             f"Q {cx + r * 0.2} {cy - r * 0.62} {cx - r * 0.55} {cy - r * 0.36} "
             f"Q {cx - r * 0.8} {cy - r * 0.28} {cx - r * 0.88} {cy - r * 0.05} "
             f"L {cx - r * 0.9} {cy + r * 0.75} Q {cx - r * 1.0} {cy + r * 1.0} {cx - r * 1.16} {cy + r * 0.85} Z")
        hairsvg = P(d, 4.5, "white")
        if headband:
            hairsvg += P(f"M {cx - r * 0.95} {cy - r * 0.42} Q {cx} {cy - r * 1.02} {cx + r * 0.95} {cy - r * 0.35}", 4)
    elif hair == "long_wavy":
        d = (f"M {cx - r * 1.3} {cy + r * 1.15} Q {cx - r * 1.45} {cy - r * 0.8} {cx - r * 0.45} {cy - r * 1.2} "
             f"Q {cx + r * 0.45} {cy - r * 1.4} {cx + r * 1.2} {cy - r * 0.5} Q {cx + r * 1.45} {cy + r * 0.2} {cx + r * 1.3} {cy + r * 1.15} "
             f"Q {cx + r * 1.05} {cy + r * 1.35} {cx + r * 0.92} {cy + r * 1.05} "
             f"L {cx + r * 0.9} {cy - r * 0.15} Q {cx + r * 0.2} {cy - r * 0.66} {cx - r * 0.5} {cy - r * 0.4} "
             f"Q {cx - r * 0.85} {cy - r * 0.3} {cx - r * 0.9} {cy + r * 0.05} L {cx - r * 0.92} {cy + r * 1.05} "
             f"Q {cx - r * 1.05} {cy + r * 1.35} {cx - r * 1.3} {cy + r * 1.15} Z")
        hairsvg = P(d, 4.5, "white")
    elif hair == "pigtails":
        d = (f"M {cx - r * 1.05} {cy + r * 0.2} Q {cx - r * 1.25} {cy - r * 0.9} {cx - r * 0.4} {cy - r * 1.16} "
             f"Q {cx + r * 0.4} {cy - r * 1.32} {cx + r * 1.02} {cy - r * 0.58} Q {cx + r * 1.2} {cy - r * 0.1} {cx + r * 1.05} {cy + r * 0.2} "
             f"L {cx + r * 0.86} {cy - r * 0.28} "
             f"Q {cx + r * 0.45} {cy - r * 0.5} {cx + r * 0.1} {cy - r * 0.34} "
             f"Q {cx - r * 0.3} {cy - r * 0.52} {cx - r * 0.86} {cy - r * 0.3} Z")
        hairsvg = P(d, 4.5, "white")
        for sx in (-1, 1):
            px = cx + sx * r * 1.32
            hairsvg += C(px, cy - r * 0.1, r * 0.38, 4, "white")
            hairsvg += C(px, cy + r * 0.42, r * 0.3, 4, "white")
            hairsvg += LINE(px - r * 0.2, cy + r * 0.12, px + r * 0.2, cy + r * 0.12, 3)
    elif hair == "curly":
        bumps = []
        n = 7
        for i in range(n + 1):
            a = math.pi - i * math.pi / n
            bumps.append((cx + r * 1.12 * math.cos(a), cy - r * 0.18 - r * 0.95 * math.sin(a)))
        d = f"M {bumps[0][0]:.0f} {bumps[0][1]:.0f} "
        for i in range(n):
            mx = (bumps[i][0] + bumps[i + 1][0]) / 2
            my = (bumps[i][1] + bumps[i + 1][1]) / 2 - r * 0.34
            d += f"Q {mx:.0f} {my:.0f} {bumps[i+1][0]:.0f} {bumps[i+1][1]:.0f} "
        d += (f"Q {cx + r * 0.6} {cy - r * 0.2} {cx + r * 0.3} {cy - r * 0.38} "
              f"Q {cx} {cy - r * 0.56} {cx - r * 0.3} {cy - r * 0.36} "
              f"Q {cx - r * 0.7} {cy - r * 0.2} {bumps[0][0]:.0f} {bumps[0][1]:.0f} Z")
        hairsvg = P(d, 4.5, "white")
    elif hair == "buzz":
        hairsvg = P(f"M {cx - r * 0.97} {cy - r * 0.18} Q {cx} {cy - r * 1.22} {cx + r * 0.97} {cy - r * 0.18}", 4.5)
        hairsvg += "".join(LINE(cx + dx * r, cy - r * 0.62 + abs(dx) * r * 0.3, cx + dx * r, cy - r * 0.48 + abs(dx) * r * 0.3, 3)
                           for dx in (-0.5, -0.17, 0.17, 0.5))
    browsvg = ""
    if brows:  # raised high = friendly-surprised; never close above the eyes
        browsvg = P(f"M {cx - ex - 6} {ey - 19} Q {cx - ex} {ey - 23} {cx - ex + 6} {ey - 19}", 3) + \
                  P(f"M {cx + ex - 6} {ey - 19} Q {cx + ex} {ey - 23} {cx + ex + 6} {ey - 19}", 3)
    beardsvg = ""
    if beard:  # short friendly beard hugging the jaw, mouth stays visible above it
        beardsvg = P(f"M {cx - r * 0.72} {cy + r * 0.15} Q {cx} {cy + r * 1.18} {cx + r * 0.72} {cy + r * 0.15} "
                     f"Q {cx + r * 0.45} {cy + r * 0.55} {cx} {cy + r * 0.82} "
                     f"Q {cx - r * 0.45} {cy + r * 0.55} {cx - r * 0.72} {cy + r * 0.15} Z", 3.5, "white")
    eyes = DOT(cx - ex, ey) + DOT(cx + ex, ey)
    if mouth == "open":  # closed D-shape: unambiguously joyful
        msvg = P(f"M {cx - r * 0.22} {cy + r * 0.40} Q {cx} {cy + r * 0.80} {cx + r * 0.22} {cy + r * 0.40} Z", 3.5, "white")
    elif mouth == "none":
        msvg = ""
    else:  # narrow deep U (a wide flat arc reads as a smirk)
        msvg = P(f"M {cx - r * 0.24} {cy + r * 0.40} Q {cx} {cy + r * 0.70} {cx + r * 0.24} {cy + r * 0.40}", 4)
    cheeksvg = ""
    if cheeks and extras and not freckles:  # freckle clusters own the cheek area
        cheeksvg = C(cx - r * 0.56, cy + r * 0.34, r * 0.10, 2.5) + \
                   C(cx + r * 0.56, cy + r * 0.34, r * 0.10, 2.5)
    out = s + hairsvg + beardsvg + browsvg + eyes + msvg + cheeksvg
    if glasses:
        gr = r * 0.30  # scale with the head — fixed-size lenses read as owl eyes on small figures
        out += C(cx - ex, ey, gr, 3.5) + C(cx + ex, ey, gr, 3.5) + LINE(cx - ex + gr, ey, cx + ex - gr, ey, 3.5)
    if freckles and extras:
        out += "".join(DOT(x, y, 2) for x, y in
                       [(cx - r * 0.55, cy + r * 0.32), (cx - r * 0.42, cy + r * 0.42), (cx - r * 0.62, cy + r * 0.45),
                        (cx + r * 0.55, cy + r * 0.32), (cx + r * 0.42, cy + r * 0.42), (cx + r * 0.62, cy + r * 0.45)])
    return out


def face_traits(cx, cy, r, t, extras=True):
    """face() driven by a character trait dict."""
    return face(cx, cy, r, hair=t.get("hair", "tousled"), glasses=t.get("glasses", False),
                freckles=t.get("freckles", False), headband=t.get("headband", False),
                beard=t.get("beard", False), extras=extras)


# ---------------------------------------------------------------- kid figures
def kid_stand(t, pose="wave", outfit=None, accessories=()):
    """Standing kid, origin at feet center, ~250 tall * t.get('height',1.0).
    pose: wave | up | down | hold  — outfit: dress | tee
    accessories: subset of {crown, wand}. Scale externally with G()."""
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
        sh = (-20, -150), (20, -150)   # shoulder attach points l/r
    else:
        out.append(P("M -12 -70 L -12 -8 Q -12 0 -4 0 L 4 0", 5))
        out.append(P("M 14 -70 L 14 -8 Q 14 0 22 0 L 30 0", 5))
        out.append(P("M -18 -152 L 18 -152 L 26 -70 L -26 -70 Z", 5, "white"))
        out.append(P("M -22 -96 L 22 -96", 4))
        sh = (-18, -142), (18, -142)
    lsx, lsy = sh[0]
    rsx, rsy = sh[1]
    if pose == "wave":
        out.append(P(f"M {lsx} {lsy} Q -48 -128 -52 -100", 5))
        out.append(C(-54, -94, 8, 4, "white"))
        out.append(P(f"M {rsx} {rsy} Q 44 -156 52 -180", 5))
        out.append(C(55, -186, 8, 4, "white"))
    elif pose == "up":
        out.append(P(f"M {lsx} {lsy} Q -52 -172 -62 -200", 5))
        out.append(C(-64, -207, 8, 4, "white"))
        out.append(P(f"M {rsx} {rsy} Q 52 -172 62 -200", 5))
        out.append(C(64, -207, 8, 4, "white"))
    elif pose == "down":
        out.append(P(f"M {lsx} {lsy} Q -44 -120 -46 -92", 5))
        out.append(C(-48, -86, 8, 4, "white"))
        out.append(P(f"M {rsx} {rsy} Q 44 -120 46 -92", 5))
        out.append(C(48, -86, 8, 4, "white"))
    elif pose == "hold":  # both arms forward (for basket/toy/leash)
        out.append(P(f"M {lsx} {lsy} Q -44 -128 -46 -102", 5))
        out.append(C(-47, -96, 8, 4, "white"))
        out.append(P(f"M {rsx} {rsy} Q 44 -128 46 -102", 5))
        out.append(C(47, -96, 8, 4, "white"))
    if "wand" in accessories:
        out.append(wand(58, -190 if pose == "wave" else -100, 55, 55, 4, 15))
    out.append(face_traits(0, head_y, 37, t))
    if "crown" in accessories:
        out.append(crown(0, head_y - 42, 58, 34, 4))
    return "".join(out)


def kid_sitting(t):
    """Kid sitting holding a game controller. Origin at seat."""
    out = []
    out.append(P("M -18 0 L -20 70 Q -20 82 -8 82 L 2 82", 5))
    out.append(P("M 18 0 L 20 70 Q 20 82 32 82 L 42 82", 5))
    out.append(P("M -24 4 L -22 -78 L 24 -78 L 26 4 Z", 5, "white"))
    out.append(P("M -20 -60 Q -34 -40 -20 -26", 5))
    out.append(P("M 22 -60 Q 36 -40 22 -26", 5))
    out.append(P("M -22 -34 Q -30 -34 -30 -22 Q -30 -12 -20 -14 L -12 -20 L 12 -20 L 20 -14 Q 30 -12 30 -22 Q 30 -34 22 -34 Z", 4, "white"))
    out.append(DOT(-20, -26, 3) + DOT(18, -28, 2.6) + DOT(24, -22, 2.6))
    out.append(C(-28, -18, 5.5, 3.5, "white") + C(28, -18, 5.5, 3.5, "white"))
    out.append(face_traits(0, -112, 34, t))
    return "".join(out)


# ---------------------------------------------------------------- animals
def dog(t=None, pose="stand"):
    """Side-view dog facing right, origin at feet. ~150 tall.
    traits: coat: plain|spots|patch ; collar: True ; floppy_ears: True"""
    t = t or {}
    out = []
    # body
    out.append(P("M -62 -46 Q -70 -84 -36 -88 L 34 -88 Q 66 -84 64 -50 Q 62 -26 34 -24 L -38 -24 Q -60 -26 -62 -46 Z", 4.5, "white"))
    # legs
    for lx in (-48, -24, 14, 42):
        out.append(P(f"M {lx} -24 L {lx} 0", 4.5))
        out.append(P(f"M {lx-5} 0 L {lx+6} 0", 4))
    # tail up-curl
    out.append(P("M -60 -62 Q -84 -74 -80 -96 Q -70 -92 -64 -80", 4.5, "white"))
    # head
    out.append(C(58, -104, 26, 4.5, "white"))
    out.append(P("M 78 -100 Q 92 -98 90 -88 Q 82 -82 72 -86", 4, "white"))  # muzzle
    out.append(DOT(88, -94, 3.5))  # nose
    out.append(DOT(60, -110, 3))   # eye
    out.append(P("M 76 -84 Q 72 -78 66 -80", 3.5))  # mouth
    if t.get("floppy_ears", True):
        out.append(P("M 44 -122 Q 30 -132 26 -112 Q 26 -96 38 -92 Q 44 -104 46 -116", 4, "white"))
    else:
        out.append(P("M 44 -124 L 38 -142 L 52 -132 Z", 4, "white"))
    coat = t.get("coat", "plain")
    if coat == "spots":
        out.append(E(-20, -60, 12, 9, 3) + E(16, -50, 9, 7, 3) + E(2, -74, 7, 6, 3))
    elif coat == "patch":
        out.append(E(52, -112, 10, 12, 3))
    if t.get("collar", True):
        out.append(P("M 38 -88 Q 52 -80 68 -84", 3.5))
        out.append(C(54, -78, 4.5, 3, "white"))
    return "".join(out)


def cat_sitting(t=None):
    """Sitting cat facing right, origin at feet. ~120 tall."""
    t = t or {}
    out = []
    out.append(P("M -30 0 Q -44 -40 -20 -68 Q -6 -80 10 -68 Q 30 -44 26 0 Z", 4.5, "white"))
    out.append(P("M -30 0 L 26 0", 4.5))
    out.append(P("M 26 -6 Q 48 -10 46 -30 Q 40 -28 36 -20", 4))  # tail
    out.append(C(-4, -88, 22, 4.5, "white"))
    out.append(P("M -20 -104 L -16 -122 L -4 -108 Z", 4, "white"))
    out.append(P("M 8 -108 L 16 -124 L 22 -106 Z", 4, "white"))
    out.append(DOT(-11, -90, 2.8) + DOT(5, -90, 2.8))
    out.append(P("M -6 -82 Q -3 -79 0 -82", 3))
    out.append(LINE(-24, -84, -34, -86, 2.5) + LINE(-24, -80, -34, -78, 2.5))
    out.append(LINE(18, -84, 28, -86, 2.5) + LINE(18, -80, 28, -78, 2.5))
    if t.get("coat") == "stripes":
        out.append(P("M -18 -56 Q -10 -60 -2 -56 M -14 -42 Q -6 -46 2 -42", 3))
    return "".join(out)


# ---------------------------------------------------------------- page/pdf
def page(title, body, num=None, caption=None):
    parts = [f'<rect x="0" y="0" width="{W}" height="{H}" fill="white"/>',
             f'<rect x="28" y="28" width="{W-56}" height="{H-56}" rx="26" fill="none" stroke="black" stroke-width="6"/>']
    if title:
        parts.append(TXT(W / 2, 100, title, 42))
        parts.append(P(f"M {W/2-260} 122 Q {W/2} 138 {W/2+260} 122", 4))
    parts.append(body)
    if caption:
        parts.append(TXT(W / 2, H - 62, caption, 26, weight="normal"))
    if num:
        parts.append(TXT(W / 2, H - 40 if not caption else H - 34, str(num), 20, weight="normal"))
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">' + "".join(parts) + "</svg>"


def build(builders, outdir, only=None, pdf_name="coloring-book.pdf"):
    """builders: list of (name, fn) -> svg string. Writes svg/png/pdf per page,
    merges to PDF with ghostscript. `only`: substring filter for partial rebuild."""
    import cairosvg, os, subprocess
    pages_dir = os.path.join(outdir, "pages")
    os.makedirs(pages_dir, exist_ok=True)
    for name, fn in builders:
        if only and not any(o in name for o in only):
            continue
        svg = fn()
        p = os.path.join(pages_dir, name)
        open(p + ".svg", "w").write(svg)
        cairosvg.svg2png(url=p + ".svg", write_to=p + ".png", output_width=680)
        cairosvg.svg2pdf(url=p + ".svg", write_to=p + ".pdf", output_width=612, output_height=792)
        print("built", name)
    if not only:
        allp = [os.path.join(pages_dir, n + ".pdf") for n, _ in builders]
        out = os.path.join(outdir, pdf_name)
        subprocess.run(["gs", "-dBATCH", "-dNOPAUSE", "-q", "-sDEVICE=pdfwrite",
                        f"-sOutputFile={out}"] + allp, check=True)
        print("PDF:", out)
        return out


def render_tiles(svg_path, outdir, name):
    """Render full page + 6 overlapping tiles for VLM QA review."""
    import cairosvg, os
    from PIL import Image
    os.makedirs(outdir, exist_ok=True)
    big = os.path.join(outdir, name + "-full.png")
    cairosvg.svg2png(url=svg_path, write_to=big, output_width=1275)
    im = Image.open(big)
    paths = [big]
    for r, (y0, y1) in enumerate([(0, 650), (500, 1150), (1000, 1650)]):
        for c, (x0, x1) in enumerate([(0, 710), (565, 1275)]):
            p = os.path.join(outdir, f"{name}-r{r}c{c}.png")
            im.crop((x0, y0, x1, y1)).save(p)
            paths.append(p)
    return paths


# ---------------------------------------------------------------- room furniture, props & story helpers
FLOOR = 960  # default scene floor for room helpers

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


def rrect(x, y, w, h, r=8, sw=SW, fill="white"):
    return (f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
            f'rx="{r}" fill="{fill}" stroke="black" stroke-width="{sw}"/>')


def otext(x, y, s, size, sw=3, anchor="middle"):
    """Hollow (outline) block letters for tracing."""
    return (f'<text x="{x}" y="{y}" font-family="DejaVu Sans" font-size="{size}" '
            f'font-weight="bold" text-anchor="{anchor}" fill="white" stroke="black" '
            f'stroke-width="{sw}" letter-spacing="10">{s}</text>')


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


# ---------------------------------------------------------------- shape cookbook helpers
# Vehicles / buildings / trees / animals / playground built to reference/shape-cookbook.md
# proportions. Side-profile things face RIGHT; mirror with GM(). Wheels/feet/walls
# sit TANGENT to a ground line so they never float. Every closed shape fills white
# so overlaps knock out. See shape-cookbook.md for the relative-proportion recipes.

def _wheel(cx, g, r, sw=4.5):
    """Wheel tangent to ground line g (hub at g-r), with a hub circle."""
    return C(cx, g - r, r, sw, "white") + C(cx, g - r, r * 0.38, 3, "white")


def car_side(cx, ground_y, w=220, sw=5):
    """Side-profile car facing right, centered at cx, wheels tangent to ground_y.
    Cabin toward the rear, two windows, hood forward. ~0.62w tall."""
    x0 = cx - w / 2
    g = ground_y
    r = 0.11 * w
    hub = g - 0.13 * w            # body bottom / wheel hub line
    out = []
    # body (rounded, hood low in front, sill along hub line)
    out.append(rrect(x0, g - 0.42 * w, w, 0.29 * w, 0.10 * w, sw, "white"))
    # cabin (trapezoid, rear half): base wide, roof shorter
    cb_l, cb_r = x0 + 0.30 * w, x0 + 0.74 * w
    rf_l, rf_r = x0 + 0.40 * w, x0 + 0.68 * w
    top = g - 0.60 * w
    out.append(P(f"M {cb_l} {g - 0.42 * w} L {rf_l} {top} "
                 f"Q {(rf_l + rf_r) / 2} {top - 0.05 * w} {rf_r} {top} "
                 f"L {cb_r} {g - 0.42 * w} Z", sw, "white"))
    # windows (two, gap between)
    out.append(rrect(cb_l + 0.02 * w, top + 0.02 * w, 0.16 * w, 0.13 * w, 4, 3.5, "white"))
    out.append(rrect(x0 + 0.50 * w, top + 0.02 * w, 0.16 * w, 0.13 * w, 4, 3.5, "white"))
    # wheels
    out.append(_wheel(x0 + 0.22 * w, g, r, sw - 0.5))
    out.append(_wheel(x0 + 0.78 * w, g, r, sw - 0.5))
    # headlight + door line
    out.append(DOT(x0 + 0.96 * w, g - 0.30 * w, 3.5))
    out.append(LINE(x0 + 0.46 * w, g - 0.40 * w, x0 + 0.46 * w, hub, 3))
    return "".join(out)


def pickup_truck(cx, ground_y, w=240, sw=5):
    """Side-profile pickup: tall cab front + low open bed rear, wheels tangent."""
    x0 = cx - w / 2
    g = ground_y
    r = 0.11 * w
    out = []
    # bed (low, rear)
    out.append(rrect(x0 + 0.04 * w, g - 0.30 * w, 0.48 * w, 0.17 * w, 6, sw, "white"))
    # cab (tall, front)
    out.append(rrect(x0 + 0.52 * w, g - 0.55 * w, 0.44 * w, 0.42 * w, 8, sw, "white"))
    # cab window
    out.append(rrect(x0 + 0.60 * w, g - 0.52 * w, 0.20 * w, 0.16 * w, 4, 3.5, "white"))
    # bed/cab seam wall
    out.append(LINE(x0 + 0.52 * w, g - 0.30 * w, x0 + 0.52 * w, g - 0.13 * w, sw))
    # wheels
    out.append(_wheel(x0 + 0.20 * w, g, r, sw - 0.5))
    out.append(_wheel(x0 + 0.80 * w, g, r, sw - 0.5))
    out.append(DOT(x0 + 0.94 * w, g - 0.30 * w, 3.5))   # headlight
    return "".join(out)


def tractor(cx, ground_y, w=220, sw=5):
    """Side-profile tractor: BIG rear wheel + small front wheel (the whole read)."""
    x0 = cx - w / 2
    g = ground_y
    rr, fr = 0.24 * w, 0.12 * w
    rcx, fcx = x0 + 0.72 * w, x0 + 0.20 * w
    out = []
    # hood/body: front axle area up and back to the seat
    out.append(P(f"M {fcx} {g - 0.18 * w} L {fcx} {g - 0.30 * w} "
                 f"L {x0 + 0.5 * w} {g - 0.34 * w} L {x0 + 0.58 * w} {g - 0.34 * w} "
                 f"L {x0 + 0.62 * w} {g - 0.5 * w} L {x0 + 0.80 * w} {g - 0.5 * w} "
                 f"L {x0 + 0.84 * w} {g - 0.20 * w} L {rcx + rr} {g - 0.20 * w} Z", sw, "white"))
    # seat + backrest
    out.append(P(f"M {x0 + 0.62 * w} {g - 0.5 * w} L {x0 + 0.62 * w} {g - 0.62 * w} "
                 f"L {x0 + 0.70 * w} {g - 0.62 * w}", sw))
    out.append(P(f"M {x0 + 0.66 * w} {g - 0.5 * w} L {x0 + 0.78 * w} {g - 0.5 * w}", sw))
    # exhaust stub
    out.append(LINE(x0 + 0.52 * w, g - 0.34 * w, x0 + 0.52 * w, g - 0.52 * w, 4))
    # big rear wheel with spokes
    out.append(_wheel(rcx, g, rr, sw - 0.5))
    for i in range(6):
        a = i * math.pi / 3
        out.append(LINE(rcx, g - rr, rcx + rr * 0.9 * math.cos(a), g - rr + rr * 0.9 * math.sin(a), 3))
    # small front wheel
    out.append(_wheel(fcx, g, fr, sw - 0.5))
    return "".join(out)


def train_engine(cx, ground_y, w=280, sw=5):
    """Side-profile steam locomotive facing right: long boiler, tall rear cab,
    cowcatcher wedge, smokestack + puff, wheels tangent to ground."""
    x0 = cx - w / 2
    g = ground_y
    out = []
    # cowcatcher wedge at the front
    out.append(P(f"M {x0} {g - 0.06 * w} L {x0 + 0.10 * w} {g - 0.34 * w} "
                 f"L {x0 + 0.10 * w} {g - 0.06 * w} Z", sw, "white"))
    # boiler (long cylinder)
    out.append(rrect(x0 + 0.10 * w, g - 0.46 * w, 0.56 * w, 0.28 * w, 0.14 * w, sw, "white"))
    # cab (tall, rear)
    out.append(rrect(x0 + 0.66 * w, g - 0.60 * w, 0.32 * w, 0.44 * w, 6, sw, "white"))
    out.append(rrect(x0 + 0.72 * w, g - 0.56 * w, 0.20 * w, 0.16 * w, 4, 3.5, "white"))  # cab window
    # smokestack + puff
    out.append(P(f"M {x0 + 0.16 * w} {g - 0.46 * w} L {x0 + 0.14 * w} {g - 0.62 * w} "
                 f"L {x0 + 0.26 * w} {g - 0.62 * w} L {x0 + 0.24 * w} {g - 0.46 * w}", sw, "white"))
    out.append(cloud(x0 + 0.20 * w, g - 0.72 * w, 0.05 * w))
    # steam dome
    out.append(P(f"M {x0 + 0.40 * w} {g - 0.46 * w} Q {x0 + 0.46 * w} {g - 0.58 * w} "
                 f"{x0 + 0.52 * w} {g - 0.46 * w}", sw, "white"))
    # chassis bar
    out.append(LINE(x0 + 0.08 * w, g - 0.16 * w, x0 + 0.98 * w, g - 0.16 * w, sw))
    # wheels: two small + a big driver under the cab
    out.append(_wheel(x0 + 0.22 * w, g, 0.10 * w, sw - 0.5))
    out.append(_wheel(x0 + 0.44 * w, g, 0.10 * w, sw - 0.5))
    out.append(_wheel(x0 + 0.78 * w, g, 0.14 * w, sw - 0.5))
    return "".join(out)


def bicycle(cx, ground_y, s=200, sw=5):
    """Side-profile bicycle facing right; s = overall width. TWO EQUAL wheels
    tangent to ground_y, diamond frame strung between the hubs, seat + handlebars.
    (The object LLMs most reliably mangle — proportions are locked here.)"""
    x0 = cx - s / 2
    g = ground_y
    r = 0.22 * s
    rhx, fhx = x0 + 0.22 * s, x0 + 0.78 * s   # rear / front hub x
    hy = g - r                                 # hub y (both equal)
    pedx, pedy = (rhx + fhx) / 2, g - 0.22 * s  # pedal/bottom-bracket
    seatx, seaty = x0 + 0.40 * s, g - 0.5 * s   # seat top vertex
    hbx, hby = fhx + 0.02 * s, g - 0.5 * s      # handlebar top
    out = []
    # two identical wheels
    out.append(C(rhx, hy, r, sw - 0.5, "white"))
    out.append(C(fhx, hy, r, sw - 0.5, "white"))
    out.append(DOT(rhx, hy, 3.5) + DOT(fhx, hy, 3.5))   # hubs
    # frame diamond: rear hub -> seat -> pedal -> rear hub, seat -> pedal, pedal -> front hub
    out.append(LINE(rhx, hy, seatx, seaty, sw))
    out.append(LINE(seatx, seaty, pedx, pedy, sw))
    out.append(LINE(pedx, pedy, rhx, hy, sw))
    out.append(LINE(pedx, pedy, fhx, hy, sw))            # down tube to front hub
    # head tube / fork up to handlebars
    out.append(LINE(seatx, seaty, hbx, hby, sw))         # top tube to steering
    out.append(LINE(hbx, hby, fhx, hy, sw))              # fork
    # seat
    out.append(P(f"M {seatx - 0.05 * s} {seaty} L {seatx + 0.05 * s} {seaty - 0.01 * s}", sw))
    # handlebars
    out.append(P(f"M {hbx - 0.06 * s} {hby - 0.02 * s} L {hbx + 0.03 * s} {hby}", sw))
    # pedal + cranks
    out.append(C(pedx, pedy, 0.03 * s, 3.5, "white"))
    out.append(LINE(pedx, pedy, pedx + 0.05 * s, pedy + 0.04 * s, 3.5))
    return "".join(out)


def tree_round(cx, ground_y, h=260, sw=5):
    """Lollipop tree: stubby trunk + fat round canopy, base tangent to ground_y."""
    g = ground_y
    tw = 0.18 * h
    out = [rrect(cx - tw / 2, g - 0.28 * h, tw, 0.28 * h, 6, sw, "white")]
    # 3-lobe canopy centered above the trunk (overlaps trunk top)
    cyy = g - 0.62 * h
    out.append(C(cx, cyy, 0.34 * h, sw, "white"))
    out.append(C(cx - 0.24 * h, cyy + 0.10 * h, 0.20 * h, sw, "white"))
    out.append(C(cx + 0.24 * h, cyy + 0.10 * h, 0.20 * h, sw, "white"))
    # re-cap the crown so lobe seams read as one canopy
    out.append(C(cx, cyy, 0.34 * h, sw, "white"))
    return "".join(out)


def tree_pine(cx, ground_y, h=280, sw=5):
    """Pine: 3 stacked triangles, each narrower + higher, trunk peeking below."""
    g = ground_y
    tw = 0.12 * h
    out = [rrect(cx - tw / 2, g - 0.14 * h, tw, 0.14 * h, 3, sw, "white")]
    tiers = [(0.70, 0.14, 0.52), (0.55, 0.36, 0.74), (0.40, 0.58, 1.00)]
    for base_w, base_y, apex_y in tiers:
        bw = base_w * h
        out.append(P(f"M {cx - bw / 2} {g - base_y * h} L {cx} {g - apex_y * h} "
                     f"L {cx + bw / 2} {g - base_y * h} Z", sw, "white"))
    return "".join(out)


def house(cx, ground_y, w=240, sw=5):
    """Simple house: walls on ground, overhanging triangular roof, door + windows."""
    x0 = cx - w / 2
    g = ground_y
    out = []
    out.append(rrect(x0 + 0.05 * w, g - 0.55 * w, 0.90 * w, 0.55 * w, 4, sw, "white"))  # walls
    out.append(P(f"M {x0} {g - 0.55 * w} L {cx} {g - 0.95 * w} "
                 f"L {x0 + w} {g - 0.55 * w} Z", sw, "white"))                          # roof
    # door
    out.append(rrect(cx - 0.09 * w, g - 0.32 * w, 0.18 * w, 0.32 * w, 4, sw, "white"))
    out.append(DOT(cx + 0.05 * w, g - 0.16 * w, 3.5))
    # two windows
    for wx in (x0 + 0.16 * w, x0 + 0.66 * w):
        out.append(rrect(wx, g - 0.44 * w, 0.14 * w, 0.14 * w, 3, 3.5, "white"))
        out.append(LINE(wx + 0.07 * w, g - 0.44 * w, wx + 0.07 * w, g - 0.30 * w, 3))
        out.append(LINE(wx, g - 0.37 * w, wx + 0.14 * w, g - 0.37 * w, 3))
    # chimney
    out.append(rrect(x0 + 0.66 * w, g - 0.86 * w, 0.08 * w, 0.20 * w, 2, sw, "white"))
    return "".join(out)


def horse(cx, ground_y, w=240, sw=4.5):
    """Lutz-style side-view horse facing right, feet on ground_y. Reuses dog()'s
    four-posts-under-a-barrel legs + arched neck + long head + mane + tail."""
    x0 = cx - w / 2
    g = ground_y
    out = []
    # tail: flows OUTWARD behind the rump (a straight-down tail next to the rear
    # legs reads as a fifth leg; a filled blob reads as a flipper)
    out.append(P(f"M {x0 + 0.21 * w} {g - 0.56 * w} Q {x0 + 0.02 * w} {g - 0.50 * w} "
                 f"{x0 + 0.04 * w} {g - 0.20 * w}", sw))
    out.append(P(f"M {x0 + 0.21 * w} {g - 0.51 * w} Q {x0 + 0.07 * w} {g - 0.45 * w} "
                 f"{x0 + 0.09 * w} {g - 0.22 * w}", 3.5))
    # neck (head caps the top): arches up-forward, muzzle points forward-down
    out.append(P(f"M {x0 + 0.64 * w} {g - 0.52 * w} Q {x0 + 0.74 * w} {g - 0.68 * w} "
                 f"{x0 + 0.82 * w} {g - 0.68 * w} L {x0 + 0.86 * w} {g - 0.56 * w} "
                 f"Q {x0 + 0.78 * w} {g - 0.5 * w} {x0 + 0.72 * w} {g - 0.44 * w} Z", sw, "white"))
    # 4 legs (paired front/back) with hooves
    for lx in (0.30, 0.40, 0.60, 0.70):
        px = x0 + lx * w
        out.append(P(f"M {px} {g - 0.4 * w} L {px} {g}", sw))
        out.append(P(f"M {px - 0.025 * w} {g} L {px + 0.035 * w} {g}", sw))
    # body barrel
    out.append(E(x0 + 0.46 * w, g - 0.5 * w, 0.30 * w, 0.18 * w, sw, "white"))
    # head: long muzzle angled forward-down off the neck top
    out.append(E(x0 + 0.88 * w, g - 0.64 * w, 0.13 * w, 0.075 * w, sw, "white"))
    # ears
    out.append(P(f"M {x0 + 0.80 * w} {g - 0.70 * w} L {x0 + 0.79 * w} {g - 0.80 * w} "
                 f"L {x0 + 0.84 * w} {g - 0.72 * w}", sw - 1, "white"))
    # forelock / mane: short scallops down the back of the neck
    out.append(P(f"M {x0 + 0.70 * w} {g - 0.5 * w} Q {x0 + 0.68 * w} {g - 0.58 * w} "
                 f"{x0 + 0.76 * w} {g - 0.62 * w} Q {x0 + 0.74 * w} {g - 0.68 * w} "
                 f"{x0 + 0.80 * w} {g - 0.70 * w}", 3.5))
    # face
    out.append(DOT(x0 + 0.86 * w, g - 0.66 * w, 3))       # eye
    out.append(DOT(x0 + 0.99 * w, g - 0.63 * w, 2.6))     # nostril
    return "".join(out)


def bird_side(cx, ground_y, w=120, sw=4.5):
    """Perched side-view bird facing right; egg body, round head, up-cocked tail,
    short beak, tucked wing, feet on ground_y."""
    x0 = cx - w / 2
    g = ground_y
    out = []
    # tail off the rear, pointing back-down
    out.append(P(f"M {x0 + 0.16 * w} {g - 0.36 * w} L {x0 - 0.02 * w} {g - 0.28 * w} "
                 f"L {x0 + 0.18 * w} {g - 0.22 * w} Z", sw, "white"))
    # body egg
    out.append(E(x0 + 0.42 * w, g - 0.34 * w, 0.30 * w, 0.22 * w, sw, "white"))
    # head
    out.append(C(x0 + 0.74 * w, g - 0.5 * w, 0.2 * w, sw, "white"))
    # beak
    out.append(P(f"M {x0 + 0.92 * w} {g - 0.52 * w} L {x0 + 1.02 * w} {g - 0.48 * w} "
                 f"L {x0 + 0.92 * w} {g - 0.44 * w} Z", sw - 1, "white"))
    # wing (tucked arc)
    out.append(P(f"M {x0 + 0.34 * w} {g - 0.44 * w} Q {x0 + 0.52 * w} {g - 0.5 * w} "
                 f"{x0 + 0.56 * w} {g - 0.3 * w} Q {x0 + 0.44 * w} {g - 0.32 * w} "
                 f"{x0 + 0.34 * w} {g - 0.44 * w}", sw - 1))
    # legs
    for lx in (0.42, 0.54):
        px = x0 + lx * w
        out.append(LINE(px, g - 0.14 * w, px, g, sw - 1))
        out.append(LINE(px - 0.03 * w, g, px + 0.03 * w, g, sw - 1.5))
    out.append(DOT(x0 + 0.80 * w, g - 0.54 * w, 3))       # eye
    return "".join(out)


def swing_set(cx, ground_y, w=240, sw=5):
    """A-frame swing set with a hanging seat; frame feet tangent to ground_y."""
    x0 = cx - w / 2
    g = ground_y
    top = g - 0.9 * w * 0.5   # apex height keyed to a squarer footprint
    apex_y = g - 0.62 * w
    la, ra = x0 + 0.14 * w, x0 + 0.86 * w
    out = []
    # left A-frame
    out.append(LINE(la, apex_y, x0 + 0.02 * w, g, sw))
    out.append(LINE(la, apex_y, x0 + 0.26 * w, g, sw))
    # right A-frame
    out.append(LINE(ra, apex_y, x0 + 0.74 * w, g, sw))
    out.append(LINE(ra, apex_y, x0 + 0.98 * w, g, sw))
    # top beam
    out.append(LINE(la, apex_y, ra, apex_y, sw))
    # swing ropes (parallel) + seat
    scx = cx
    rope_top = apex_y
    seat_y = g - 0.20 * w
    out.append(LINE(scx - 0.06 * w, rope_top, scx - 0.06 * w, seat_y, 3.5))
    out.append(LINE(scx + 0.06 * w, rope_top, scx + 0.06 * w, seat_y, 3.5))
    out.append(rrect(scx - 0.10 * w, seat_y, 0.20 * w, 0.04 * w, 3, sw - 0.5, "white"))
    return "".join(out)


# ---------------------------------------------------------------- knockout mat
def matted(inner, pad=9):
    """Anti-tangency halo: returns a white 'mat' copy of `inner` (every stroke
    whitened and thickened by `pad`) followed by `inner` itself. Draw background
    (rug, path, fence, furniture) first, then wrap each foreground figure/object
    in matted() — background lines get knocked out wherever they approach it,
    so tangent-line illusions can't happen. Nested G()/GM() transforms are kept."""
    import re
    mat = inner
    mat = re.sub(r'stroke-width="([0-9.]+)"',
                 lambda m: f'stroke-width="{float(m.group(1)) + pad:.1f}"', mat)
    mat = mat.replace('stroke="black"', 'stroke="white"')
    # fill-only elements (DOT/TXT/filled polygons) just go white in the mat;
    # adding stroke attrs here would duplicate attributes on stroked elements
    mat = mat.replace('fill="black"', 'fill="white"')
    return mat + inner
