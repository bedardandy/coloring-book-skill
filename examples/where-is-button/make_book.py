#!/usr/bin/env python3
"""Harper family story-mode coloring book — "Where Is Button?"

11 pages, ages 3-6, story arc: Button the teddy goes missing -> the family
searches the house -> the reader draws where Button might be hiding ->
Biscuit finds him -> celebrate -> bedtime.

Characters are PARAMETRIC trait vectors (charlib), never photo-likeness.
Every scene page follows the three-layer composition recipe from
reference/drawing-guide.md:
  BACKGROUND  wall/floor line, window with curtains, wall art
  MIDGROUND   furniture scaled to the kids, tops reaching y~450-550
  FOREGROUND  kids at ~1.4x (main figure ~300-350px tall) and Biscuit,
              standing a step in front of the wall line, matted()
Partial rebuild:  python make_book.py 05      (substring filter on page name)
"""
import os
import sys

SKILL_LIB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "lib")
sys.path.insert(0, SKILL_LIB)
from charlib import *          # primitives, motifs, figures, furniture, letters, creativity, build

OUTDIR = os.path.dirname(os.path.abspath(__file__))
FLOOR = 890                    # wall/floor line: furniture stands here
FEET = 935                     # kids + Biscuit stand a step in front of it

# ---------------------------------------------------------------- cast traits
MAX    = {"name": "Max",  "age": 6, "hair": "buzz",      "glasses": False,
          "freckles": False, "height": 1.05, "outfit": "tee"}
LILY   = {"name": "Lily", "age": 4, "hair": "bob_bangs", "glasses": False,
          "freckles": False, "height": 0.82, "outfit": "dress"}
BISCUIT = {"coat": "plain", "floppy_ears": True, "collar": True}

FG = 1.43                      # foreground scale (drawing-guide: 1.2-1.4+)
MAX_S, LILY_S = FG * MAX["height"], FG * LILY["height"]   # ~1.50 / ~1.17
DOG_S = 1.25


# ---------------------------------------------------------------- helpers
# Furniture comes from charlib (bed, bookshelf, couch, armchair, floor_lamp,
# toybox, window, wall_picture, wall_clock, rug, wardrobe). The library draws
# it at doll size next to 1.0 kids, so place() scales it up to match the
# ~1.4x cast while restroke() keeps every line at the page's stroke weight.
# The local helpers below are objects charlib has no helper for.
def place(frag, x, y, k):
    """Place a fragment drawn around its own ground origin at (x, y), scaled
    by k with page-weight strokes."""
    return G(x, y, restroke(frag, k), k)


def mattress_top(k):
    """y of the mattress top of a charlib bed() placed on FLOOR at scale k
    (24px legs + 34px mattress at scale 1)."""
    return FLOOR - 58 * k


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


def wall_line():
    return ground_line(FLOOR, 44, W - 44, sw=5)


def curtained_window(x, y, w=190, h=170):
    """charlib window() plus two tied-back drapes hanging below the rod."""
    out = [window(x, y, w, h)]
    for side in (-1, 1):
        # drape drawn for the LEFT side, mirrored about the window centre
        def px(v):
            return x + v if side < 0 else x + w - v
        tie = y + h * 0.60
        pts = [(px(-18), y - 4), (px(30), y - 4), (px(14), tie - 30),
               (px(4), tie), (px(24), y + h + 34), (px(-22), y + h + 34),
               (px(-24), tie)]
        out.append(smooth_path(pts, 4.5, "white", closed=True))
        out.append(LINE(px(4), y + 4, px(-4), tie - 12, 3))                  # fold
        out.append(rrect(min(px(-26), px(8)), tie - 7, 34, 14, 6, 3.5, "white"))  # tie-back
    return "".join(out)


