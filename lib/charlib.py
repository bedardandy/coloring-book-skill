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
    if beard:
        # under-jaw fringe: a crescent hanging BELOW the face circle. No stroke
        # crosses the face interior (an inner edge across the face reads as a
        # giant grin), so the standard mouth stays untouched.
        beardsvg = P(f"M {cx - r * 0.82} {cy + r * 0.57} "
                     f"Q {cx - r * 0.55} {cy + r * 1.28} {cx} {cy + r * 1.30} "
                     f"Q {cx + r * 0.55} {cy + r * 1.28} {cx + r * 0.82} {cy + r * 0.57} "
                     f"Q {cx + r * 0.52} {cy + r * 0.98} {cx} {cy + r * 1.00} "
                     f"Q {cx - r * 0.52} {cy + r * 0.98} {cx - r * 0.82} {cy + r * 0.57} Z", 3.5, "white")
    eyes = DOT(cx - ex, ey) + DOT(cx + ex, ey)
    if mouth == "open":  # closed D-shape: unambiguously joyful
        msvg = P(f"M {cx - r * 0.22} {cy + r * 0.40} Q {cx} {cy + r * 0.80} {cx + r * 0.22} {cy + r * 0.40} Z", 3.5, "white")
    elif mouth == "none":
        msvg = ""
    else:  # narrow deep U (a wide flat arc reads as a smirk) — bearded faces too
        msvg = P(f"M {cx - r * 0.24} {cy + r * 0.40} Q {cx} {cy + r * 0.70} {cx + r * 0.24} {cy + r * 0.40}", 4)
    cheeksvg = ""
    if cheeks and extras and not freckles:  # under-jaw beard leaves cheeks free
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
        # cairosvg output_width is in px @96dpi; PDF units are pt (72dpi).
        # 816x1056px -> 612x792pt = true US letter.
        cairosvg.svg2pdf(url=p + ".svg", write_to=p + ".pdf", output_width=816, output_height=1056)
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


# ---------------------------------------------------------------- scene & prop library (harvested from production books, 2026-07)
def dog_sit(t, long_nose=False, wink=False):
    """Sitting dog facing right, origin at ground. ~150 tall."""
    out = []
    out.append(P("M -46 0 Q -62 -60 -28 -86 Q -4 -100 18 -84 Q 34 -70 32 -40 Q 30 -12 24 0 Z", 4.5, "white"))
    out.append(P("M 6 -60 L 10 0 M 24 -58 L 28 0", 4.5))
    out.append(P("M 4 0 L 16 0 M 22 0 L 34 0", 4))
    out.append(P("M -46 -8 Q -68 -14 -66 -34 Q -56 -30 -48 -22", 4, "white"))  # tail
    out.append(C(28, -110, 26, 4.5, "white"))                                  # head
    if long_nose:
        out.append(P("M 48 -106 Q 70 -104 68 -92 Q 58 -84 42 -90", 4, "white"))
        out.append(DOT(65, -98, 3.5))
    else:
        out.append(P("M 48 -106 Q 62 -104 60 -94 Q 52 -88 42 -92", 4, "white"))
        out.append(DOT(58, -100, 3.5))
    if wink:
        out.append(P("M 24 -118 Q 29 -114 34 -118", 3))
    else:
        out.append(DOT(30, -116, 3))
    out.append(P("M 46 -90 Q 42 -84 36 -86", 3.5))
    if t.get("floppy_ears", True):
        out.append(P("M 14 -128 Q 0 -138 -4 -118 Q -4 -102 8 -98 Q 14 -110 16 -122", 4, "white"))
    if t.get("coat") == "patch":
        out.append(E(22, -118, 10, 12, 3))
    if t.get("collar", True):
        out.append(P("M 8 -94 Q 22 -86 38 -90", 3.5))
        out.append(C(24, -84, 4.5, 3, "white"))
    return "".join(out)


def dog_sleep(t, long_nose=False, zzz=True):
    """Dog lying down 'asleep', head on paws, origin at ground. Facing right."""
    out = []
    out.append(E(-10, -34, 62, 32, 4.5, "white"))                              # body
    out.append(P("M -70 -22 Q -88 -30 -84 -48 Q -74 -42 -66 -34", 4, "white"))  # tail
    out.append(C(52, -34, 24, 4.5, "white"))                                   # head low
    if long_nose:
        out.append(P("M 70 -30 Q 90 -28 88 -18 Q 78 -12 64 -16", 4, "white"))
        out.append(DOT(85, -24, 3.2))
    else:
        out.append(P("M 70 -30 Q 82 -28 80 -18 Q 72 -14 62 -18", 4, "white"))
        out.append(DOT(77, -24, 3.2))
    out.append(P("M 44 -42 Q 49 -38 54 -42", 3))                               # closed eye
    out.append(P("M 38 -54 Q 24 -62 22 -44 Q 24 -32 36 -30", 4, "white"))      # ear
    out.append(P("M 30 -12 L 78 -12", 4))                                      # paws line
    out.append(P("M 34 -12 Q 34 -4 42 -4 L 70 -4 Q 78 -4 78 -12", 4, "white"))
    if t.get("coat") == "patch":
        out.append(E(48, -44, 9, 10, 3))
    if zzz:
        out.append(TXT(96, -76, "z", 17) + TXT(110, -92, "z", 14))
    return "".join(out)


def sock(cx, cy, s=1.0, rot=0):
    d = (f"M {-9*s} {-22*s} L {9*s} {-22*s} L {9*s} {2*s} Q {9*s} {12*s} {0} {14*s} "
         f"Q {-14*s} {16*s} {-15*s} {6*s} Q {-15*s} {0} {-9*s} {-2*s} Z")
    inner = P(f"M {-9*s} {-16*s} L {9*s} {-16*s}", 3)
    return G(cx, cy, P(d, 3.5, "white") + inner, 1.0, rot)


def cushion_fort(cx, gy):
    out = []
    for i, (dx, dy, w_, h_) in enumerate([(-70, 0, 90, 52), (20, 0, 90, 52), (-95, -52, 80, 48),
                                          (45, -52, 80, 48), (-25, -100, 96, 50)]):
        out.append(rrect(cx + dx, gy + dy - h_, w_, h_, 10, 4.5, "white"))
        out.append(P(f"M {cx+dx+10} {gy+dy-h_/2} L {cx+dx+w_-10} {gy+dy-h_/2}", 2.5))
    return "".join(out)


def table(cx, gy, w=240, h=120):
    out = [P(f"M {cx-w/2} {gy-h} L {cx+w/2} {gy-h} L {cx+w/2} {gy-h+16} L {cx-w/2} {gy-h+16} Z", 4.5, "white")]
    out.append(LINE(cx - w / 2 + 18, gy - h + 16, cx - w / 2 + 18, gy, 4.5))
    out.append(LINE(cx + w / 2 - 18, gy - h + 16, cx + w / 2 - 18, gy, 4.5))
    return "".join(out)


def food_bowl(cx, gy, label=""):
    out = [P(f"M {cx-36} {gy-24} L {cx+36} {gy-24} L {cx+28} {gy} L {cx-28} {gy} Z", 4.5, "white")]
    if label:
        out.append(TXT(cx, gy - 7, label, 14))
    return "".join(out)


def dirt_hole(cx, gy):
    out = [E(cx, gy, 46, 12, 4)]
    for dx, dy in [(-60, -40), (-30, -66), (10, -74), (46, -60), (70, -30)]:
        out.append(P(f"M {cx+dx} {gy+dy} Q {cx+dx+6} {gy+dy-10} {cx+dx+12} {gy+dy}", 3))
    return "".join(out)


