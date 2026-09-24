#!/usr/bin/env python3
"""Photo-to-outline evaluation harness.

Renders the synthetic fixture tiers through the trace pipeline and scores
each result on reference-free metrics (what we can measure on ANY photo)
plus reference metrics (synthetic fixtures only, where the subject's true
shape is known). A second, REAL-PHOTO tier traces the open-licensed sample
photos in assets/photos/ (plus any *.jpg/*.png in --photos DIR, which
never enters the repo) and scores them reference-free: subject-ink ratio
inside the GrabCut subject mask, sliver count, region count. Produces a
markdown scorecard, and --gate mode fails when a metric leaves its
calibrated acceptance band.

    python tools/eval_photo.py                 # report
    python tools/eval_photo.py --gate          # CI: exit 1 out of band
    python tools/eval_photo.py --styles clean,sketch
    python tools/eval_photo.py --photos ~/my-test-photos   # extra real photos
    python tools/eval_photo.py --no-photos     # synthetic tier only

Bands live in tools/eval_bands.json (metric -> [low, high]); regenerate
with --calibrate after intentional pipeline changes, review the diff.
Real-photo keys are "photo:<name>|<style>|<metric>"; a photo that is not
present in a run is simply not checked (the bedroom sample lives outside
the repo — it shows children — so its bands only bite locally).
"""
import argparse
import json
import os
import sys

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "lib"))

import cairosvg  # noqa: E402
import photolib  # noqa: E402
from charlib import qa_page  # noqa: E402

FIXTURES = ("animal", "house", "car", "crisp_toy", "soft_portrait",
            "textured_foliage", "low_light")
BANDS_PATH = os.path.join(ROOT, "tools", "eval_bands.json")
PHOTOS_DIR = os.path.join(ROOT, "assets", "photos")     # open-licensed samples
PHOTO_EXT = (".jpg", ".jpeg", ".png")


# ---------------------------------------------------------------- fixtures
def fixture_path(kind, tmp):
    p = os.path.join(tmp, f"fx_{kind}.png")
    cv2.imwrite(p, photolib.synthetic_photo(kind))
    return p


# ---------------------------------------------------------------- ground truth
def subject_truth(kind, size=640):
    """Approximate TRUE subject mask for the synthetic fixtures (draw shapes
    twice — once into the photo, once here as a mask)."""
    mask = np.zeros((size, size), np.uint8)
    if kind == "animal":
        cv2.ellipse(mask, (size // 2, int(size * 0.58)), (int(size * 0.30),
                    int(size * 0.20)), 0, 0, 360, 255, -1)
        cv2.circle(mask, (int(size * 0.72), int(size * 0.42)),
                   int(size * 0.13), 255, -1)
        cv2.ellipse(mask, (int(size * 0.60), int(size * 0.30)),
                    (int(size * 0.045), int(size * 0.11)), 25, 0, 360, 255, -1)
    elif kind == "house":
        pts = np.array([[size * 0.2, size * 0.75], [size * 0.2, size * 0.45],
                        [size * 0.5, size * 0.25], [size * 0.8, size * 0.45],
                        [size * 0.8, size * 0.75]], np.int32)
        cv2.fillPoly(mask, [pts], 255)
    elif kind == "car":
        cv2.rectangle(mask, (int(size * 0.15), int(size * 0.5)),
                      (int(size * 0.85), int(size * 0.68)), 255, -1)
        pts = np.array([[size * 0.28, size * 0.5], [size * 0.38, size * 0.36],
                        [size * 0.62, size * 0.36], [size * 0.74, size * 0.5]],
                       np.int32)
        cv2.fillPoly(mask, [pts], 255)
        cv2.circle(mask, (int(size * 0.30), int(size * 0.68)),
                   int(size * 0.06), 255, -1)
        cv2.circle(mask, (int(size * 0.70), int(size * 0.68)),
                   int(size * 0.06), 255, -1)
    elif kind == "crisp_toy":
        cv2.rectangle(mask, (int(size * 0.2), int(size * 0.3)),
                      (int(size * 0.5), int(size * 0.7)), 255, -1)
        cv2.circle(mask, (int(size * 0.68), int(size * 0.5)),
                   int(size * 0.16), 255, -1)
    else:
        return None
    return mask


