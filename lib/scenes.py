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
                     mountain_range, fence_ranch, fence_picket, barn,
                     crater_ground, star_field, planet_ringed, moon,
                     skyline, road, ROAD_H, lamppost, tree_round,
                     _f)

SCENE_GROUND = 940          # default land ground line
BEACH_GROUND = 900          # beach shoreline (sand ground)
SPACE_GROUND = 930          # lunar surface line


def scene_meadow(*, sun_at=(130, 140), hills=True, flowers=5):
    """Sunny meadow. Ground: SCENE_GROUND. Sky lane stays clear above y=300
    on the right for a title; flowers dot the foreground band."""
    out = [sun(*sun_at, r=42), cloud(660, 170, 28), sparkle(560, 220, 8)]
    if hills:
        out.append(hill(300, SCENE_GROUND, w=470, h=95))
        out.append(hill(645, SCENE_GROUND, w=320, h=70))
    out.append(LINE(50, SCENE_GROUND, W - 50, SCENE_GROUND, 4))
    kinds = (tulip, sunflower, flower)
    for i in range(flowers):
        fx = 120 + (W - 240) * (i + 0.5) / flowers
        if i % 3 == 2:
            out.append(G(fx, SCENE_GROUND - 12, flower(0, 0, s=1.3), 1.0))
            out.append(LINE(fx, SCENE_GROUND - 12, fx, SCENE_GROUND, 3))
        else:
            out.append(kinds[i % 2](fx, SCENE_GROUND, h=88 + 22 * (i % 3)))
        if i % 2 == 0:
            out.append(grass_tuft(fx + 30, SCENE_GROUND - 2))
    return "".join(out)


def scene_street(*, lampposts=True):
    """City street. Vehicle/figure ground: STREET_GROUND (road near edge)."""
    street_y = SCENE_GROUND - 120
    out = [sun(120, 140, r=40), cloud(650, 170, 26),
           skyline(street_y - 8, 60, W - 60), road(50, W - 50, street_y),
           LINE(50, street_y + ROAD_H, W - 50, street_y + ROAD_H, 4)]
    if lampposts:
        out.append(G(115, street_y + ROAD_H, lamppost(0, 0, h=250), 0.9))
        out.append(G(W - 115, street_y + ROAD_H, lamppost(0, 0, h=250), 0.9))
    return "".join(out)


def scene_beach(*, sun_at=(720, 140), umbrella=True):
    """Beach: waves + shoreline + shells. Ground: BEACH_GROUND (the sand)."""
    out = [sun(*sun_at, r=42), cloud(180, 170, 26),
           waves(BEACH_GROUND - 46, 50, W - 50, amp=10),
           beach_shore(BEACH_GROUND, 50, W - 50)]
    if umbrella:
        ux = 690
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


def scene_space(*, planet=True, ufo_target=None):
    """Lunar surface. Ground: SPACE_GROUND (crater line). Sky filled with a
    deterministic star field; optional ringed planet + small moon."""
    out = [star_field(60, 170, W - 60, SPACE_GROUND - 120, n=16)]
    if planet:
        out.append(planet_ringed(660, 300, r=70))
        out.append(moon(140, 260, r=42))
    out.append(crater_ground(SPACE_GROUND, 50, W - 50))
    return "".join(out)


def scene_farm(*, pond_too=True):
    """Farmyard: barn + ranch fence + grass. Ground: SCENE_GROUND."""
    out = [sun(130, 140, r=40), cloud(620, 160, 26),
           hill(560, SCENE_GROUND, w=460, h=70)]
    out.append(G(200, SCENE_GROUND, barn(0, 0, w=230), 1.0))
    out.append(fence_ranch(360, 620, SCENE_GROUND, posts=5))
    if pond_too:
        out.append(pond(700, SCENE_GROUND - 4, w=170))
    for i in range(4):
        out.append(grass_tuft(380 + i * 60, SCENE_GROUND - 2))
    return "".join(out)