def kibble(cx, cy, n=7):
    import math as m
    out = [P(f"M {cx-34} {cy} Q {cx} {cy-30} {cx+34} {cy} Z", 4, "white")]
    for i in range(n):
        a = m.pi * (0.15 + 0.7 * i / max(1, n - 1))
        out.append(DOT(cx - 40 * m.cos(a) * (0.6 + 0.4 * (i % 2)), cy - 24 - 14 * m.sin(a) - (i % 3) * 8, 3.5))
    return "".join(out)


def tiara(cx, cy, w=44):
    out = [P(f"M {cx-w/2} {cy} Q {cx} {cy-8} {cx+w/2} {cy}", 3.5)]
    for dx in (-w * 0.3, 0, w * 0.3):
        out.append(LINE(cx + dx, cy - 4, cx + dx, cy - 16, 3.5))
        out.append(DOT(cx + dx, cy - 19, 3))
    return "".join(out)


def chef_hat(cx, cy, w=54):
    """Classic toque: straight band + tall puff with three distinct bumps."""
    bw = w * 0.64
    out = []
    out.append(P(f"M {cx-bw/2} {cy-2} "
                 f"Q {cx-w*0.72} {cy-16} {cx-w*0.66} {cy-34} "
                 f"Q {cx-w*0.62} {cy-54} {cx-w*0.30} {cy-50} "
                 f"Q {cx-w*0.28} {cy-68} {cx} {cy-62} "
                 f"Q {cx+w*0.28} {cy-68} {cx+w*0.30} {cy-50} "
                 f"Q {cx+w*0.62} {cy-54} {cx+w*0.66} {cy-34} "
                 f"Q {cx+w*0.72} {cy-16} {cx+bw/2} {cy-2} Z", 4, "white"))
    # pleat lines on the puff
    out.append(P(f"M {cx-w*0.20} {cy-6} L {cx-w*0.23} {cy-42}", 2.5))
    out.append(P(f"M {cx} {cy-6} L {cx} {cy-48}", 2.5))
    out.append(P(f"M {cx+w*0.20} {cy-6} L {cx+w*0.23} {cy-42}", 2.5))
    # band with double line
    out.append(rrect(cx - bw / 2, cy - 2, bw, 20, 4, 4, "white"))
    out.append(LINE(cx - bw / 2 + 4, cy + 5, cx + bw / 2 - 4, cy + 5, 2.5))
    return "".join(out)


def bib_apron():
    """Baker's bib apron overlay for a baker figure — one clean silhouette, draw AFTER his figure.
    Kept deliberately simple: a busy chest (straps/bows/tools) reads as clutter."""
    out = []
    # single outline: narrow bib at the chest flaring into the skirt
    out.append(P("M -11 -146 L 11 -146 L 13 -102 L 26 -96 L 29 -44 "
                 "Q 0 -35 -29 -44 L -26 -96 L -13 -102 Z", 3.5, "white"))
    # waist line
    out.append(P("M -25 -95 L 25 -95", 2.5))
    # one pocket, low on the skirt where there's room
    out.append(rrect(-9, -80, 18, 15, 3, 2.5, "white"))
    return "".join(out)


def briefcase(cx, gy, s=1.0):
    return (rrect(cx - 34 * s, gy - 48 * s, 68 * s, 48 * s, 8, 4, "white") +
            P(f"M {cx-12*s} {gy-48*s} Q {cx-12*s} {gy-60*s} {cx} {gy-60*s} Q {cx+12*s} {gy-60*s} {cx+12*s} {gy-48*s}", 3.5) +
            rrect(cx - 7 * s, gy - 32 * s, 14 * s, 10 * s, 2, 2.5, "white"))


def cupcake(cx, gy, s=1.0, crowned=False):
    out = [P(f"M {cx-16*s} {gy-18*s} L {cx+16*s} {gy-18*s} L {cx+11*s} {gy} L {cx-11*s} {gy} Z", 3.5, "white")]
    out.append(LINE(cx - 8 * s, gy - 16 * s, cx - 6 * s, gy - 2 * s, 2) + LINE(cx + 8 * s, gy - 16 * s, cx + 6 * s, gy - 2 * s, 2))
    out.append(P(f"M {cx-16*s} {gy-18*s} Q {cx-14*s} {gy-34*s} {cx} {gy-34*s} Q {cx+14*s} {gy-34*s} {cx+16*s} {gy-18*s}", 3.5, "white"))
    out.append(P(f"M {cx-9*s} {gy-30*s} Q {cx} {gy-46*s} {cx+9*s} {gy-30*s}", 3, "white"))
    if crowned:
        out.append(P(f"M {cx-7*s} {gy-46*s} L {cx-7*s} {gy-54*s} L {cx-2*s} {gy-49*s} L {cx} {gy-56*s} L {cx+2*s} {gy-49*s} L {cx+7*s} {gy-54*s} L {cx+7*s} {gy-46*s} Z", 2.5, "white"))
    else:
        out.append(DOT(cx, gy - 48 * s, 3 * s))
    return "".join(out)


def bread_loaf(cx, gy, s=1.0):
    return (P(f"M {cx-30*s} {gy} Q {cx-34*s} {gy-26*s} {cx} {gy-28*s} Q {cx+34*s} {gy-26*s} {cx+30*s} {gy} Z", 3.5, "white") +
            P(f"M {cx-14*s} {gy-22*s} L {cx-8*s} {gy-14*s} M {cx-2*s} {gy-24*s} L {cx+4*s} {gy-16*s} M {cx+10*s} {gy-22*s} L {cx+16*s} {gy-14*s}", 2.5))


def oven(cx, gy, w=190):
    out = [rrect(cx - w / 2, gy - 200, w, 200, 8, 5, "white")]
    out.append(rrect(cx - w / 2 + 22, gy - 150, w - 44, 100, 6, 4, "white"))
    out.append(LINE(cx - w / 2 + 22, gy - 160, cx + w / 2 - 22, gy - 160, 3.5))
    for i, dx in enumerate((-40, -13, 13, 40)):
        out.append(C(cx + dx, gy - 180, 7, 3, "white"))
    out.append(P(f"M {cx-26} {gy-118} Q {cx} {gy-132} {cx+26} {gy-118}", 3))  # bread inside!
    return "".join(out)


def mixing_bowl(cx, gy, s=1.0):
    out = [P(f"M {cx-52*s} {gy-58*s} Q {cx-56*s} {gy} {cx} {gy} Q {cx+56*s} {gy} {cx+52*s} {gy-58*s} Z", 4.5, "white")]
    out.append(P(f"M {cx-52*s} {gy-58*s} L {cx+52*s} {gy-58*s}", 3.5))
    out.append(LINE(cx + 20 * s, gy - 58 * s, cx + 52 * s, gy - 108 * s, 4))  # spoon
    out.append(E(cx + 56 * s, gy - 114 * s, 10 * s, 14 * s, 3.5, "white"))
    return "".join(out)


def display_case(cx, gy, w=260, h=170):
    out = [rrect(cx - w / 2, gy - h, w, h, 6, 5, "white")]
    out.append(LINE(cx - w / 2 + 10, gy - h * 0.52, cx + w / 2 - 10, gy - h * 0.52, 3.5))
    for i, dx in enumerate((-w * 0.3, 0, w * 0.3)):
        out.append(cupcake(cx + dx, gy - h * 0.58, 0.9, crowned=True))
    out.append(bread_loaf(cx - w * 0.25, gy - 12, 1.0))
    out.append(cupcake(cx + w * 0.22, gy - 12, 1.0))
    return "".join(out)


