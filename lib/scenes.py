"""Scene kits: composite backgrounds that encode PROVEN composition —
ground lines, sky lanes, and prop placement that already pass validation.
Each returns a body string for spage()/page() and documents its ground
line so figures/vehicles snap on deterministically:

    from scenes import scene_beach, BEACH_GROUND
    body = scene_beach() + G(300, BEACH_GROUND, kid_stand(t), 1.0)
    svg = spage("Beach Day", body)

All placement is index arithmetic — never random — so output is
byte-deterministic. Compose ONE scene kit per page, then add figures,
matted(), and props on the declared ground line.
"""
import math

from charlib import (W, LINE, C, E, DOT, P, G, GM, rrect, star, sparkle,
                     sun, cloud, smooth_path, grass_tuft, flower, tulip,
                     sunflower, stones, waves, beach_shore, pond, hill,
                     tree_round, tree_pine,
                     mountain_range, fence_ranch, fence_picket, barn,
                     crater_ground, star_field, planet_ringed, moon,
                     skyline, road, ROAD_H, lamppost, tree_round,
                     _f)

SCENE_GROUND = 940          # default land ground line
BEACH_GROUND = 900          # beach shoreline (sand ground)
SPACE_GROUND = 930          # lunar surface line


def scene_meadow(*, sun_at=None, hills=True, flowers=None, sky_fill=True,
                 midground=True, variant=0):
    """Sunny meadow. Ground: SCENE_GROUND. variant=N re-lays the kit (sun
    side, hill shapes, planting, clouds) deterministically — same N, same
    page; different N, different meadow. midground adds a background tree."""
    v = variant % 4
    sun_at = sun_at or ((W - 130, 225) if v % 2 else (130, 225))
    out = [sun(*sun_at, r=42),
           cloud(660 - v * 90, 235, 28), sparkle(560 - v * 60, 250, 8)]
    if sky_fill:
        out += [cloud(230 + v * 70, 330, 20), sparkle(700 - v * 60, 330, 7)]
    if hills:
        hw, hh = ((470, 95), (520, 120), (430, 80))[v % 3]
        out.append(hill(300 + v * 40, SCENE_GROUND, w=hw, h=hh))
        out.append(hill(645 - v * 30, SCENE_GROUND, w=320, h=70))
    if midground:
        out.append(tree_round(610 + (v % 2) * 130, SCENE_GROUND - 4, h=145))
    out.append(LINE(50, SCENE_GROUND, W - 50, SCENE_GROUND, 4))
    kinds = (tulip, sunflower, flower)
    n_flowers = (flowers if flowers is not None else 5) + (v % 2)
    for i in range(n_flowers):
        fx = 120 + (W - 240) * ((i + v) % n_flowers + 0.5) / n_flowers
        if (i + v) % 3 == 2:
            out.append(G(fx, SCENE_GROUND - 12, flower(0, 0, s=1.3), 1.0))
            out.append(LINE(fx, SCENE_GROUND - 12, fx, SCENE_GROUND, 3))
        else:
            out.append(kinds[(i + v) % 2](fx, SCENE_GROUND,
                                          h=88 + 22 * ((i + v) % 3)))
        if (i + v) % 2 == 0:
            out.append(grass_tuft(fx + 30, SCENE_GROUND - 2))
    return "".join(out)


def scene_street(*, lampposts=True, sky_fill=True, midground=True,
                 variant=0):
    """City street. Vehicle/figure ground: STREET_GROUND (road near edge).
    variant=N rotates the skyline building mix and shifts sky dressing."""
    v = variant % 3
    street_y = SCENE_GROUND - 120
    out = [sun(650 - v * 200, 225, r=40), cloud(200 + v * 120, 235, 26),
           skyline(street_y - 8, 60, W - 60), road(50, W - 50, street_y),
           LINE(50, street_y + ROAD_H, W - 50, street_y + ROAD_H, 4)]
    if sky_fill:
        out += [cloud(300 + v * 90, 320, 22), sparkle(500 + v * 40, 300, 7)]
    if midground:
        out.append(tree_round(470 + v * 40, street_y + 2, h=110))
    if lampposts:
        lx = (115, W - 115) if v % 2 == 0 else (170, W - 170)
        out.append(G(lx[0], street_y + ROAD_H, lamppost(0, 0, h=250), 0.9))
        out.append(G(lx[1], street_y + ROAD_H, lamppost(0, 0, h=250), 0.9))
    return "".join(out)