# ---------------------------------------------------------------- metrics
def ink_of_svg(svg_str):
    """Rasterize a traced page and return its ink mask at 850px width."""
    png = cairosvg.svg2png(bytestring=svg_str.encode(), output_width=850,
                           background_color="white")
    arr = np.frombuffer(png, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
    return (img < 128).astype(np.uint8) * 255


def metrics_for(svg_str):
    """Reference-free metrics on a traced page."""
    from validate import validate_svg
    rep = validate_svg(svg_str, require_span=False)
    q = None
    try:
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".svg",
                                         delete=False) as fh:
            fh.write(svg_str)
            tmp = fh.name
        q = qa_page(tmp)
        os.unlink(tmp)
    except Exception:
        pass
    ink = ink_of_svg(svg_str)
    strokes = svg_str.count("<path")
    ys, xs = np.nonzero(ink)
    coverage = float((ink > 0).mean()) * 100
    return {
        "strokes": strokes,
        "slivers": q["sliver_count"] if q else None,
        "regions": q["regions"] if q else None,
        "print_safe": q["print_safe"] if q else None,
        "ink_coverage_pct": round(coverage, 2),
        "has_ink": bool(len(xs)),
    }


def _strip_ground(svg_str):
    """The ground contact line is drawn under the subject by design; it is
    not part of the subject, so subject-hit metrics ignore it."""
    import re
    return re.sub(r'<g data-ground="1">.*?</g>', "", svg_str, flags=re.S)


def subject_iou(svg_str, truth_mask, dilate_px=6):
    """Subject hit: traced ink restricted to the art band (ground line
    excluded) vs a subject silhouette mask in image px, dilated by
    dilate_px page px (outlines sit just outside the fill). Reference
    metric on synthetic fixtures (true mask), reference-free on real
    photos (the GrabCut mask)."""
    ink = ink_of_svg(_strip_ground(svg_str))
    band = np.zeros_like(ink)
    x0, y0, x1, y1 = photolib.ART_BAND
    band[y0:y1, x0:x1] = 1
    ink_band = (ink > 0) & band
    truth_page = np.zeros_like(ink)
    ih, iw = truth_mask.shape
    s, ox, oy = photolib._page_fit(iw, ih)
    resized = cv2.resize(truth_mask, (int(iw * s), int(ih * s)),
                         interpolation=cv2.INTER_NEAREST)
    truth_page[int(oy):int(oy) + resized.shape[0],
               int(ox):int(ox) + resized.shape[1]] = (resized > 0)
    k = 2 * int(dilate_px) + 1
    truth_dil = cv2.dilate(truth_page.astype(np.uint8),
                           np.ones((k, k), np.uint8)) > 0
    hit = (ink_band & truth_dil).sum()
    union = ink_band.sum()
    return round(float(hit) / union, 3) if union else 0.0


def subject_ink_ratio(svg_str, photo_path):
    """Real-photo tier: share of traced ink inside the DILATED GrabCut
    subject mask (the same detection the trace used). 1.0 = every stroke
    belongs to the subject; low = background traced as splatter. None when
    no mask was detected."""
    gray, bgr = photolib.load_photo(photo_path)
    mask, label, _meta = photolib.detect_subject(gray, bgr)
    if mask is None:
        return None, label
    ih, iw = gray.shape
    s, _ox, _oy = photolib._page_fit(iw, ih)
    r = photolib._zone_radius(gray.shape, photolib.POLICIES[label], 1.0)
    return subject_iou(svg_str, mask, dilate_px=int(r * s) + 6), label


def real_photos(extra_dir=None):
    """[(name, path)]: the in-repo samples, then any photo in extra_dir."""
    out = []
    for d in (PHOTOS_DIR, extra_dir):
        if not d or not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            if f.lower().endswith(PHOTO_EXT):
                name = os.path.splitext(f)[0]
                if name not in {n for n, _ in out}:
                    out.append((name, os.path.join(d, f)))
    return out


# ---------------------------------------------------------------- harness
def run(styles, tmp, photos=()):
    rows = []
    for kind in FIXTURES:
        p = fixture_path(kind, tmp)
        truth = subject_truth(kind)
        for style in styles:
            svg = photolib.photo_to_svg(p, style=style, qa=False)
            m = metrics_for(svg)
            m["fixture"] = kind
            m["style"] = style
            if truth is not None:
                m["subject_hit_ratio"] = subject_iou(svg, truth)
            else:
                m["subject_hit_ratio"] = None
            rows.append(m)
    for name, path in photos:
        for style in styles:
            svg = photolib.photo_to_svg(path, style=style, qa=False)
            m = metrics_for(svg)
            m["fixture"] = f"photo:{name}"
            m["style"] = style
            m["subject_hit_ratio"] = None
            m["subject_ink_ratio"], m["label"] = subject_ink_ratio(svg, path)
            rows.append(m)
    return rows


