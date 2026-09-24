#!/usr/bin/env python3
"""Render one showcase page per content pack into examples/showcase/pages/
and validate each with lib.validate — a fast visual + deterministic smoke
of the whole library. Run from anywhere:

    python tools/showcase.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "lib"))

import math  # noqa: E402

import cv2  # noqa: E402
import cairosvg  # noqa: E402

import scenes  # noqa: E402
from charlib import (W, G, spage, kid_stand, kid_run, kid_jump,          # noqa: E402
                     kid_point, kid_carry, kids_holding_hands, kid_wheelchair,
                     kid_toddler, kid_in_bed, dog, fish, turtle,
                     snail, rabbit, duck, cow, sheep, chicken, owl, monkey,
                     frog, tulip, sunflower, apple_tree, potted_plant, cactus,
                     kite, scooter, tricycle, seesaw, sandbox,
                     blocks, dice, drum, puzzle_piece, ice_cream, barn,
                     schoolhouse, lighthouse, windmill, school_bus, dump_truck,
                     helicopter, hot_air_balloon, sailboat, rowboat, canoe,
                     train_engine, train_car, rail_track, shooting_star, moon,
                     ufo, satellite, telescope, star_field, rocket,
                     planet_ringed, symmetry_page, finish_page, sticker_sheet,
                     speech_bubble, thought_bubble, pattern_menu,
                     design_template, name_trace_page, butterfly, star, heart,
                     dino, soccer_ball, bird_side, crater_ground, fit_fragment,
                     fragment_bbox, LINE, C, P, cloud, matted, flower,
                     grass_tuft, lamppost, ball, castle_small, airplane, pond,
                     tree_round, tree_pine)
from validate import validate_svg  # noqa: E402

T1 = {"hair": "pigtails", "outfit": "dress"}
T2 = {"hair": "buzz", "outfit": "tee"}
T3 = {"hair": "long_wavy", "outfit": "dress", "glasses": True}
T4 = {"hair": "curly", "outfit": "tee", "freckles": True}
P85 = {"scale": 0.85}              # one figure scale per page: sizes stay honest

# ---------------------------------------------------------------- catalog grid
# Catalog pages are tidy grids over the drawable band (below the title zone,
# above the caption band). Every item is MEASURED (fragment_bbox) and scaled
# to its cell with page-weight strokes (fit_fragment), so nothing overlaps
# and small helpers get big enough for >=3mm colorable regions.
BAND = (60, 172, 790, 988)          # x0, y0, x1, y1


def grid(rows, band=BAND, fill_w=0.84, fill_h=0.80):
    """rows: [(height_weight, [item, ...], ground), ...].
    item = (fragment, mode[, opts]):
      mode "ground" stands the art ON the row's base line (a short base
      line is drawn under it when the row's ground is "line"); "sit" stands
      it without a base line (boats on their own waves); "float" centres it.
      opts: wt=cell width weight; scale=FIXED scale instead of fit-to-cell
      (figures keep their relative sizes; origin placed on the base line).
    ground: "line", None, or a callable(x0, x1, y) drawing a row-wide ground."""
    x0, y0, x1, y1 = band
    total = sum(r[0] for r in rows)
    out, y = [], y0
    for weight, items, ground in rows:
        rh = (y1 - y0) * weight / total
        items = [it if len(it) == 3 else (it[0], it[1], {}) for it in items]
        wts = [it[2].get("wt", 1.0) for it in items]
        base = y + rh - 0.07 * rh
        if callable(ground):
            out.append(ground(x0 + 10, x1 - 10, base))
        cx0 = x0
        for (frag, mode, opts), wt in zip(items, wts):
            cw = (x1 - x0) * wt / sum(wts)
            cx = cx0 + cw / 2
            cx0 += cw
            if "scale" in opts:
                sc = opts["scale"]
                bb = fragment_bbox(frag, stroke=False)
                placed = G(cx - (bb[0] + bb[2]) / 2 * sc, base, frag, sc)
            elif mode == "float":
                placed = fit_fragment(frag, cx, y + rh * 0.47, fill_w * cw, fill_h * rh)
            else:
                placed = fit_fragment(frag, cx, base, fill_w * cw, fill_h * rh,
                                      anchor="bottom")
            if mode == "ground" and ground == "line":
                bb = fragment_bbox(placed, stroke=False)
                half = min(cw * 0.47, (bb[2] - bb[0]) / 2 + 16)
                out.append(LINE(cx - half, base, cx + half, base, 3.5))
            out.append(placed)
        y += rh
    return "".join(out)


def creativity():
    """Creativity catalog: a speaker with a speech bubble and a dog with a
    thought bubble, both placed via speaker_top (the bubble tail ends 20px
    above the MEASURED head top), then the pattern menu + design template."""
    gy = 585
    girl = G(215, gy, kid_stand(T1, "wave"), 0.95)
    pup = G(560, gy, dog({"coat": "spots"}), 1.5)
    girl_top = fragment_bbox(girl, stroke=False)[1]
    pup_head = (560 + 58 * 1.5, gy - 130 * 1.5)            # dog head top (local 58,-130)
    return (LINE(70, gy, 780, gy, 4) + girl + pup +
            speech_bubble(speaker_top=(215, girl_top), w=240, h=104, lines=True) +
            thought_bubble(speaker_top=pup_head, side=-1) +
            pattern_menu(76, 752, w=330) +
            design_template("tee", cx=615, ground_y=975))


# ---------------------------------------------------------------- scene pages
# Three-layer recipe (reference/drawing-guide.md): scene kit background,
# midground anchors at reduced size, foreground figures/vehicles at
# 1.2-1.4 scale standing ON (or a step in front of) the kit's ground line,
# matted() where a background line would otherwise run tangent to them.
def meadow_kite():
    g = scenes.SCENE_GROUND
    s, kx = 1.3, 205
    flyer = {"hair": "tousled", "outfit": "tee"}        # pigtails would cover
    hand = (kx + 55 * s, g - 186 * s)                   # the string hand (wave wrist)
    # kite corner sits ON the kite's own string-stub direction (46,-40) so
    # the long string and the stub read as one straight line
    ux, uy = 46 / math.hypot(46, 40), -40 / math.hypot(46, 40)
    corner = (hand[0] + ux * 480, hand[1] + uy * 480)
    kw = 130
    return (scenes.scene_meadow(variant=0, flowers=0, sky_fill=False) +
            cloud(380, 300, 22) +
            matted(G(kx, g, kid_stand(flyer, "wave"), s)) +
            matted(G(425, g + 26, dog({"coat": "patch"}), 1.2)) +     # a step in front
            grass_tuft(318, g + 24) + grass_tuft(514, g + 24) +
            LINE(hand[0], hand[1], corner[0], corner[1], 2.5) +
            kite(corner[0] + kw / 2, corner[1], w=kw) +
            sunflower(712, g, h=150) + tulip(768, g, h=104) +
            G(532, g - 12, flower(0, 0, s=1.3)) + LINE(532, g - 12, 532, g, 3) +
            grass_tuft(560, g - 2) + grass_tuft(676, g - 2))


def street_busstop():
    road_y = scenes.SCENE_GROUND - 120                  # far edge of the road
    near = road_y + scenes.ROAD_H                       # vehicles drive here
    walk = 965                                          # near sidewalk
    kids_x, sign_x = 575, 752
    return (scenes.scene_street(variant=0, lampposts=False, midground=False) +
            airplane(470, 360, w=230) +
            G(98, near, lamppost(0, 0, h=250), 0.9) +              # midground
            school_bus(300, near, w=320) +
            LINE(50, walk, W - 50, walk, 4) +
            # bus-stop sign on the sidewalk, the kids waiting beside it
            LINE(sign_x, walk, sign_x, walk - 180, 5) +
            C(sign_x, walk - 204, 26, 5, "white") + C(sign_x, walk - 204, 15, 3, "white") +
            kids_holding_hands(T1, T2, kids_x, walk, s=1.2))


def beach_day():
    g = scenes.BEACH_GROUND
    horizon = 722
    far_sea = (LINE(50, horizon, W - 50, horizon, 3.5) +
               sailboat(488, horizon, w=64) + sailboat(578, horizon, w=46) +
               "".join(P(f"M {x - 16} {y} Q {x} {y - 9} {x + 16} {y}", 3)
                       for x, y in ((452, 792), (598, 770), (740, 800), (150, 772))))
    return (far_sea +                                                # drawn first
            scenes.scene_beach(variant=0, midground=False) + cloud(440, 330, 24) +
            lighthouse(118, g - 4, h=320) +                          # midground
            matted(G(282, g, kid_stand(T2, "up"), 1.3)) +
            matted(castle_small(450, g + 4, w=150)) +
            matted(ball(598, g + 50, 30)) +
            star(168, g + 58, 24, 4, "white"))                        # starfish


def space_landing():
    g = scenes.SPACE_GROUND
    s, kx = 1.25, 480
    head = (kx, g - 188 * s)
    return (scenes.scene_space(variant=0) +
            G(606, 520, ufo(0, 0, w=190), 1.0) +                     # midground
            matted(G(225, g, rocket(0, -105), 1.35)) +
            # bubble helmet drawn FIRST in the group: hair and the waving
            # hand overlap it, nothing is drawn over the face
            matted(C(head[0], head[1], 37 * s * 1.45, 4) +
                   G(kx, g, kid_stand(T4, "wave"), s)))


def farm_day():
    g = scenes.SCENE_GROUND
    return (scenes.scene_farm(variant=0, pond_too=False, midground=False,
                              fence=False) +
            hot_air_balloon(470, 420, h=190) +
            windmill(718, g, h=300) +                                # midground
            pond(705, g + 4, w=180) + duck(700, g - 6, w=74) +
            cow(470, g + 24, w=300) +          # crosses the lines behind it: no mat needed
            matted(chicken(128, g + 24, w=118)))


def pages():
    gr, fl = "ground", "float"
    return {
        # three columns: at four, animals fit ~150px and legs/ears/horns drop
        # under the 3x3mm colorable floor; plants get their own page (19)
        "01-animals": grid([
            (1, [(fish(0, 0), fl), (turtle(0, 0), gr), (snail(0, 0), gr)], "line"),
            (1, [(rabbit(0, 0), gr), (duck(0, 0), "sit"), (cow(0, 0), gr)], "line"),
            (1, [(sheep(0, 0), gr), (chicken(0, 0), gr), (owl(0, 0), gr)], "line"),
            (1, [(monkey(0, 0, banana=True), gr), (frog(0, 0), gr),
                 (bird_side(0, 0), gr)], "line"),
        ]),
        "02-vehicles": grid([
            (1.2, [(hot_air_balloon(0, 0), fl), (helicopter(0, 0), fl)], None),
            (1, [(sailboat(0, 0), "sit"), (rowboat(0, 0), "sit"),
                 (canoe(0, 0), "sit")], None),
            (1, [(school_bus(0, 0), gr), (dump_truck(0, 0), gr)],
             lambda a, b, y: LINE(a, y, b, y, 4)),
            (0.8, [(train_engine(0, 0), gr), (train_car(0, 0), gr),
                   (train_car(0, 0, kind="passenger"), gr),
                   (train_car(0, 0, kind="caboose"), gr)],
             lambda a, b, y: rail_track(a, b, y)),
        ], fill_w=0.92),
        "03-space": grid([
            (1, [(moon(0, 0), fl), (ufo(0, 0, beam=True), fl),
                 (satellite(0, 0), fl)], None),
            (1, [(planet_ringed(0, 0), fl), (shooting_star(0, 0, 1.6), fl),
                 (star_field(0, 0, 200, 200, n=9), fl)], None),
            (1.3, [(telescope(0, 0), gr), (rocket(0, -105), gr)],
             lambda a, b, y: crater_ground(y, a, b)),
        ]),
        "04-games": grid([
            (1.1, [(kite(0, 0), fl), (ice_cream(0, 0), fl), (puzzle_piece(0, 0), fl)], None),
            (1, [(drum(0, 0), gr), (blocks(0, 0), gr), (dice(0, 0, rot=12), gr)], "line"),
            (1, [(scooter(0, 0), gr), (tricycle(0, 0), gr)], "line"),
            (1, [(seesaw(0, 0), gr), (sandbox(0, 0), gr)], "line"),
        ]),
        "05-places": grid([
            (1, [(barn(0, 0), gr), (schoolhouse(0, 0), gr)], "line"),
            (1, [(lighthouse(0, 0), gr), (windmill(0, 0), gr)], "line"),
        ], fill_w=0.80, fill_h=0.84),
        "06-people": grid([
            (1, [(kid_run(T2), gr, P85), (kid_jump(T1), gr, P85),
                 (kid_point(T3), gr, P85)], "line"),
            (1, [(kid_carry(T4), gr, P85), (kid_wheelchair(T3), gr, P85),
                 (kid_toddler(T1), gr, P85)], "line"),
            (1, [(kids_holding_hands(T1, T2, 0, 0), gr, dict(P85, wt=1.25)),
                 (kid_stand(T4, "wave", accessories=("cap", "cape", "scarf")), gr, P85),
                 (kid_in_bed(T2, -100, floor=0, w=200), gr, {"scale": 1.0, "wt": 1.15})],
             "line"),
        ]),
        "19-garden": grid([
            (1, [(apple_tree(0, 0), gr), (tree_round(0, 0), gr),
                 (tree_pine(0, 0), gr)], "line"),
            (1, [(sunflower(0, 0), gr), (tulip(0, 0), gr),
                 (potted_plant(0, 0), gr), (cactus(0, 0, pot=True), gr)], "line"),
        ], fill_h=0.84),
        "07-scenes-meadow": meadow_kite(),
        "08-scenes-street": street_busstop(),
        "09-scenes-beach": beach_day(),
        "10-scenes-space": space_landing(),
        "11-scenes-farm": farm_day(),
        "12-creativity": creativity(),
    }


CATALOG = ("01", "02", "03", "04", "05", "06", "12", "19")


def main():
    outdir = os.path.join(ROOT, "examples", "showcase", "pages")
    os.makedirs(outdir, exist_ok=True)
    builders = {name: ("body", body) for name, body in pages().items()}
    builders["13-symmetry"] = ("page", symmetry_page(
        "butterfly", caption="Draw the other half! Make yours different."))
    builders["14-finish"] = ("page", finish_page(
        "house", caption="The house is missing its right side!"))
    builders["15-stickers"] = ("page", sticker_sheet(
        [butterfly(0, 0, 1.6), star(0, 0, 30, 4, "white"),
         heart(0, 0, 26, 4, "white"), dino(0, 0, s=0.9),
         rocket(0, -60, h=140), soccer_ball(0, 0, 34)]))
    builders["16-tracing"] = ("page", name_trace_page(["Harper", "Max", "Lily"]))
    import photolib as _pl
    _photo = os.path.join(ROOT, "examples", "showcase", "fixture_animal.png")
    cv2.imwrite(_photo, _pl.synthetic_photo("animal"))
    builders["17-photo"] = ("page", _pl.composite_page(
        _photo, scenes.scene_meadow(), scenes.SCENE_GROUND,
        x=580, scale=0.95, title="Photo Traced",
        caption="A photo turned into a coloring page."))
    builders["18-photo-sketch"] = ("page", _pl.photo_to_svg(
        _photo, style="sketch", title="Sketch Style", layout="creative"))

    bad = 0
    for name in sorted(builders):
        kind, content = builders[name]
        svg = content if kind == "page" else spage(
            name.split("-", 1)[1].replace("-", " ").title(), content,
            layout="activity" if name[:2] in CATALOG else None)
        rep = validate_svg(svg)
        status = "OK " if rep["ok"] else "FAIL"
        print(f"{status} {name:22s} {rep['counts']}")
        for f in rep["findings"]:
            if f["severity"] == "HIGH":
                print("     HIGH:", f["check"], f["msg"][:90])
                bad += 1
        p = os.path.join(outdir, name)
        with open(p + ".svg", "w") as fh:
            fh.write(svg)
        cairosvg.svg2png(bytestring=svg.encode(), write_to=p + ".png",
                         output_width=510)
    print("HIGH findings:", bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