def door(x, floor=FLOOR, w=150, h=420):
    """Interior door on the wall line: trim, two panels, round knob."""
    top = floor - h
    return (rrect(x - 12, top - 12, w + 24, h + 12, 6, 5, "white") +      # trim
            rrect(x, top, w, h, 4, 4.5, "white") +
            rrect(x + 20, top + 24, w - 40, h * 0.36, 6, 3, "white") +
            rrect(x + 20, top + h * 0.50, w - 40, h * 0.40, 6, 3, "white") +
            C(x + w - 22, top + h * 0.46, 9, 4, "white"))


def coat_rack(x, floor=FLOOR, h=430):
    """Standing coat rack: tripod feet, post, knob, hooks, one jacket."""
    top = floor - h
    out = [P(f"M {x-44} {floor} L {x} {floor-40} L {x+44} {floor}", 5),
           rrect(x - 7, top, 14, h - 30, 5, 4.5, "white"),
           C(x, top - 8, 12, 4.5, "white")]
    for sx in (-1, 1):
        out.append(P(f"M {x} {top+34} Q {x+sx*30} {top+30} {x+sx*34} {top+14}", 4))
    # a jacket hanging from the right hook
    jx, jy = x + 34, top + 18
    out.append(P(f"M {jx-22} {jy+14} Q {jx} {jy} {jx+22} {jy+14} L {jx+34} {jy+150} "
                 f"L {jx-34} {jy+150} Z", 4.5, "white"))
    out.append(LINE(jx, jy + 12, jx, jy + 150, 3))
    out.append(DOT(jx - 8, jy + 100, 3.5) + DOT(jx - 8, jy + 130, 3.5))
    return "".join(out)


def bunting(x0, x1, y, n=9, sag=30):
    """Party flag garland sagging between two tacks."""
    out = [P(f"M {x0} {y} Q {(x0+x1)/2} {y+2*sag} {x1} {y}", 3.5),
           C(x0, y, 5, 3, "white"), C(x1, y, 5, 3, "white")]
    for i in range(n):
        t = (i + 0.5) / n
        fx = x0 + (x1 - x0) * t
        fy = y + 2 * sag * 2 * t * (1 - t)        # on the quadratic sag
        out.append(P(f"M {fx-18} {fy} L {fx+18} {fy} L {fx} {fy+36} Z", 3.5, "white"))
    return "".join(out)


def soft_blanket(cx, gy, w=170):
    """Crumpled blanket heap (base on gy): soft lumpy outline + stitched hem."""
    h = 0.34 * w
    pts = [(cx - w/2, gy), (cx - w*0.46, gy - h*0.55), (cx - w*0.2, gy - h),
           (cx + w*0.12, gy - h*0.78), (cx + w*0.4, gy - h*0.9), (cx + w/2, gy - h*0.3),
           (cx + w*0.46, gy)]
    return (smooth_path(pts, 4.5, "white", closed=True) +
            stitch_dash(cx - w*0.36, gy - 18, cx + w*0.34, gy - 18, sw=3) +
            P(f"M {cx-w*0.2} {gy-h*0.95} Q {cx-w*0.1} {gy-h*0.5} {cx} {gy-h*0.2}", 3))


def open_toybox(x, gy, k=1.3):
    """charlib toybox with its lid swung up behind it and toys peeking over
    the rim (lid + toys draw first, so the box front covers their bottoms)."""
    w, h = 124, 92
    top = gy - h * k
    lid = rrect(x + 4, top - 52, w * k - 8, 56, 8, 4.5, "white")
    toys = (soccer_ball(x + 44 * k, top - 10, 22) +
            rrect(x + 76 * k, top - 36, 36, 40, 4, 3.5, "white") +
            star(x + 76 * k + 18, top - 16, 9, 3, "white"))
    return lid + toys + place(toybox(0, 0, w=w, h=h), x, gy, k)


def flashlight(x, y, rot=-40):
    """Chunky flashlight whose lens end points along +y before rotation."""
    return G(x, y, rrect(-9, -30, 18, 40, 5, 4, "white") +
             rrect(-14, 8, 28, 16, 5, 4, "white") + LINE(-9, -14, 9, -14, 3), 1.0, rot)