def easel(cx, gy):
    out = [P(f"M {cx-52} {gy} L {cx} {gy-190} L {cx+52} {gy} M {cx} {gy-190} L {cx} {gy-30}", 4)]
    out.append(rrect(cx - 70, gy - 180, 140, 110, 4, 4.5, "white"))
    out.append(crown(cx - 24, gy - 110, 44, 26, 3))
    out.append(heart(cx + 34, gy - 122, 12, 3))
    out.append(P(f"M {cx-50} {gy-92} Q {cx-30} {gy-84} {cx-10} {gy-92}", 2.5))
    return "".join(out)


def desk(cx, gy, w=300):
    out = [P(f"M {cx-w/2} {gy-120} L {cx+w/2} {gy-120} L {cx+w/2} {gy-104} L {cx-w/2} {gy-104} Z", 4.5, "white")]
    out.append(LINE(cx - w / 2 + 16, gy - 104, cx - w / 2 + 16, gy, 4.5))
    out.append(LINE(cx + w / 2 - 16, gy - 104, cx + w / 2 - 16, gy, 4.5))
    # monitor
    out.append(rrect(cx - 60, gy - 210, 120, 84, 6, 4.5, "white"))
    out.append(P(f"M {cx-10} {gy-126} L {cx-6} {gy-108} L {cx+6} {gy-108} L {cx+10} {gy-126}", 3.5, "white"))
    out.append(P(f"M {cx-40} {gy-170} Q {cx-20} {gy-186} {cx-8} {gy-168} M {cx+6} {gy-158} L {cx+40} {gy-158}", 2.5))
    # keyboard + mug
    out.append(rrect(cx - 44, gy - 132, 88, 12, 3, 3, "white"))
    out.append(rrect(cx + 92, gy - 146, 26, 26, 4, 3.5, "white"))
    out.append(P(f"M {cx+118} {gy-140} Q {cx+130} {gy-138} {cx+118} {gy-128}", 3))
    return "".join(out)


def office_chair(cx, gy):
    return (rrect(cx - 26, gy - 118, 52, 60, 8, 4, "white") +
            rrect(cx - 30, gy - 64, 60, 12, 4, 4, "white") +
            LINE(cx, gy - 52, cx, gy - 22, 4) +
            P(f"M {cx-28} {gy} L {cx+28} {gy} M {cx} {gy-22} L {cx-22} {gy} M {cx} {gy-22} L {cx+22} {gy}", 3.5))


def sticky_notes(spots):
    out = []
    for x, y, r in spots:
        out.append(f'<rect x="{x}" y="{y}" width="26" height="26" rx="2" fill="white" stroke="black" stroke-width="3" transform="rotate({r} {x+13} {y+13})"/>')
        out.append(f'<line x1="{x+5}" y1="{y+10}" x2="{x+21}" y2="{y+10}" stroke="black" stroke-width="2" transform="rotate({r} {x+13} {y+13})"/>')
    return "".join(out)


def village_house(cx, gy, w=280):
    """Two-story New England clapboard village house with a front porch."""
    x0 = cx - w / 2
    out = [rrect(x0 + w * 0.05, gy - w * 0.62, w * 0.9, w * 0.62, 4, 5, "white")]
    out.append(P(f"M {x0} {gy-w*0.62} L {cx} {gy-w*0.95} L {x0+w} {gy-w*0.62} Z", 5, "white"))
    out.append(rrect(cx + w * 0.16, gy - w * 0.92, w * 0.09, w * 0.16, 2, 4, "white"))  # chimney
    # clapboard hints
    out.append(P(f"M {x0+w*0.08} {gy-w*0.34} L {x0+w*0.92} {gy-w*0.34}", 2.5))
    # upstairs windows
    for wx in (cx - w * 0.26, cx + w * 0.26):
        out.append(rrect(wx - 20, gy - w * 0.56, 40, 44, 3, 3.5, "white"))
        out.append(LINE(wx, gy - w * 0.56, wx, gy - w * 0.56 + 44, 2.5))
        out.append(LINE(wx - 20, gy - w * 0.56 + 22, wx + 20, gy - w * 0.56 + 22, 2.5))
    # porch: roof + posts + steps
    out.append(P(f"M {x0-6} {gy-w*0.30} L {x0+w+6} {gy-w*0.30} L {x0+w} {gy-w*0.24} L {x0} {gy-w*0.24} Z", 4, "white"))
    for px in (x0 + w * 0.08, x0 + w * 0.36, x0 + w * 0.64, x0 + w * 0.92):
        out.append(LINE(px, gy - w * 0.24, px, gy, 4))
    out.append(rrect(cx - w * 0.09, gy - w * 0.20, w * 0.18, w * 0.20, 3, 4, "white"))  # door
    out.append(DOT(cx + w * 0.05, gy - w * 0.10, 3.5))
    out.append(P(f"M {cx-w*0.15} {gy} L {cx+w*0.15} {gy} L {cx+w*0.12} {gy+14} L {cx-w*0.12} {gy+14} Z", 3.5, "white"))
    return "".join(out)


def dress_rack(cx, gy):
    """Wardrobe rack with three little dresses on hangers."""
    out = [LINE(cx - 110, gy - 200, cx + 110, gy - 200, 4.5),
           LINE(cx - 100, gy - 200, cx - 100, gy, 4.5), LINE(cx + 100, gy - 200, cx + 100, gy, 4.5),
           P(f"M {cx-112} {gy} L {cx-88} {gy} M {cx+88} {gy} L {cx+112} {gy}", 4)]
    for i, dx in enumerate((-60, 0, 60)):
        hx = cx + dx
        out.append(P(f"M {hx} {gy-200} L {hx} {gy-186}", 3))
        out.append(P(f"M {hx-16} {gy-172} Q {hx} {gy-182} {hx+16} {gy-172} L {hx+26} {gy-108} "
                     f"Q {hx} {gy-98} {hx-26} {gy-108} Z", 3.5, "white"))
        if i == 0:
            out.append(star(hx, gy - 138, 7, 2.5, "white"))
        elif i == 1:
            out.append(heart(hx, gy - 138, 6, 2.5))
        else:
            out.append(flower(hx, gy - 140, 0.6, 2.2))
    return "".join(out)


def castle_small(cx, gy, w=380):
    """Story Land fairy-tale castle, compact."""
    x0 = cx - w / 2
    out = []
    out.append(P(f"M {x0+w*0.18} {gy} L {x0+w*0.18} {gy-w*0.42} "
                 + "".join(f"L {x0+w*(0.18+i*0.08)} {gy-w*(0.42 if i%2 else 0.38)} " for i in range(1, 9))
                 + f"L {x0+w*0.82} {gy} Z", 5, "white"))
    for tx in (x0 + w * 0.12, x0 + w * 0.88):
        out.append(P(f"M {tx-w*0.09} {gy} L {tx-w*0.09} {gy-w*0.52} L {tx+w*0.09} {gy-w*0.52} L {tx+w*0.09} {gy} Z", 5, "white"))
        out.append(P(f"M {tx-w*0.12} {gy-w*0.52} L {tx} {gy-w*0.72} L {tx+w*0.12} {gy-w*0.52} Z", 5, "white"))
        out.append(LINE(tx, gy - w * 0.72, tx, gy - w * 0.80, 4))
        out.append(P(f"M {tx} {gy-w*0.80} L {tx+w*0.07} {gy-w*0.775} L {tx} {gy-w*0.75} Z", 3.5, "white"))
    out.append(P(f"M {cx-w*0.07} {gy} L {cx-w*0.07} {gy-w*0.20} Q {cx} {gy-w*0.28} {cx+w*0.07} {gy-w*0.20} L {cx+w*0.07} {gy} Z", 4))
    for wx in (cx - w * 0.22, cx + w * 0.22):
        out.append(P(f"M {wx-11} {gy-w*0.20} Q {wx-11} {gy-w*0.27} {wx} {gy-w*0.27} Q {wx+11} {gy-w*0.27} {wx+11} {gy-w*0.20} L {wx+11} {gy-w*0.12} L {wx-11} {gy-w*0.12} Z", 3.5))
    return "".join(out)


