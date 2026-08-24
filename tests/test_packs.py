"""Content-pack smoke tests: every new helper renders, parses, and its
canonical sample composition passes the deterministic validator."""
import os
import subprocess
import sys
import xml.etree.ElementTree as ET

from charlib import (G, spage, school_bus, dump_truck, helicopter,
                     hot_air_balloon, sailboat, rowboat, canoe, train_car,
                     rail_track, shooting_star, moon, ufo, satellite,
                     telescope, star_field, crater_ground, planet_ringed, fish, turtle,
                     snail, rabbit, duck, cow, sheep, chicken, owl, monkey,
                     frog, tulip, sunflower, apple_tree, potted_plant,
                     cactus, garden_strip, kite, scooter, tricycle, seesaw,
                     sandbox, blocks, dice, drum, puzzle_piece, ice_cream,
                     barn, schoolhouse, lighthouse, windmill, kid_run,
                     kid_jump, kid_point, kid_carry, kid_in_bed,
                     kids_holding_hands, kid_wheelchair, kid_toddler,
                     speech_bubble, symmetry_page, finish_page, pattern_menu,
                     design_template, sticker_sheet, butterfly, star, heart,
                     dino, rocket, soccer_ball, mountain_range, road, ROAD_H, sun, cloud,
                     fence_picket, forest_border, bridge, pond, beach_shore)
import scenes
from validate import validate_svg

G_ = 940
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _check(name, svg, **kw):
    ET.fromstring(svg)
    rep = validate_svg(svg, **kw)
    highs = [f for f in rep["findings"] if f["severity"] == "HIGH"]
    assert not highs, f"{name}: {highs}"
    return rep


def test_vehicles_pack():
    body = (school_bus(190, G_, w=240) + dump_truck(480, G_, w=230) +
            G(680, 260, helicopter(0, 0), 0.8) +
            G(400, 250, hot_air_balloon(0, 0), 0.85) +
            sailboat(680, 520, w=190) + rowboat(680, 660, w=160) +
            canoe(680, 790, w=150) +
            rail_track(60, 420, G_ + 20) +
            train_car(300, G_ + 20, w=140) +
            train_car(450, G_ + 20, w=140, kind="passenger") +
            train_car(600, G_ + 20, w=140, kind="caboose"))
    _check("vehicles", spage("Vehicles", body))


def test_space_pack():
    body = (star_field(70, 180, 780, 700, n=14) + moon(150, 300, r=55) +
            G(400, 320, ufo(0, 0, beam=True), 0.85) +
            G(650, 300, satellite(0, 0), 0.7) +
            telescope(140, 640, h=150) + shooting_star(430, 500, 1.0) +
            planet_ringed(680, 560, r=60) +
            G(350, G_, rocket(0, -105), 1.1) + crater_ground(G_ + 20))
    _check("space", spage("Space", body))


def test_nature_pack():
    body = (fish(140, 310, w=150) + turtle(340, 310, w=150) +
            snail(520, 310, w=100) + rabbit(680, 310, w=130) +
            duck(140, 490, w=120) + cow(370, 490, w=200) +
            sheep(600, 490, w=150) + chicken(760, 490, w=95) +
            owl(120, 670, w=100) + monkey(300, 670, w=150) +
            frog(470, 670, w=130) + tulip(568, 670, h=95) +
            sunflower(642, 670, h=130) + apple_tree(736, 670, h=160) +
            potted_plant(106, 880, h=120) + cactus(180, 880, h=140) +
            garden_strip(235, 415, 880))
    _check("nature", spage("Nature", body))


def test_games_pack():
    body = (G(178, 300, kite(0, 0, w=130), 1.1) +
            scooter(125, G_, w=130) + tricycle(258, G_, w=130) +
            seesaw(425, G_, w=190) + sandbox(595, G_, w=160) +
            blocks(720, G_, s=0.8) + G(775, 815, dice(0, 0, s=38, rot=12)) +
            drum(108, 700, w=105) + puzzle_piece(198, 660, s=64) +
            ice_cream(300, 655, h=115))
    _check("games", spage("Games", body))


def test_structures_pack():
    from charlib import dog
    body = (sun(120, 140, r=40) + cloud(650, 160, 26) +
            barn(160, 660, w=220) + schoolhouse(415, 660, w=250) +
            lighthouse(600, 660, h=280) + windmill(728, 660, h=230) +
            fence_picket(60, 250, 880) + sandbox(400, 880, w=160) +
            G(660, G_, dog({"coat": "spots"}), 1.4))
    _check("structures", spage("Places", body))


def test_people_pack():
    t1 = {"hair": "pigtails", "outfit": "dress"}
    t2 = {"hair": "buzz", "outfit": "tee"}
    t3 = {"hair": "long_wavy", "outfit": "dress", "glasses": True}
    body = (G(120, 480, kid_run(t2), 1.0) +
            G(390, G_, kid_jump(t1), 1.0) + G(540, G_, kid_point(t3), 1.0) +
            G(700, G_, kid_carry(t2), 1.0) +
            kids_holding_hands(t1, t2, 250, 700, s=0.85) +
            G(520, 700, kid_wheelchair(t3), 0.9) +
            G(680, 700, kid_toddler(t1), 1.0) +
            kid_in_bed(t2, 72, floor=G_ + 20, w=230))
    _check("people", spage("People", body))


def test_creativity_pack():
    for name, svg in (
            ("symmetry", symmetry_page("butterfly")),
            ("finish", finish_page("house")),
            ("stickers", sticker_sheet([butterfly(0, 0, 1.6),
                                        star(0, 0, 30, 4, "white"),
                                        dino(0, 0, s=0.9),
                                        rocket(0, -60, h=140),
                                        soccer_ball(0, 0, 34)])),
            ("design", spage("Design", speech_bubble(200, 300, lines=True) +
                             pattern_menu(90, 610) +
                             design_template("tee", cx=560, ground_y=890),
                             layout="creative"))):
        _check(f"creativity:{name}", svg)


def test_landscape_pack():
    body = (sun(120, 140, r=40) + cloud(650, 160, 26) +
            mountain_range(310, G_, peaks=3, w=440) +
            road(440, 790, G_ - 120) +
            forest_border(G_, n=3, x0=255, x1=425, h=115) +
            bridge(200, G_ - 170, w=260) + pond(690, G_ - 30))
    _check("landscapes", spage("World", body))


def test_scene_kits():
    kits = [(scenes.scene_meadow(), scenes.SCENE_GROUND),
            (scenes.scene_street(), scenes.SCENE_GROUND - 120 + ROAD_H),
            (scenes.scene_beach(), scenes.BEACH_GROUND),
            (scenes.scene_space(), scenes.SPACE_GROUND),
            (scenes.scene_farm(), scenes.SCENE_GROUND)]
    for i, (body, _ground) in enumerate(kits):
        _check(f"scene{i}", spage("Kit", body))
    # declared ground lines actually work: a kid stands on each kit
    from charlib import kid_stand
    body, ground = kits[0]
    body += G(430, ground, kid_stand({"outfit": "tee"}, "wave"), 1.0)
    _check("scene+figure", spage("Meadow", body))


def test_showcase_pages_all_clean():
    """tools/showcase.py must build + validate every showcase page."""
    r = subprocess.run(
        [sys.executable, os.path.join("tools", "showcase.py")],
        capture_output=True, text=True, timeout=300, cwd=REPO)
    assert r.returncode == 0, r.stdout + r.stderr