# ---------------------------------------------------------------- pages
def cover():
    b = []
    gy, feet = 905, 932              # house/tree ground line; cast a step in front
    b.append(TXT(W / 2, 172, "A Harper Family Story", 30, weight="normal"))
    # sky: sun corner + clouds + Lily's butterflies, clear of the roof line
    b.append(sun(140, 285, 40) + cloud(655, 255, 28) + cloud(350, 232, 20))
    b.append(butterfly(710, 410, 1.7) + butterfly(105, 470, 1.5))
    # midground: the Harper house + a big garden tree behind it
    b.append(ground_line(gy, 44, W - 44, 5))
    b.append(tree_round(652, gy, h=380))
    b.append(house(410, gy + 2, w=450))
    b.append(grass_tuft(95, gy - 2))
    # foreground cast
    b.append(matted(G(200, feet, kid_stand(MAX, pose="wave"), MAX_S)))
    b.append(matted(G(425, feet, kid_stand(LILY, pose="hold"), LILY_S) +
                    hold_teddy(425, feet, LILY_S)))    # Button at chest, below chin
    b.append(matted(G(645, feet, dog(BISCUIT), DOG_S)))
    b.append(matted(soccer_ball(300, feet - 24, 24)))  # Max's ball
    # colorable name ribbon (glyph-metric sized: can't overflow)
    b.append(banner("Max \u2022 Lily \u2022 Biscuit \u2022 Button", 973, size=32))
    return spage("Where Is Button?", "".join(b), title_size=54)


def names():
    svg = name_trace_page(
        ["Max", "Lily"], num=2,
        caption="Trace the letters. M-A-X spells Max. L-I-L-Y spells Lily. "
                "Color a dinosaur for Max and a butterfly for Lily!")
    # name_trace_page() returns a whole page; add each name's motif inside
    # its activity group (Max's above his row, Lily's below hers)
    motifs = (dino(215, 345, 1.3) + soccer_ball(650, 300, 32) +
              butterfly(200, 930, 2.1) + butterfly(650, 930, 2.1) +
              heart(425, 930, 24, 4))
    tag = '<g data-layout="activity">'
    return svg.replace(tag, tag + motifs, 1)


def intro():
    b = []
    b.append(wall_line())
    b.append(curtained_window(100, 300, 190, 170))
    b.append(wall_picture(360, 330, 110, 90, "heart"))
    b.append(place(bookshelf(0, 0), 636, FLOOR, 1.45))
    b.append(rug(474, 942, 230, 20))
    b.append(place(bed(0, 0, w=170), 82, FLOOR, 1.35))
    b.append(teddy(215, mattress_top(1.35), 0.8))       # Button sits on the bed
    # cast
    b.append(matted(G(400, FEET, kid_stand(MAX, pose="wave"), MAX_S)))
    b.append(matted(G(548, FEET, kid_stand(LILY, pose="down"), LILY_S)))
    b.append(matted(G(716, FEET, dog_sit(BISCUIT), 1.2)))
    # name labels help parents read the cast
    for x, nm in ((400, "Max"), (548, "Lily"), (716, "Biscuit"), (215, "Button")):
        b.append(TXT(x, 990 if nm != "Button" else 640, nm, 22, weight="normal"))
    return spage("Meet the Harpers", "".join(b), num=3,
                 caption="This is Max. This is Lily. This is Biscuit the dog. Max and "
                         "Lily love their teddy bear Button, who goes everywhere with them.")