def pumpkin_coach(cx, gy, s=1.0):
    """Cinderella pumpkin coach with wheels."""
    out = []
    out.append(E(cx, gy - 62 * s, 58 * s, 50 * s, 5, "white"))
    for dx in (-30, 0, 30):
        out.append(P(f"M {cx+dx*s} {gy-108*s} Q {cx+dx*1.5*s} {gy-62*s} {cx+dx*s} {gy-16*s}", 3.5))
    out.append(P(f"M {cx-14*s} {gy-108*s} Q {cx} {gy-122*s} {cx+10*s} {gy-110*s} Q {cx+2*s} {gy-104*s} {cx-14*s} {gy-108*s} Z", 3.5, "white"))
    out.append(P(f"M {cx-16*s} {gy-78*s} Q {cx-16*s} {gy-92*s} {cx} {gy-92*s} Q {cx+16*s} {gy-92*s} {cx+16*s} {gy-78*s} L {cx+16*s} {gy-48*s} L {cx-16*s} {gy-48*s} Z", 3.5))
    out.append(C(cx - 40 * s, gy - 12 * s, 13 * s, 4, "white") + C(cx + 40 * s, gy - 12 * s, 13 * s, 4, "white"))
    return "".join(out)


def reindeer(cx, gy, s=1.0):
    """Friendly reindeer: horse-pattern body + antlers + round nose."""
    out = []
    out.append(E(cx, gy - 52 * s, 46 * s, 28 * s, 4.5, "white"))
    for lx in (-30, -12, 12, 30):
        out.append(LINE(cx + lx * s, gy - 26 * s, cx + lx * s, gy, 4.5))
        out.append(LINE(cx + (lx - 4) * s, gy, cx + (lx + 4) * s, gy, 4))
    out.append(P(f"M {cx+34*s} {gy-70*s} Q {cx+44*s} {gy-86*s} {cx+58*s} {gy-88*s} L {cx+60*s} {gy-74*s} Q {cx+48*s} {gy-64*s} {cx+38*s} {gy-58*s} Z", 4.5, "white"))
    out.append(C(cx + 62 * s, gy - 86 * s, 14 * s, 4.5, "white"))
    out.append(C(cx + 74 * s, gy - 82 * s, 5 * s, 3.5, "white"))   # round nose!
    out.append(DOT(cx + 60 * s, gy - 90 * s, 2.6))
    out.append(P(f"M {cx+52*s} {gy-98*s} L {cx+44*s} {gy-116*s} M {cx+48*s} {gy-108*s} L {cx+40*s} {gy-112*s} M {cx+44*s} {gy-116*s} L {cx+46*s} {gy-124*s}", 3.5))
    out.append(P(f"M {cx+62*s} {gy-98*s} L {cx+70*s} {gy-118*s} M {cx+66*s} {gy-108*s} L {cx+74*s} {gy-112*s} M {cx+70*s} {gy-118*s} L {cx+66*s} {gy-126*s}", 3.5))
    out.append(P(f"M {cx-44*s} {gy-62*s} Q {cx-54*s} {gy-70*s} {cx-50*s} {gy-78*s}", 3.5))
    return "".join(out)


def candy_cane(cx, gy, h=120, sw=5):
    out = [P(f"M {cx} {gy} L {cx} {gy-h+26} Q {cx} {gy-h} {cx+20} {gy-h} Q {cx+38} {gy-h} {cx+38} {gy-h+22}", sw, "white")]
    for i in range(5):
        y = gy - 14 - i * 20
        out.append(P(f"M {cx-7} {y} L {cx+7} {y-11}", 4.5))
    return "".join(out)


def ferris_wheel(cx, cy, r=110):
    out = [C(cx, cy, r, 4.5), C(cx, cy, 8, 4, "white")]
    import math as m
    for i in range(6):
        a = i * m.pi / 3
        gx, gy2 = cx + r * m.cos(a), cy + r * m.sin(a)
        out.append(LINE(cx, cy, gx, gy2, 3))
        out.append(P(f"M {gx-12} {gy2} Q {gx-12} {gy2+16} {gx} {gy2+16} Q {gx+12} {gy2+16} {gx+12} {gy2} Z", 3.5, "white"))
    out.append(LINE(cx - r * 0.55, cy + r + 42, cx, cy, 4.5))
    out.append(LINE(cx + r * 0.55, cy + r + 42, cx, cy, 4.5))
    return "".join(out)


def baby_goat():
    """Baby goat (ported from the family's first book), origin at feet."""
    out = []
    out.append(P("M -50 -38 Q -56 -66 -30 -70 L 26 -70 Q 52 -68 50 -42 Q 48 -22 26 -20 L -30 -20 Q -50 -22 -50 -38 Z", 4.5, "white"))
    for lx in (-38, -18, 12, 34):
        out.append(P(f"M {lx} -20 L {lx} 0", 4.5))
        out.append(P(f"M {lx-4} 0 L {lx+4} 0", 4))
    out.append(P("M 42 -66 Q 40 -92 60 -96 Q 84 -98 88 -80 Q 90 -66 76 -60 Q 60 -54 48 -58 Q 42 -60 42 -66 Z", 4.5, "white"))
    out.append(P("M 52 -92 Q 40 -104 32 -96 Q 40 -86 50 -88", 4, "white"))
    out.append(P("M 74 -96 L 70 -112 M 82 -94 L 84 -110", 4))
    out.append(DOT(76, -82, 3))
    out.append(P("M 86 -70 Q 92 -68 90 -62", 3.5))
    out.append(P("M 44 -58 Q 52 -50 60 -54", 3) + C(52, -47, 4, 2.5, "white"))
    out.append(P("M -50 -50 Q -62 -58 -58 -68", 4))
    return "".join(out)


def wooden_sign(cx, gy, text, w=170):
    out = [LINE(cx, gy, cx, gy - 96, 5)]
    out.append(P(f"M {cx-w/2} {gy-96} L {cx+w/2-24} {gy-96} L {cx+w/2} {gy-78} L {cx+w/2-24} {gy-60} L {cx-w/2} {gy-60} Z", 4.5, "white"))
    out.append(TXT(cx - 10, gy - 71, text, 21))
    return "".join(out)


def tent(cx, gy, w=210, sw=5):
    """Chunky A-frame tent, base on the ground line; door + pole flag + pegs."""
    x0 = cx - w / 2
    h = 0.82 * w
    ap = gy - h
    out = [P(f"M {x0} {gy} L {cx} {ap} L {x0+w} {gy} Z", sw, "white")]     # main triangle
    dw = w * 0.15
    # arched door
    out.append(P(f"M {cx-dw} {gy} L {cx-dw} {gy-h*0.48} "
                 f"Q {cx} {gy-h*0.60} {cx+dw} {gy-h*0.48} L {cx+dw} {gy}", sw))
    out.append(LINE(cx, gy - h * 0.55, cx, gy, 3.5))                       # center seam
    # a seam line up each roof slope
    out.append(LINE(cx - w * 0.24, gy, cx - w * 0.10, ap + h * 0.30, 2.5))
    out.append(LINE(cx + w * 0.24, gy, cx + w * 0.10, ap + h * 0.30, 2.5))
    # flag on a short pole at the apex
    out.append(LINE(cx, ap, cx, ap - 28, 4))
    out.append(P(f"M {cx} {ap-28} L {cx+24} {ap-20} L {cx} {ap-12} Z", 3.5, "white"))
    # ground pegs
    out.append(P(f"M {x0} {gy} L {x0-13} {gy+3}", 3.5) +
               P(f"M {x0+w} {gy} L {x0+w+13} {gy+3}", 3.5))
    return "".join(out)