def scorecard(rows):
    lines = ["# Photo-pipeline evaluation", "", "## Synthetic fixtures", "",
             "| fixture | style | strokes | slivers | regions | ink% | "
             "subject hit | print safe |",
             "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if r["fixture"].startswith("photo:"):
            continue
        lines.append(
            f"| {r['fixture']} | {r['style']} | {r['strokes']} | "
            f"{r['slivers']} | {r['regions']} | {r['ink_coverage_pct']} | "
            f"{r['subject_hit_ratio']} | {r['print_safe']} |")
    photo_rows = [r for r in rows if r["fixture"].startswith("photo:")]
    if photo_rows:
        lines += ["", "## Real photos (reference-free)", "",
                  "| photo | style | policy | strokes | slivers | regions | "
                  "ink% | subject ink | print safe |",
                  "|---|---|---|---|---|---|---|---|---|"]
        for r in photo_rows:
            lines.append(
                f"| {r['fixture'][6:]} | {r['style']} | {r['label']} | "
                f"{r['strokes']} | {r['slivers']} | {r['regions']} | "
                f"{r['ink_coverage_pct']} | {r['subject_ink_ratio']} | "
                f"{r['print_safe']} |")
    return "\n".join(lines) + "\n"


def check_bands(rows, bands):
    """Return list of violations against calibrated bands.
    Band keys: "fixture|style|metric" -> [low, high]."""
    bad = []
    for r in rows:
        for key, band in bands.items():
            parts = key.split("|")
            if len(parts) != 3:
                continue
            fname, mname, metric = parts
            if r["fixture"] != fname or r["style"] != mname:
                continue
            v = r.get(metric)
            if v is None:
                continue
            lo, hi = band
            if not (lo <= v <= hi):
                bad.append(f"{fname}:{mname} {metric}={v} outside [{lo}, {hi}]")
    return bad


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--styles", default="clean")
    ap.add_argument("--gate", action="store_true")
    ap.add_argument("--calibrate", action="store_true",
                    help="rewrite eval_bands.json from this run")
    ap.add_argument("--report", default=os.path.join(ROOT, "eval_report.md"))
    ap.add_argument("--photos", default=None,
                    help="extra directory of real photos (never committed)")
    ap.add_argument("--no-photos", action="store_true",
                    help="synthetic tier only")
    a = ap.parse_args(argv)
    styles = [s.strip() for s in a.styles.split(",") if s.strip()]
    photos = [] if a.no_photos else real_photos(a.photos)

    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        rows = run(styles, tmp, photos)

    report = scorecard(rows)
    with open(a.report, "w") as fh:
        fh.write(report)
    print(report)

    bands = {}
    if os.path.exists(BANDS_PATH):
        with open(BANDS_PATH) as fh:
            bands = json.load(fh)

    if a.calibrate:
        cal = {}
        for r in rows:
            for metric in ("strokes", "slivers", "ink_coverage_pct",
                           "subject_hit_ratio", "regions", "subject_ink_ratio"):
                v = r.get(metric)
                if v is None:
                    continue
                if metric in ("regions", "subject_ink_ratio") and \
                        not r["fixture"].startswith("photo:"):
                    continue                     # real-photo tier metrics
                key = f"{r['fixture']}|{r['style']}|{metric}"
                lo, hi = cal.get(key, (v, v))
                cal[key] = [min(lo, v), max(hi, v)]
        # tolerance margins: cross-version/platform float drift is real
        # (counts +-2, relative metrics +-12%); real photos have hundreds
        # of strokes riding on GrabCut + bilateral filtering, so their
        # counts get +-15% (min 3) and their ratios +-0.08
        for key, (lo, hi) in list(cal.items()):
            photo = key.startswith("photo:")
            if "slivers" in key or "strokes" in key or "regions" in key:
                pad = max(3, round(hi * 0.15)) if photo else 2
                cal[key] = [max(0, lo - pad), hi + pad]
                if "slivers" in key:
                    cal[key][0] = 0              # fewer slivers is never a regression
            elif "subject_ink_ratio" in key:
                cal[key] = [max(0.0, lo - 0.08), min(1.0, hi + 0.08)]
            else:
                pad = max(abs(lo), abs(hi)) * 0.12
                cal[key] = [lo - pad, hi + pad]
        with open(BANDS_PATH, "w") as fh:
            json.dump(cal, fh, indent=1)
        print(f"calibrated bands -> {BANDS_PATH}")
        return 0

    if a.gate and bands:
        bad = check_bands(rows, bands)
        for b in bad:
            print("OUT OF BAND:", b)
        if bad:
            return 1
        print("gate: all metrics in band")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