def problem():
    b = []
    b.append(wall_line())
    b.append(wardrobe(145, FLOOR, w=180, h=430, doors=False))
    b.append(wall_clock(372, 330, 36))
    b.append(curtained_window(575, 290, 170, 150))
    b.append(place(bed(0, 0, w=190), 515, FLOOR, 1.35))       # the EMPTY bed
    # a big colorable question mark over the empty pillow
    b.append(word("?", 592, 690, size=190))
    b.append(sparkle(515, 560, 12) + sparkle(680, 610, 12) + sparkle(715, 515, 9))
    # Lily points at the empty bed, Max wonders, Biscuit checks the wardrobe
    b.append(matted(GM(165, FEET, dog_sit(BISCUIT), 1.1)))      # sniffs the wardrobe
    b.append(matted(G(305, FEET, kid_stand(MAX, pose="down"), MAX_S)))
    b.append(matted(G(478, FEET, kid_point(LILY), LILY_S)))
    return spage("Where Is Button?", "".join(b), num=4,
                 caption="Oh no! Button is not on the bed. Where is Button? Max and Lily "
                         "and Biscuit look everywhere. Come and help Max and Lily search!")


def search_bedroom():
    b = []
    b.append(wall_line())
    b.append(curtained_window(84, 290, 170, 150))
    b.append(wall_picture(340, 330, 110, 90, "star"))
    b.append(place(bookshelf(0, 0), 645, FLOOR, 1.4))
    b.append(GM(765, FLOOR, restroke(bed(0, 0, w=210), 1.35), 1.35))   # headboard right
    # the flashlight's pool of light under the bed (a dashed ellipse)
    b.append(E(575, 877, 46, 9, 3).replace("/>", ' stroke-dasharray="7 6"/>'))
    b.append(sparkle(575, 870, 7))
    # Biscuit hops onto the bed and sniffs the soft blanket
    top = mattress_top(1.35)
    b.append(soft_blanket(560, top + 2, 120))
    b.append(matted(GM(705, top, dog(BISCUIT), 0.95)))
    b.append(P("M 610 718 Q 602 726 610 734", 3) + P("M 598 712 Q 587 726 598 740", 3))
    # Lily peeks into the open toy box
    b.append(open_toybox(58, FEET + 8, 1.25))
    b.append(matted(GM(300, FEET, kid_reach(LILY), LILY_S)))
    # Max shines a flashlight under the bed
    mx = 420
    hx, hy = mx + 40 * MAX_S, FEET - 103 * MAX_S          # between the hold_r wrists
    b.append(matted(G(mx, FEET, kid_stand(MAX, pose="hold_r"), MAX_S) +
                    flashlight(hx + 4, hy + 8, -40)))
    return spage("Look in the Bedroom", "".join(b), num=5,
                 caption="Max looks under the bed. Lily peeks in the toy box. Biscuit "
                         "sniffs the soft blanket. Button is not here! Max and Lily keep looking.")


def search_living():
    b = []
    b.append(wall_line())
    b.append(curtained_window(100, 280, 180, 150))
    b.append(wall_clock(430, 400, 40))
    b.append(wall_picture(555, 430, 165, 120, "sun"))
    b.append(floor_lamp(772, FLOOR, h=420))
    b.append(rug(415, 952, 175, 20))
    b.append(place(armchair(0, 0, w=120), 76, FLOOR, 1.55))       # the BIG chair
    b.append(place(couch(0, 0, w=180), 520, FLOOR, 1.3))
    # Lily reaches LEFT behind the big chair; Max lifts a couch cushion
    b.append(matted(GM(335, FEET, kid_reach(LILY), LILY_S)))
    mx = 490
    puff = [(-50, -24), (0, -30), (50, -24), (57, 0), (50, 24), (0, 30),
            (-50, 24), (-57, 0)]                                   # plump pillow
    cushion = G(mx + 118, FEET - 172, smooth_path(puff, 4.5, "white", closed=True) +
                DOT(12, 2, 5), 1.0, -14)
    # cushion first, so both hands visibly grip its near end
    b.append(matted(cushion + G(mx, FEET, kid_reach(MAX), MAX_S)))
    # Biscuit sniffs along the couch
    b.append(matted(GM(705, FEET, dog(BISCUIT), 1.1)))
    return spage("Look in the Living Room", "".join(b), num=6,
                 caption="Now Max and Lily look in the living room. Lily checks behind the "
                         "big chair. Max lifts the couch cushions. Where is Button hiding?")


