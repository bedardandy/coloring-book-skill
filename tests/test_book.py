"""End-to-end smoke: the bundled example book must build and validate."""
import os
import subprocess
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXAMPLE = os.path.join(REPO, "examples", "where-is-button")
PY = sys.executable


@pytest.mark.slow
def test_example_book_builds_and_validates(tmp_path):
    env = dict(os.environ)
    r = subprocess.run([PY, "make_book.py"], cwd=EXAMPLE, env=env,
                       capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stderr
    pdf = os.path.join(EXAMPLE, "Harper-Coloring-Book.pdf")
    assert os.path.exists(pdf)

    pages = sorted(p for p in os.listdir(os.path.join(EXAMPLE, "pages"))
                   if p.endswith(".svg"))
    assert len(pages) == 10

    v = subprocess.run([PY, "-m", "lib.validate"] +
                       [os.path.join(EXAMPLE, "pages", p) for p in pages],
                       cwd=REPO, capture_output=True, text=True, timeout=300)
    assert v.returncode == 0, v.stdout + v.stderr


def test_validator_cli_exit_codes(tmp_path):
    from charlib import spage, C, name_trace_page
    good = tmp_path / "good.svg"
    bad = tmp_path / "bad.svg"
    good.write_text(name_trace_page(["Max"]))
    bad.write_text(spage("B", C(400, 1035, 60)))
    r_good = subprocess.run([PY, "-m", "lib.validate", str(good)],
                            cwd=REPO, capture_output=True)
    r_bad = subprocess.run([PY, "-m", "lib.validate", str(bad)],
                           cwd=REPO, capture_output=True)
    assert r_good.returncode == 0
    assert r_bad.returncode == 1