def scene_beach(*, sun_at=None, umbrella=True, midground=True, variant=0):
    """Beach: waves + shoreline + shells. Ground: BEACH_GROUND (the sand).
    variant=N flips the umbrella side and re-lays waves/shells."""
    v = variant % 2
    sun_at = sun_at or ((140, 235) if v else (720, 235))
    out = [sun(*sun_at, r=42), cloud(180 + v * 470, 235, 26),
           waves(BEACH_GROUND - 46, 50, W - 50, amp=10),
           beach_shore(BEACH_GROUND, 50, W - 50)]
    if midground:
        out.append(E(120 + v * 40, BEACH_GROUND - 10, 46, 14, 3.5, "white"))
        out.append(stones([(100 + v * 40, BEACH_GROUND - 6)]))
    if umbrella:
        ux = 690 - v * 480
        out.append(LINE(ux, BEACH_GROUND, ux, BEACH_GROUND - 170, 4))
        out.append(P(f"M {_f(ux - 70)} {_f(BEACH_GROUND - 160)} "
                     f"Q {_f(ux)} {_f(BEACH_GROUND - 235)} {_f(ux + 70)} {_f(BEACH_GROUND - 160)} Z",
                     4, "white"))
        for i in (-1, 0, 1):
            out.append(LINE(ux + i * 35, BEACH_GROUND - 160,
                            ux + i * 23, BEACH_GROUND - 205 + abs(i) * 12, 2.5))
        out.append(LINE(ux, BEACH_GROUND - 235, ux, BEACH_GROUND - 218, 3))
        out.append(P(f"M {_f(ux - 26)} {_f(BEACH_GROUND - 8)} "
                     f"Q {_f(ux)} {_f(BEACH_GROUND - 22)} {_f(ux + 26)} {_f(BEACH_GROUND - 8)} "
                     f"Q {_f(ux)} {_f(BEACH_GROUND - 14)} {_f(ux - 26)} {_f(BEACH_GROUND - 8)} Z",
                     3, "white"))
    for i, (fx, fy) in enumerate(((0.16, 0.5), (0.42, 0.62), (0.30, 0.8))):
        out.append(P(f"M {_f(60 + (W - 120) * fx - 10)} {_f(BEACH_GROUND + fy * 20 - 10)} "
                     f"Q {_f(60 + (W - 120) * fx)} {_f(BEACH_GROUND + fy * 20 - 20)} "
                     f"{_f(60 + (W - 120) * fx + 10)} {_f(BEACH_GROUND + fy * 20 - 10)} "
                     f"Q {_f(60 + (W - 120) * fx)} {_f(BEACH_GROUND + fy * 20 - 4)} "
                     f"{_f(60 + (W - 120) * fx - 10)} {_f(BEACH_GROUND + fy * 20 - 10)} Z", 2.5))
    return "".join(out)


def scene_space(*, planet=True, midground=True, variant=0):
    """Lunar surface. Ground: SPACE_GROUND (crater line). Sky filled with a
    deterministic star field; optional ringed planet + small moon.
    variant=N flips planet side and re-lays the star density."""
    v = variant % 2
    out = [star_field(60, 170, W - 60, SPACE_GROUND - 120, n=13 + v * 4)]
    if planet:
        out.append(planet_ringed(W - 190 if v else 660, 300, r=70))
        out.append(moon(W - 150 if v else 140, 260, r=42))
    if midground:
        for dx, rx in ((-60, 22), (10, 14)):
            out.append(E(705 + dx, SPACE_GROUND - 8, rx, rx * 0.4, 3.5, "white"))
    out.append(crater_ground(SPACE_GROUND, 50, W - 50))
    return "".join(out)


def scene_farm(*, pond_too=True, sky_fill=True, midground=True, variant=0):
    """Farmyard: barn + ranch fence + grass. Ground: SCENE_GROUND.
    variant=N flips the barn side and re-lays fence/pond."""
    v = variant % 2
    out = [sun(130 + v * 560, 225, r=40), cloud(620 - v * 460, 235, 26),
           hill(560 - v * 180, SCENE_GROUND, w=460, h=70)]
    if sky_fill:
        out += [sparkle(300 + v * 60, 330, 7), cloud(450 - v * 60, 320, 20)]
    if midground:
        out.append(tree_pine(740 - v * 620, SCENE_GROUND, h=150))
    out.append(G(200 + v * 430, SCENE_GROUND, barn(0, 0, w=230), 1.0))
    out.append(fence_ranch(360 - v * 290, 650 - v * 290, SCENE_GROUND,
                           posts=5 + v))
    if pond_too:
        out.append(pond(700 - v * 540, SCENE_GROUND - 4, w=170))
    for i in range(4):
        out.append(grass_tuft(380 + i * 60 + v * 40, SCENE_GROUND - 2))
    return "".join(out)