def campfire(cx, gy, s=1.0, sw=5):
    """Fire ring (rocks) + two crossed logs + flame tongues. gy = ground line."""
    out = []
    rx = 78 * s
    # ring of rocks along a shallow front arc
    for i in range(6):
        t = i / 5.0
        sx = cx - rx + 2 * rx * t
        sy = gy - 2 * s + 9 * s * math.sin(math.pi * t)
        out.append(E(sx, sy, 14 * s, 9 * s, 3.5, "white"))
    # two crossed logs sitting in the ring
    for sgn in (-1, 1):
        g = (f'<g transform="rotate({sgn*20} {cx} {gy-8*s})">')
        g += rrect(cx - 48 * s, gy - 16 * s, 96 * s, 15 * s, 7, sw - 0.5, "white")
        g += C(cx + sgn * 42 * s, gy - 8.5 * s, 5.5 * s, 3, "white")       # end grain
        g += "</g>"
        out.append(g)

    def flame(fx, by, fw, fh):
        return P(f"M {fx} {by} "
                 f"C {fx-fw*0.6} {by-fh*0.35} {fx-fw*0.35} {by-fh*0.75} {fx} {by-fh} "
                 f"C {fx+fw*0.35} {by-fh*0.75} {fx+fw*0.6} {by-fh*0.35} {fx} {by} Z",
                 sw - 0.5, "white")
    fb = gy - 18 * s
    out.append(flame(cx, fb, 62 * s, 96 * s))
    out.append(flame(cx - 24 * s, fb, 36 * s, 56 * s))
    out.append(flame(cx + 24 * s, fb, 36 * s, 56 * s))
    out.append(flame(cx, fb - 8 * s, 30 * s, 50 * s))                     # inner flame
    return "".join(out)


def log_seat(cx, gy, w=130, s=1.0, sw=5):
    """A log to sit on: horizontal cylinder, end-grain rings at the left cap."""
    h = 30 * s
    out = [rrect(cx - w / 2, gy - h, w, h, h / 2, sw, "white")]
    out.append(E(cx - w / 2, gy - h / 2, 9 * s, h / 2, sw - 0.5, "white"))  # end cap
    out.append(C(cx - w / 2, gy - h / 2, 4 * s, 2.5, "white"))              # inner ring
    out.append(LINE(cx - w / 2 + 16, gy - h + 7, cx + w / 2 - 8, gy - h + 7, 2.5))
    return "".join(out)


def marsh_stick(x1, y1, x2, y2, s=1.0, sw=4):
    """Roasting stick from a hand (x1,y1) to a marshmallow at (x2,y2)."""
    return (LINE(x1, y1, x2, y2, sw) +
            rrect(x2 - 11 * s, y2 - 12 * s, 22 * s, 20 * s, 7, sw - 0.5, "white"))


def smore(cx, gy, s=1.0, sw=4):
    """Graham stack: graham, chocolate, marshmallow, graham."""
    w = 46 * s
    out = [rrect(cx - w / 2, gy - 12 * s, w, 12 * s, 3, sw, "white")]          # bottom graham
    out.append(rrect(cx - w / 2 + 3 * s, gy - 22 * s, w - 6 * s, 10 * s, 2, sw - 1.5, "white"))  # chocolate
    out.append(LINE(cx, gy - 22 * s, cx, gy - 12 * s, 2))                       # choc score
    out.append(P(f"M {cx-w/2+3*s} {gy-22*s} Q {cx-w/2+3*s} {gy-40*s} {cx} {gy-40*s} "
                 f"Q {cx+w/2-3*s} {gy-40*s} {cx+w/2-3*s} {gy-22*s} Z", sw - 0.5, "white"))  # marshmallow
    out.append(rrect(cx - w / 2 + 4 * s, gy - 52 * s, w - 8 * s, 12 * s, 3, sw, "white"))    # top graham
    out.append(DOT(cx - 9 * s, gy - 6 * s, 2) + DOT(cx + 9 * s, gy - 6 * s, 2))
    return "".join(out)


def pine_cone(cx, cy, s=1.0, sw=3):
    """Little pine cone: egg body with chevron scale rows."""
    out = [E(cx, cy, 10 * s, 14 * s, sw, "white")]
    for i in range(4):
        yy = cy - 8 * s + i * 6 * s
        ww = (9 - i * 1.1) * s
        out.append(P(f"M {cx-ww} {yy} L {cx} {yy+4*s} L {cx+ww} {yy}", 2))
    return "".join(out)


def mushroom(cx, gy, s=1.0, sw=4):
    """Toadstool: stem + domed spotted cap."""
    out = [rrect(cx - 7 * s, gy - 22 * s, 14 * s, 22 * s, 5, sw - 0.5, "white")]  # stem
    out.append(P(f"M {cx-22*s} {gy-20*s} Q {cx} {gy-44*s} {cx+22*s} {gy-20*s} "
                 f"Q {cx} {gy-27*s} {cx-22*s} {gy-20*s} Z", sw, "white"))         # cap
    out.append(DOT(cx - 9 * s, gy - 28 * s, 3) + DOT(cx + 8 * s, gy - 30 * s, 3) +
               DOT(cx + 1 * s, gy - 24 * s, 2.5))
    return "".join(out)


def basket(cx, gy, w=94, s=1.0, sw=5):
    """Woven basket (for pine cones): tapered body, rim, handle, weave lines."""
    tw, bw = w, w * 0.72
    out = [P(f"M {cx-tw/2} {gy-46*s} L {cx-bw/2} {gy} L {cx+bw/2} {gy} L {cx+tw/2} {gy-46*s} Z", sw, "white")]
    out.append(rrect(cx - tw / 2 - 4, gy - 54 * s, tw + 8, 10 * s, 4, sw - 0.5, "white"))   # rim
    for t in (0.3, 0.5, 0.7):
        out.append(LINE(cx - tw / 2 + tw * t, gy - 44 * s, cx - bw / 2 + bw * t, gy, 2.5))
    out.append(LINE(cx - tw * 0.42, gy - 30 * s, cx + tw * 0.42, gy - 30 * s, 2.5) +
               LINE(cx - tw * 0.36, gy - 15 * s, cx + tw * 0.36, gy - 15 * s, 2.5))
    out.append(P(f"M {cx-tw/2+6} {gy-54*s} Q {cx} {gy-96*s} {cx+tw/2-6} {gy-54*s}", sw - 1))  # handle
    return "".join(out)


def fairy_door(cx, gy, s=1.0, sw=4):
    """Tiny arched fairy door + round window, drawn on a tree trunk base."""
    dw, dh = 28 * s, 46 * s
    out = [P(f"M {cx-dw/2} {gy} L {cx-dw/2} {gy-dh*0.58} "
             f"Q {cx} {gy-dh} {cx+dw/2} {gy-dh*0.58} L {cx+dw/2} {gy} Z", sw, "white")]
    out.append(LINE(cx, gy, cx, gy - dh * 0.8, 2.5))                       # plank line
    out.append(DOT(cx + 8 * s, gy - dh * 0.32, 3))                         # knob
    out.append(C(cx, gy - dh - 15 * s, 9 * s, sw - 1, "white"))            # round window
    out.append(LINE(cx - 9 * s, gy - dh - 15 * s, cx + 9 * s, gy - dh - 15 * s, 2) +
               LINE(cx, gy - dh - 24 * s, cx, gy - dh - 6 * s, 2))
    return "".join(out)