# the four loose butterflies of the find-5 page (the fifth is framed on the
# wall): (x, y, scale, matted) — the one resting on the jacket gets a mat
FIND_BUTTERFLIES = ((615, 330, 1.9, False), (470, 480, 1.8, False),
                    (730, 765, 1.5, False), (152, 526, 1.4, True))


def find_activity():
    b = []
    b.append(wall_line())
    b.append(TXT(W / 2, 196, "Find 5 butterflies!", 28, weight="normal"))
    b.append("".join(C(W / 2 + 46 * (i - 2), 236, 13, 3.5, "white")    # color one
                     for i in range(5)))                                # per find
    b.append(door(665, FLOOR, 130, 430))
    b.append(coat_rack(110, FLOOR, 430))
    b.append(wall_picture(260, 300, 150, 110, "butterfly"))        # butterfly 1
    b.append(rrect(80, 946, 690, 32, 14, 4, "white"))              # hallway runner
    b.append(stitch_dash(100, 962, 750, 962, sw=3))
    for x, y, s, mat in FIND_BUTTERFLIES:                           # butterflies 2-5
        b.append(matted(butterfly(x, y, s)) if mat else butterfly(x, y, s))
    # Biscuit leads with his nose toward the door; the kids follow
    b.append(matted(G(178, FEET, kid_stand(LILY, pose="wave"), LILY_S)))
    b.append(matted(G(355, FEET, kid_point(MAX), MAX_S)))
    b.append(matted(G(520, FEET, dog(BISCUIT), 1.3)))
    for i, r in enumerate((10, 16, 22)):                            # sniff arcs
        sx = 648 + i * 11
        b.append(P(f"M {sx} {FEET-128-r} Q {sx+r*0.8} {FEET-128} {sx} {FEET-128+r}", 3))
    return spage("Follow Biscuit!", "".join(b), num=7,
                 caption="Max and Lily and Biscuit look everywhere! Biscuit points his nose "
                         "down the hallway. Can you find five butterflies to color?")


def draw_hiding_spot():
    """Creativity beat (layout="creative"): the reader decides where Button
    hides. Button sits in a big blank thought cloud; the child draws the
    hiding place around him."""
    b = []
    b.append(wall_line())
    lily = G(430, FEET, kid_stand(LILY, pose="down"), LILY_S)
    b.append(matted(G(250, FEET, kid_stand(MAX, pose="down"), MAX_S)))
    b.append(matted(lily))
    b.append(matted(GM(640, FEET, dog_sit(BISCUIT), 1.2)))
    # speaker_top = Lily's MEASURED head top; the cloud rises above her
    lily_top = fragment_bbox(lily, stroke=False)[1]
    bubble = thought_bubble(speaker_top=(430, lily_top), w=600, side=1)
    b.append(bubble)
    x0, _y0, x1, _y1 = fragment_bbox(bubble)
    # Button sits on the cloud's flat base (80px above the head top), waiting
    b.append(teddy((x0 + x1) / 2, lily_top - 100, 0.8))
    return spage("Where Would YOU Hide Button?", "".join(b), num=8, layout="creative",
                 caption="Max and Lily think and think. Where would YOU hide Button? "
                         "Draw a hiding spot for Button in the big cloud!")


