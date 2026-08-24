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

import cv2  # noqa: E402
import cairosvg  # noqa: E402

import scenes  # noqa: E402
from charlib import (W, G, GM, spage, sun, fence_picket, kid_stand, kid_run, kid_jump,          # noqa: E402
                     kid_point, kid_carry, kids_holding_hands, kid_wheelchair,
                     kid_toddler, kid_in_bed, dog, cat_sitting, fish, turtle,
                     snail, rabbit, duck, cow, sheep, chicken, owl, monkey,
                     frog, tulip, sunflower, apple_tree, potted_plant, cactus,
                     garden_strip, kite, scooter, tricycle, seesaw, sandbox,
                     blocks, dice, drum, puzzle_piece, ice_cream, barn,
                     schoolhouse, lighthouse, windmill, school_bus, dump_truck,
                     helicopter, hot_air_balloon, sailboat, rowboat, canoe,
                     train_engine, train_car, rail_track, shooting_star, moon,
                     ufo, satellite, telescope, star_field, rocket,
                     planet_ringed, symmetry_page, finish_page, sticker_sheet,
                     speech_bubble, thought_bubble, pattern_menu,
                     design_template, name_trace_page, butterfly, star, heart,
                     dino, soccer_ball)
from validate import validate_svg  # noqa: E402

T1 = {"hair": "pigtails", "outfit": "dress"}
T2 = {"hair": "buzz", "outfit": "tee"}
T3 = {"hair": "long_wavy", "outfit": "dress", "glasses": True}


def pages():
    G_ = 940
    return {
        "01-animals": (
            fish(140, 310, w=150) + turtle(340, 310, w=150) +
            snail(520, 310, w=100) + rabbit(680, 310, w=130) +
            duck(140, 490, w=120) + cow(370, 490, w=200) +
            sheep(600, 490, w=150) + chicken(760, 490, w=95) +
            owl(120, 670, w=100) + monkey(300, 670, w=150) +
            frog(470, 670, w=130) + tulip(568, 670, h=95) +
            sunflower(642, 670, h=130) + apple_tree(736, 670, h=160) +
            potted_plant(106, 880, h=120) + cactus(180, 880, h=140) +
            garden_strip(235, 415, 880)),
        "02-vehicles": (
            school_bus(190, G_, w=240) + dump_truck(480, G_, w=230) +
            G(680, 260, helicopter(0, 0), 0.8) +
            G(400, 250, hot_air_balloon(0, 0), 0.85) +
            sailboat(680, 520, w=190) + rowboat(680, 660, w=160) +
            canoe(680, 790, w=150) +
            rail_track(60, 420, G_ + 20) + train_engine(180, G_ + 20, w=170) +
            train_car(360, G_ + 20, w=140) +
            train_car(505, G_ + 20, w=140, kind="passenger") +
            train_car(650, G_ + 20, w=140, kind="caboose")),
        "03-space": (
            star_field(70, 180, W - 70, 700, n=14) +
            moon(150, 300, r=55) + G(400, 320, ufo(0, 0, beam=True), 0.85) +
            G(650, 300, satellite(0, 0), 0.7) +
            telescope(140, 640, h=150) + shooting_star(430, 500, 1.0) +
            planet_ringed(680, 560, r=60) +
            G(350, G_, rocket(0, -105), 1.1)),
        "04-games": (
            G(178, 300, kite(0, 0, w=130), 1.1) +
            scooter(125, G_, w=130) + tricycle(258, G_, w=130) +
            seesaw(425, G_, w=190) + sandbox(595, G_, w=160) +
            blocks(720, G_, s=0.8) + G(775, 815, dice(0, 0, s=38, rot=12), 1.0) +
            drum(108, 700, w=105) + puzzle_piece(198, 660, s=64) +
            ice_cream(260, 655, h=115)),
        "05-places": (
            sun(120, 140, r=40) + apple_tree(714, 660, h=200) +
            barn(160, 660, w=220) + schoolhouse(415, 660, w=250) +
            lighthouse(600, 660, h=280) + windmill(728, 660, h=230) +
            fence_picket(60, 250, 880) + sandbox(400, 880, w=160) +
            ice_cream(540, 830, h=115) + tricycle(680, 880, w=130)),
        "06-people": (
            G(120, 480, kid_run(T2), 1.0) +
            G(390, G_, kid_jump(T1), 1.0) + G(540, G_, kid_point(T3), 1.0) +
            G(700, G_, kid_carry(T2), 1.0) +
            kids_holding_hands(T1, T2, 250, 700, s=0.85) +
            G(520, 700, kid_wheelchair(T3), 0.9) +
            G(680, 700, kid_toddler(T1), 1.0) +
            kid_in_bed(T2, 72, floor=G_ + 20, w=230) +
            G(400, 560, kid_stand({"hair": "curly", "outfit": "tee",
                                   "freckles": True}, "wave",
                                  accessories=("cap", "cape", "scarf")), 0.8)),
        "07-scenes-meadow": scenes.scene_meadow() + G(
            430, scenes.SCENE_GROUND, kid_stand(T1, "wave"), 1.0),
        "08-scenes-street": scenes.scene_street() + G(
            400, scenes.SCENE_GROUND - 120 + scenes.ROAD_H,
            school_bus(0, 0, w=190), 0.9),
        "09-scenes-beach": scenes.scene_beach() + G(
            300, scenes.BEACH_GROUND, kid_stand(T2, "up"), 1.0),
        "10-scenes-space": scenes.scene_space() + G(
            300, scenes.SPACE_GROUND, rocket(0, -105), 1.1),
        "11-scenes-farm": scenes.scene_farm() + G(
            500, scenes.SCENE_GROUND, dog({"coat": "spots"}), 1.4),
        "12-creativity": (
            speech_bubble(190, 300, tail="down", lines=True) +
            G(190, 440, kid_stand(T1, "wave"), 0.9) +
            thought_bubble(590, 290) + G(590, 440, dog({"coat": "spots"}), 1.1) +
            pattern_menu(90, 610) + design_template("tee", cx=590, ground_y=890)),
    }


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
            name.split("-", 1)[1].replace("-", " ").title(), content)
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
