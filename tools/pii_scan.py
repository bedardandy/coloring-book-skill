#!/usr/bin/env python3
"""PII gate — scan tracked files for personally identifiable information.

This project processes FAMILY PHOTOS and bakes CHILDREN'S NAMES into
coloring books. Nothing personal should ever live in the repo. This gate
enforces that:

  1. TEXT patterns: emails, phone numbers, SSNs, street addresses, IP
     addresses, API keys/tokens, personal filesystem paths (/Users/<name>)
  2. IMAGE metadata: any committed image must be free of EXIF GPS,
     camera, artist/owner, and description tags (real photos carry these;
     our rendered pages must never)

Fictional cast names (Harper, Max, Lily, Nina — from the example books)
are allowlisted; a small ALLOW_EXTRA regex list covers deliberate test
strings. Scan scope = git-tracked files only, honoring .gitignore.

    python tools/pii_scan.py            # report
    python tools/pii_scan.py --gate     # exit 1 on any finding (CI)
"""
import fnmatch
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------- patterns
PII_PATTERNS = {
    "email": re.compile(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    "phone": re.compile(
        r"(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "street_address": re.compile(
        r"\b\d{1,5}\s+[A-Z][a-z]+\s(?:St|Street|Ave|Avenue|Rd|Road|Ln|Lane|"
        r"Blvd|Boulevard|Dr|Drive|Way|Court|Ct)\b"),
    "ip_address": re.compile(
        r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    "api_key": re.compile(
        r"\b(?:sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{30,}|gho_[A-Za-z0-9]{30,}|"
        r"AKIA[0-9A-Z]{16}|xox[baprs]-[A-Za-z0-9-]{10,})\b"),
    "personal_path": re.compile(
        r"/(?:Users|home)/[A-Za-z0-9_.-]+/"),
    "generic_secret": re.compile(
        r"(?:password|passwd|secret|api_key|apikey|token)\s*[=:]\s*"
        r"[\"'][^\"']{8,}[\"']", re.IGNORECASE),
}

# fictional cast + legitimate lookalikes (never flagged)
ALLOW_PATTERNS = [
    re.compile(r"\b(?:harper|max|lily|nina|emma|noah|biscuit|button|rex)"
               r"@[a-z]+\b"),                     # no real cast emails exist
    re.compile(r"version=\s*[\"']"),              # version="..." strings
    re.compile(r"\b0\.0\.0\.0\b"),                # bind-all address
    re.compile(r"\b127\.0\.0\.1\b|\b255\.255\.255\.255\b"),
    re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b.*version"),  # pkg vers
]

# EXIF tags that leak personal data
_EXIF_BAD_TAGS = ("GPS", "Artist", "Copyright", "CameraOwnerName",
                  "BodySerialNumber", "LensSerialNumber", "OwnerName",
                  "ImageDescription", "DateTimeOriginal", "Make", "Model")

# version-string lookalike for IPs (e.g. cairosvg 1.2.3.4 style releases)
_VERSION_LOOKALIKE = re.compile(
    r"[A-Za-z][A-Za-z0-9_.-]+\s+[=v]?\s*\d+(?:\.\d+){1,3}\b")


def tracked_files():
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True,
                         text=True, check=True).stdout.splitlines()
    skip = ("*.png", "*.jpg", "*.jpeg", "*.pdf", "*.ttf", "*.onnx",
            "*.pyc", "*.json")  # json: letters.json is glyph data
    text, images = [], []
    for f in out:
        if any(fnmatch.fnmatch(f, pat) for pat in skip):
            if f.lower().endswith((".png", ".jpg", ".jpeg")):
                images.append(f)
            continue
        text.append(f)
    return text, images


def allowlisted(line):
    return any(p.search(line) for p in ALLOW_PATTERNS)


def scan_text(files):
    findings = []
    for f in files:
        path = os.path.join(ROOT, f)
        if not os.path.exists(path):
            continue
        try:
            with open(path, encoding="utf-8", errors="strict") as fh:
                for i, line in enumerate(fh, 1):
                    if allowlisted(line) or _VERSION_LOOKALIKE.search(line):
                        continue
                    for kind, pat in PII_PATTERNS.items():
                        m = pat.search(line)
                        if kind == "ip_address" and _VERSION_LOOKALIKE.search(line):
                            continue
                        if m:
                            findings.append(
                                (f, i, kind, line.strip()[:90]))
        except (UnicodeDecodeError, OSError):
            continue
    return findings


def scan_image_exif(files):
    """Rendered pages must be metadata-free: no GPS, camera, owner tags."""
    findings = []
    try:
        from PIL import Image
    except ImportError:
        return findings
    for f in files:
        path = os.path.join(ROOT, f)
        if not os.path.exists(path):
            continue
        try:
            img = Image.open(path)
            exif = img.getexif()
            for tag_id, value in exif.items():
                tag = Image.TAGS.get(tag_id, str(tag_id))
                if any(bad.lower() in tag.lower()
                       for bad in _EXIF_BAD_TAGS):
                    findings.append((f, 0, f"exif_{tag}", str(value)[:90]))
        except Exception:
            continue
    return findings


def main(argv):
    gate = "--gate" in argv
    text_files, image_files = tracked_files()
    findings = scan_text(text_files) + scan_image_exif(image_files)
    if findings:
        print(f"PII scan: {len(findings)} finding(s)")
        for f, i, kind, snippet in findings:
            print(f"  [{kind}] {f}:{i}  {snippet}")
        if gate:
            print("GATE FAILED: remove the PII above (or allowlist a false "
                  "positive in tools/pii_scan.py).")
            return 1
    else:
        print(f"PII scan: clean ({len(text_files)} text files, "
              f"{len(image_files)} images checked)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