def solve():
    b = []
    b.append(wall_line())
    b.append(curtained_window(90, 290, 170, 150))
    b.append(wall_picture(360, 320, 110, 90, "heart"))
    b.append(place(bookshelf(0, 0), 645, FLOOR, 1.4))
    b.append(place(bed(0, 0, w=180), 90, FLOOR, 1.45))
    # Biscuit sniffed him out: he stands by the bed, a proud heart overhead
    b.append(matted(G(198, FEET, dog(BISCUIT), 1.1)))
    b.append(heart(250, 752, 15, 4))
    # Max pulls Button out from under the bed, holding him by one paw
    mx = 478
    hand = (mx - 72 * MAX_S, FEET - 122 * MAX_S)          # upper wrist of the reach
    bear = teddy(hand[0] - 29, hand[1] + 45, 0.72)
    b.append(matted(GM(mx, FEET, kid_reach(MAX), MAX_S) + bear +
                    C(hand[0], hand[1], 8 * MAX_S, 4, "white")))
    # Lily claps and cheers
    b.append(matted(G(640, FEET, kid_stand(LILY, pose="up"), LILY_S)))
    b.append(heart(560, 470, 16, 4) + sparkle(470, 520, 12) + heart(300, 540, 14, 4))
    return spage("Biscuit Found Him!", "".join(b), num=9,
                 caption="Biscuit found him! Button is under Max's bed. Max reaches down and "
                         "pulls Button out. Lily claps and cheers. Good dog, Biscuit!")


def celebrate():
    b = []
    b.append(wall_line())
    b.append(bunting(70, 780, 220, n=11, sag=28))
    b.append(curtained_window(575, 330, 170, 150))
    b.append(heart(140, 350, 18, 4) + star(450, 340, 18, 4, "white") + sparkle(330, 400, 11))
    b.append(blocks(88, FEET + 6, 1.15, letters="ABC"))
    # Max jumps with a balloon bunch; Lily hugs Button; Biscuit dances
    mx = 250
    hand = (mx + 64 * MAX_S, FEET - 207 * MAX_S)
    b.append(balloon_bunch(hand[0], hand[1] - 70 * 1.25, 1.25))
    b.append(matted(G(mx, FEET, kid_jump(MAX), MAX_S)))
    b.append(matted(G(488, FEET, kid_stand(LILY, pose="hold"), LILY_S) +
                    hold_teddy(488, FEET, LILY_S)))
    b.append(matted(G(668, FEET, dog(BISCUIT), DOG_S)))
    b.append(music_note(610, 700, 1.4) + music_note(750, 650, 1.2))
    return spage("Hooray for Button!", "".join(b), num=10,
                 caption="Max and Lily and Biscuit found Button! Everyone dances in a happy "
                         "circle. Now Max and Lily snuggle into bed with Button.")


def back_cover():
    b = []
    b.append(banner("The End", 260, size=72))
    b.append(moon(700, 215, 44) + star(150, 205, 18, 4, "white") +
             star(175, 330, 13, 4, "white") + star(690, 345, 14, 4, "white"))
    # cozy vignette: Button and Biscuit asleep on the rug
    b.append(rug(W / 2, 610, 250, 38))
    b.append(teddy(320, 610, 0.95))
    b.append(matted(G(505, 614, dog_sleep(BISCUIT), 1.35)))
    b.append(TXT(W / 2, 740, "Goodnight, Max. Goodnight, Lily.", 28, weight="normal"))
    b.append(TXT(W / 2, 780, "Goodnight, Biscuit and Button.", 28, weight="normal"))
    b.append(TXT(W / 2, 860, "Made with love for Max and Lily", 28, weight="normal"))
    b.append(heart(W / 2, 922, 22, 4))
    return spage("", "".join(b), layout="vignette")


# ---------------------------------------------------------------- build
# Builder names are stable ids (tests + README reference them), so the
# creativity page added later slots in as "07b"; printed page numbers
# (num=) follow the page's position in the book.
BUILDERS = [
    ("01-cover",             cover),
    ("02-names",             names),
    ("03-intro",             intro),
    ("04-problem",           problem),
    ("05-search-bedroom",    search_bedroom),
    ("06-search-living",     search_living),
    ("07-find-activity",     find_activity),
    ("07b-draw-hiding-spot", draw_hiding_spot),
    ("08-solve",             solve),
    ("09-celebrate",         celebrate),
    ("10-back-cover",        back_cover),
]

if __name__ == "__main__":
    build(BUILDERS, OUTDIR, only=sys.argv[1:] or None,
          pdf_name="Harper-Coloring-Book.pdf")