def firefly(cx, cy, s=1.0):
    """Firefly: bright dot + glow ring + tiny sparkle."""
    return DOT(cx, cy, 3.5 * s) + C(cx, cy, 9 * s, 2.2, "none") + sparkle(cx, cy, 5 * s, 2)


def wardrobe(cx, gy, w=240, h=400, doors=True, sw=5):
    """Tall wardrobe cabinet with open double doors + a row of hanging coats."""
    x0 = cx - w / 2
    top = gy - h
    out = []
    # little feet
    out.append(LINE(x0 + 18, gy, x0 + 18, gy - 14, sw))
    out.append(LINE(x0 + w - 18, gy, x0 + w - 18, gy - 14, sw))
    # carcass
    out.append(rrect(x0, top, w, h - 14, 10, sw, "white"))
    # cornice on top
    out.append(rrect(x0 - 12, top - 22, w + 24, 24, 6, sw, "white"))
    # interior opening
    inx, iny = x0 + 22, top + 26
    inw, inh = w - 44, h - 14 - 52
    out.append(rrect(inx, iny, inw, inh, 6, 4, "white"))
    # hanging rod + three coats
    rody = iny + 18
    out.append(LINE(inx + 8, rody, inx + inw - 8, rody, 3))
    coat_h = inh - 44
    for dx in (0.24, 0.5, 0.76):
        hx = inx + inw * dx
        out.append(LINE(hx, rody - 7, hx, rody, 2.5))               # hanger stem
        out.append(P(f"M {hx-24} {rody+8} Q {hx} {rody-2} {hx+24} {rody+8} "
                     f"L {hx+29} {iny+coat_h} L {hx-29} {iny+coat_h} Z", 3.5, "white"))
        out.append(LINE(hx, rody + 6, hx, iny + coat_h, 2.5))       # coat seam
    if doors:
        dy = top + 24
        dh = h - 14 - 34
        # left door swung open (hinge at the cabinet, free edge out-left)
        out.append(P(f"M {x0} {dy} L {x0-48} {dy-10} L {x0-48} {dy+dh+10} L {x0} {dy+dh} Z", sw, "white"))
        out.append(rrect(x0 - 40, dy + 8, 30, dh - 16, 4, 3, "white"))   # panel inset
        out.append(DOT(x0 - 44, top + h / 2, 4))                          # knob
        # right door swung open
        out.append(P(f"M {x0+w} {dy} L {x0+w+48} {dy-10} L {x0+w+48} {dy+dh+10} L {x0+w} {dy+dh} Z", sw, "white"))
        out.append(rrect(x0 + w + 10, dy + 8, 30, dh - 16, 4, 3, "white"))
        out.append(DOT(x0 + w + 44, top + h / 2, 4))
    return "".join(out)


def lamppost(cx, gy, h=340, sw=5):
    """Iconic Narnia lamppost: base + fluted post + lantern box + glow ticks."""
    postop = gy - h
    out = []
    # base
    out.append(P(f"M {cx-24} {gy} L {cx+24} {gy} L {cx+14} {gy-22} L {cx-14} {gy-22} Z", sw, "white"))
    # fluted post (tall thin body + a centre flute line)
    out.append(rrect(cx - 9, postop, 18, gy - 22 - postop, 4, sw, "white"))
    out.append(LINE(cx, postop + 12, cx, gy - 32, 2.5))
    # knob under the lantern
    out.append(E(cx, postop, 16, 7, sw, "white"))
    # lantern box
    lw, lh = 30, 48
    lby = postop - 2
    lty = lby - lh
    out.append(P(f"M {cx-lw} {lby} L {cx+lw} {lby} L {cx+lw-7} {lty} L {cx-lw+7} {lty} Z", sw, "white"))
    # little roof + finial
    out.append(P(f"M {cx-lw+3} {lty} L {cx} {lty-26} L {cx+lw-3} {lty} Z", sw, "white"))
    out.append(DOT(cx, lty - 30, 3.5))
    # window panes
    out.append(LINE(cx, lby, cx, lty, 3))
    out.append(LINE(cx - lw * 0.6, (lby + lty) / 2, cx + lw * 0.6, (lby + lty) / 2, 3))
    # warm glow ticks (skip the straight-down one so it stays off the post)
    lcx, lcy = cx, (lby + lty) / 2
    for i in range(8):
        if i == 2:
            continue
        a = i * math.pi / 4
        out.append(LINE(lcx + (lw + 12) * math.cos(a), lcy + (lw + 12) * math.sin(a),
                        lcx + (lw + 26) * math.cos(a), lcy + (lw + 26) * math.sin(a), 3))
    return "".join(out)


def lion(cx, gy, s=1.0):
    """Aslan: a BIG warm friendly lion. Rounded body, sitting; a great mane of
    soft petal spikes around a gentle round face. Nothing fierce. Origin feet."""
    out = []
    # rounded body
    out.append(E(cx, gy - 72 * s, 92 * s, 68 * s, 5, "white"))
    # two front legs / paws
    for sx in (-1, 1):
        pxx = cx + sx * 46 * s
        out.append(P(f"M {pxx-16*s} {gy-72*s} L {pxx-16*s} {gy-6*s} Q {pxx-16*s} {gy} {pxx-8*s} {gy} "
                     f"L {pxx+8*s} {gy} Q {pxx+16*s} {gy} {pxx+16*s} {gy-6*s} L {pxx+16*s} {gy-64*s} Z", 5, "white"))
        out.append(LINE(pxx - 6 * s, gy - 8 * s, pxx - 6 * s, gy, 3) +
                   LINE(pxx + 6 * s, gy - 8 * s, pxx + 6 * s, gy, 3))
    # tail with soft tuft
    out.append(P(f"M {cx+86*s} {gy-84*s} Q {cx+132*s} {gy-74*s} {cx+120*s} {gy-22*s}", 4.5))
    out.append(P(f"M {cx+120*s} {gy-22*s} q {-11*s} {13*s} {-22*s} {2*s} q {13*s} {2*s} {9*s} {-16*s} Z", 4, "white"))
    # mane: soft petal spikes ringing the face
    fcx, fcy, fr = cx, gy - 182 * s, 46 * s
    mane_r = fr + 5 * s
    petals = 14
    for i in range(petals):
        a = i * 2 * math.pi / petals
        tx, ty = fcx + (mane_r + 27 * s) * math.cos(a), fcy + (mane_r + 27 * s) * math.sin(a)
        bx1, by1 = fcx + mane_r * math.cos(a + 0.30), fcy + mane_r * math.sin(a + 0.30)
        bx2, by2 = fcx + mane_r * math.cos(a - 0.30), fcy + mane_r * math.sin(a - 0.30)
        out.append(P(f"M {bx1:.1f} {by1:.1f} Q {tx:.1f} {ty:.1f} {bx2:.1f} {by2:.1f}", 4.5, "white"))
    # face circle caps the petal bases
    out.append(C(fcx, fcy, fr, 5, "white"))
    # ears peeking through the mane
    for sx in (-1, 1):
        out.append(C(fcx + sx * 33 * s, fcy - 30 * s, 11 * s, 4, "white"))
    # gentle face
    out.append(DOT(fcx - 16 * s, fcy - 4 * s, 3.5) + DOT(fcx + 16 * s, fcy - 4 * s, 3.5))
    out.append(E(fcx, fcy + 16 * s, 22 * s, 15 * s, 4, "white"))                   # muzzle
    out.append(P(f"M {fcx-7*s} {fcy+8*s} L {fcx+7*s} {fcy+8*s} L {fcx} {fcy+15*s} Z", 3.5, "black"))
    out.append(P(f"M {fcx} {fcy+15*s} Q {fcx-6*s} {fcy+24*s} {fcx-12*s} {fcy+22*s}", 3))
    out.append(P(f"M {fcx} {fcy+15*s} Q {fcx+6*s} {fcy+24*s} {fcx+12*s} {fcy+22*s}", 3))
    out.append(DOT(fcx - 15 * s, fcy + 16 * s, 2) + DOT(fcx + 15 * s, fcy + 16 * s, 2))  # whisker dots
    return "".join(out)


def snowman(cx, gy, s=1.0, sw=5):
    """Three-ball snowman: carrot nose, twig arms, top hat. Cheerful."""
    out = []
    rb, rm, rh = 46 * s, 34 * s, 24 * s
    yb = gy - rb
    ym = yb - rb - rm + 16 * s
    yh = ym - rm - rh + 14 * s
    out.append(C(cx, yb, rb, sw, "white"))
    out.append(C(cx, ym, rm, sw, "white"))
    out.append(C(cx, yh, rh, sw, "white"))
    # face
    out.append(DOT(cx - 8 * s, yh - 4 * s, 3) + DOT(cx + 8 * s, yh - 4 * s, 3))
    out.append(P(f"M {cx} {yh-1*s} L {cx+18*s} {yh+2*s} L {cx} {yh+5*s} Z", 3, "white"))   # carrot nose
    out.append(P(f"M {cx-9*s} {yh+9*s} Q {cx} {yh+15*s} {cx+9*s} {yh+9*s}", 2.5))          # smile
    # buttons
    out.append(DOT(cx, ym - 8 * s, 3) + DOT(cx, ym + 8 * s, 3) + DOT(cx, ym + 24 * s, 3))
    # twig arms
    out.append(P(f"M {cx-rm+4*s} {ym-2*s} L {cx-rm-28*s} {ym-16*s} "
                 f"M {cx-rm-14*s} {ym-9*s} L {cx-rm-20*s} {ym-26*s}", 3.5))
    out.append(P(f"M {cx+rm-4*s} {ym-2*s} L {cx+rm+28*s} {ym-16*s} "
                 f"M {cx+rm+14*s} {ym-9*s} L {cx+rm+20*s} {ym-26*s}", 3.5))
    # top hat
    out.append(rrect(cx - rh, yh - rh - 4 * s, 2 * rh, 8 * s, 2, sw, "white"))            # brim
    out.append(rrect(cx - rh * 0.62, yh - rh - 30 * s, rh * 1.24, 28 * s, 3, sw, "white"))  # crown
    return "".join(out)


def snowflake(cx, cy, r=16, sw=3):
    """Six-arm snowflake sparkle with little branch ticks."""
    out = []
    for i in range(6):
        a = i * math.pi / 3
        x2, y2 = cx + r * math.cos(a), cy + r * math.sin(a)
        out.append(LINE(cx, cy, x2, y2, sw))
        bx, by = cx + r * 0.6 * math.cos(a), cy + r * 0.6 * math.sin(a)
        for da in (-0.6, 0.6):
            out.append(LINE(bx, by, bx + r * 0.32 * math.cos(a + da),
                            by + r * 0.32 * math.sin(a + da), max(2, sw - 0.5)))
    return "".join(out)


def teapot(cx, gy, s=1.0, sw=4):
    """Cozy round teapot with spout, handle, lid, and a little steam curl."""
    out = []
    by = gy - 30 * s
    out.append(E(cx, by, 40 * s, 30 * s, sw, "white"))
    out.append(LINE(cx - 30 * s, gy - 2 * s, cx + 30 * s, gy - 2 * s, sw))       # flat base
    # spout (left)
    out.append(P(f"M {cx-34*s} {by-6*s} Q {cx-58*s} {by-8*s} {cx-62*s} {by-30*s} "
                 f"Q {cx-52*s} {by-24*s} {cx-46*s} {by-24*s} Q {cx-40*s} {by-10*s} {cx-30*s} {by-12*s} Z", sw, "white"))
    # handle (right)
    out.append(P(f"M {cx+34*s} {by-10*s} Q {cx+60*s} {by-14*s} {cx+56*s} {by+10*s} "
                 f"Q {cx+52*s} {by+18*s} {cx+38*s} {by+16*s}", sw))
    # lid + knob
    out.append(P(f"M {cx-22*s} {by-26*s} Q {cx} {by-40*s} {cx+22*s} {by-26*s}", sw, "white"))
    out.append(C(cx, by - 40 * s, 6 * s, sw, "white"))
    # steam
    out.append(P(f"M {cx-4*s} {by-48*s} q {9*s} {-9*s} {0} {-18*s} q {-9*s} {-9*s} {0} {-18*s}", 2.5))
    return "".join(out)


def treehouse(cx, g, h=440, ladder=True):
    """Tree house ON branches BELOW a defined leaf canopy: trunk forks into two
    main branches that carry the platform; the canopy sits above the roof as a
    lobed leaf mass with scallops + inner leaf marks. Base tangent to ground g."""
    u = h / 440.0
    out = []
    # trunk up to the fork
    out.append(rrect(cx - 26 * u, g - 310 * u, 52 * u, 310 * u, 10, 5, "white"))
    out.append(P(f"M {cx - 8 * u} {g - 260 * u} Q {cx} {g - 200 * u} {cx + 6 * u} {g - 140 * u}", 3))  # bark
    # two main branches forking out to carry the platform
    out.append(P(f"M {cx - 20 * u} {g - 300 * u} Q {cx - 70 * u} {g - 330 * u} {cx - 98 * u} {g - 366 * u}", 5))
    out.append(P(f"M {cx + 20 * u} {g - 300 * u} Q {cx + 70 * u} {g - 330 * u} {cx + 98 * u} {g - 366 * u}", 5))
    out.append(P(f"M {cx - 62 * u} {g - 326 * u} Q {cx - 80 * u} {g - 342 * u} {cx - 76 * u} {g - 358 * u}", 3.5))
    out.append(P(f"M {cx + 62 * u} {g - 326 * u} Q {cx + 80 * u} {g - 342 * u} {cx + 76 * u} {g - 358 * u}", 3.5))
    # platform plank resting on the branches
    out.append(rrect(cx - 112 * u, g - 376 * u, 224 * u, 14 * u, 4, 5, "white"))
    # house box on the platform, BELOW the leaves
    out.append(rrect(cx - 80 * u, g - 478 * u, 160 * u, 102 * u, 6, 5, "white"))
    # roof
    out.append(P(f"M {cx - 96 * u} {g - 478 * u} L {cx} {g - 544 * u} "
                 f"L {cx + 96 * u} {g - 478 * u} Z", 5, "white"))
    # round window with cross + door
    wx, wy = cx + 40 * u, g - 430 * u
    out.append(C(wx, wy, 20 * u, 4.5, "white"))
    out.append(LINE(wx - 20 * u, wy, wx + 20 * u, wy, 3) + LINE(wx, wy - 20 * u, wx, wy + 20 * u, 3))
    out.append(rrect(cx - 58 * u, g - 434 * u, 44 * u, 58 * u, 6, 4.5, "white"))
    out.append(DOT(cx - 22 * u, g - 404 * u, 3.5))
    # canopy ABOVE the roof: full five-lobe leaf mass (wide base, domed top)
    out.append(C(cx - 96 * u, g - 548 * u, 64 * u, 5, "white"))
    out.append(C(cx + 96 * u, g - 548 * u, 64 * u, 5, "white"))
    out.append(C(cx - 54 * u, g - 636 * u, 58 * u, 5, "white"))
    out.append(C(cx + 54 * u, g - 636 * u, 58 * u, 5, "white"))
    out.append(C(cx, g - 598 * u, 92 * u, 5, "white"))
    # leaf scallops along the outer rim of the whole canopy
    for sx, sy in [(-140, 570), (-118, 634), (-72, 682), (-16, 700), (44, 696),
                   (98, 664), (138, 606), (150, 548)]:
        out.append(P(f"M {cx + (sx - 11) * u} {g - sy * u} Q {cx + sx * u} {g - (sy + 14) * u} "
                     f"{cx + (sx + 11) * u} {g - sy * u}", 3))
    # asymmetric inner leaf marks (paired marks at equal height read as eyes)
    for lx, ly in [(-62, 566), (28, 545), (-12, 612), (64, 592), (-46, 648),
                   (36, 660), (2, 558), (-88, 540)]:
        out.append(P(f"M {cx + (lx - 8) * u} {g - ly * u} Q {cx + lx * u} {g - (ly + 11) * u} "
                     f"{cx + (lx + 8) * u} {g - ly * u}", 2.5))
    if ladder:
        # rope ladder hangs BESIDE the trunk (rails over the trunk crowd it out)
        lx1, lx2 = cx + 36 * u, cx + 78 * u
        top, bot = g - 362 * u, g - 30 * u
        out.append(LINE(lx1, top, lx1, bot, 4.5))
        out.append(LINE(lx2, top, lx2, bot, 4.5))
        for i in range(7):
            ry = top + (bot - top) * (i + 0.5) / 7
            out.append(LINE(lx1, ry, lx2, ry, 4))
    return "".join(out)


def open_book(cx, cy, s=1.0, mermaid=True):
    """Open book: back cover + two page arcs + spine, with a tiny mermaid + sparkle."""
    out = []
    out.append(P(f"M {cx - 96 * s} {cy + 2 * s} Q {cx} {cy + 24 * s} {cx + 96 * s} {cy + 2 * s} "
                 f"L {cx + 96 * s} {cy + 52 * s} Q {cx} {cy + 74 * s} {cx - 96 * s} {cy + 52 * s} Z", 5, "white"))
    out.append(P(f"M {cx} {cy} Q {cx - 48 * s} {cy - 14 * s} {cx - 86 * s} {cy - 2 * s} "
                 f"L {cx - 86 * s} {cy + 42 * s} Q {cx - 48 * s} {cy + 30 * s} {cx} {cy + 44 * s} Z", 4, "white"))
    out.append(P(f"M {cx} {cy} Q {cx + 48 * s} {cy - 14 * s} {cx + 86 * s} {cy - 2 * s} "
                 f"L {cx + 86 * s} {cy + 42 * s} Q {cx + 48 * s} {cy + 30 * s} {cx} {cy + 44 * s} Z", 4, "white"))
    out.append(LINE(cx, cy, cx, cy + 44 * s, 3.5))
    out.append(P(f"M {cx - 74 * s} {cy + 6 * s} Q {cx - 42 * s} {cy - 2 * s} {cx - 12 * s} {cy + 8 * s}", 2.5))
    if mermaid:
        out.append(tiny_mermaid(cx + 46 * s, cy + 18 * s, 0.95 * s))
        out.append(sparkle(cx + 74 * s, cy - 2 * s, 6) + star(cx - 44 * s, cy + 24 * s, 6, 2.5, "white"))
    return "".join(out)


def tiny_mermaid(cx, cy, s=1.0):
    """Very small mermaid drawn ON a book page: round head + a curl of tail."""
    out = [C(cx, cy - 14 * s, 6 * s, 2.5, "white"),
           DOT(cx - 2 * s, cy - 15 * s, 1.4 * s) + DOT(cx + 2 * s, cy - 15 * s, 1.4 * s)]
    out.append(P(f"M {cx - 5 * s} {cy - 8 * s} Q {cx - 3 * s} {cy + 8 * s} {cx - 9 * s} {cy + 16 * s} "
                 f"Q {cx} {cy + 11 * s} {cx + 9 * s} {cy + 16 * s} "
                 f"Q {cx + 3 * s} {cy + 2 * s} {cx + 5 * s} {cy - 8 * s} Z", 2.5, "white"))
    return "".join(out)


def wind_swirl(cx, cy, s=1.0, turns=2.4):
    """Spiral path of wind."""
    pts = []
    steps = 40
    for i in range(steps + 1):
        t = i / steps
        ang = t * turns * 2 * math.pi
        r = 8 * s + t * 46 * s
        pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    d = f"M {pts[0][0]:.1f} {pts[0][1]:.1f} " + " ".join(f"L {x:.1f} {y:.1f}" for x, y in pts[1:])
    return P(d, 4)


def pearl_shell(cx, cy, s=1.0):
    """Open scallop shell cradling a pearl."""
    hinge_y = cy + 10 * s
    d = (f"M {cx} {hinge_y} L {cx - 48 * s} {cy - 18 * s} "
         f"Q {cx - 40 * s} {cy - 40 * s} {cx - 24 * s} {cy - 32 * s} "
         f"Q {cx - 12 * s} {cy - 48 * s} {cx} {cy - 38 * s} "
         f"Q {cx + 12 * s} {cy - 48 * s} {cx + 24 * s} {cy - 32 * s} "
         f"Q {cx + 40 * s} {cy - 40 * s} {cx + 48 * s} {cy - 18 * s} L {cx} {hinge_y} Z")
    out = [P(d, 4, "white")]
    for dx in (-32, -16, 0, 16, 32):
        out.append(LINE(cx, hinge_y, cx + dx * s, cy - 30 * s, 2.5))
    out.append(C(cx, cy - 12 * s, 10 * s, 3.5, "white"))    # pearl
    out.append(C(cx - 3 * s, cy - 15 * s, 2.6 * s, 2, "white"))  # shine
    return "".join(out)


def small_shell(cx, cy, s=1.0):
    """Tiny fan clam on the seabed."""
    return (P(f"M {cx - 16 * s} {cy} Q {cx} {cy - 22 * s} {cx + 16 * s} {cy} Z", 3.5, "white") +
            LINE(cx - 7 * s, cy - 12 * s, cx - 7 * s, cy, 3) +
            LINE(cx + 7 * s, cy - 12 * s, cx + 7 * s, cy, 3) +
            LINE(cx, cy - 15 * s, cx, cy, 3))


def waves(y, x0=60, x1=790, amp=14):
    """Wavy sea-surface line + a couple of ripple marks below it."""
    span = x1 - x0
    d = f"M {x0} {y} "
    n = 8
    for i in range(n):
        xa = x0 + span * (i + 0.5) / n
        xb = x0 + span * (i + 1) / n
        yy = y - amp if i % 2 == 0 else y + amp
        d += f"Q {xa:.0f} {yy:.0f} {xb:.0f} {y} "
    return P(d, 5)


def closed_book(cx, cy, s=1.0):
    """Closed mermaid book lying flat-ish: cover + spine + a shell/star on front."""
    out = [rrect(cx - 60 * s, cy - 44 * s, 120 * s, 88 * s, 6, 5, "white")]
    out.append(LINE(cx - 52 * s, cy - 44 * s, cx - 52 * s, cy + 44 * s, 3.5))  # spine strip
    out.append(mermaid_tail_icon() and G(cx + 14 * s, cy - 26 * s, mermaid_tail_icon(), 0.34 * s))
    out.append(star(cx - 22 * s, cy - 10 * s, 10 * s, 3, "white"))
    out.append(sparkle(cx + 40 * s, cy + 24 * s, 7))
    return "".join(out)


def leaf(cx, cy, ang=0, s=1.0):
    return G(cx, cy, P("M 0 0 Q 12 -10 24 0 Q 12 10 0 0 Z", 3, "white") + LINE(4, 0, 20, 0, 2), s, ang)
