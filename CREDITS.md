# Credits & licenses

The shape-cookbook recipes (`reference/shape-cookbook.md`) and the object helpers
in `lib/charlib.py` (`car_side`, `pickup_truck`, `tractor`, `train_engine`,
`bicycle`, `house`, `tree_round`, `tree_pine`, `horse`, `bird_side`, `swing_set`)
were derived from **relative proportions** observed in the sources below. No path
data, `d`-strings, or literal illustrations were copied — every object is redrawn
from scratch with `charlib` primitives. Drawing *methods* (which shapes go where,
in what ratio) are not copyrightable (17 USC 102(b), *Baker v. Selden*); the
recipes are our own prose expression of public techniques.

| Source | License | How used |
|---|---|---|
| **Tabler Icons** (github.com/tabler/tabler-icons) | MIT | Skeletal proportion reference for car, truck, tractor, train, bike, home, tree, cat, horse, fish, sailboat, armchair, table. Icons inspected at 24×24; only ratios were carried over. |
| **Lucide Icons** (github.com/lucide-icons/lucide) | ISC | Cross-check proportions for bird, sailboat, tent/pine, truck, fish. |
| **E. G. Lutz**, *Drawing Made Easy* (1921) & *What to Draw and How to Draw It* (1913) | Public domain | Construction phrasing / "shape-recipe" method for vehicles, houses, and the horse (four-posts-under-a-barrel legs, arched neck). |
| **Google QuickDraw** (quickdraw.withgoogle.com) | CC-BY 4.0 | Reference ONLY, for part-relationships and proportions (which parts touch, relative sizes). No stroke data bundled or redistributed. |

| **Twemoji** (github.com/jdecked/twemoji) | CC-BY 4.0 | Proportion reference for the 2026-07 helper batch: rocket, elephant, fire/police/ambulance, rainbow, present, pumpkin, airplane, giraffe, penguin, ringed planet, balloon, pig, anchor, octopus, whale, shield. Ratios only; no path data copied. Attribution: "Includes proportions referenced from Twemoji (CC-BY 4.0)." (CC-BY 4.0 is one-way compatible with GPLv3-family licensing per Creative Commons.) |
| **Phosphor Icons** (github.com/phosphor-icons/core) | MIT | Stroke skeleton reference for the excavator (bulldozer.svg). |
| **Andika** (SIL International, via google/fonts) | SIL OFL 1.1 (`assets/fonts/OFL.txt`) | Glyph outlines for the colorable letters/words kit (`lib/letters.json`, built by `tools/build_font.py`). Andika is designed for early-literacy teaching. Outlines only are bundled; the font program itself ships alongside for regeneration. Andika now renders ALL page text too (titles, captions, page numbers via `charlib.text_path()`), so output no longer depends on the host's installed fonts. |

Avoided entirely for the LIBRARY (helpers, recipes, fonts): OpenClipart
(quality/provenance lottery), Streamline (terms forbid asset-library bundling),
any CC-BY-SA source (OpenMoji and derivatives — share-alike contamination risk),
and personal-use-only galleries (supercoloring, wikiHow). The two sample
PHOTOS below are share-alike licensed; they are test inputs and showcase
subjects, not library code, and carry their own attribution.

## 2026-07 quality-research additions
- Twemoji (CC-BY 4.0): proportion references for future object helpers come from the
  maintained fork `jdecked/twemoji` (the archived `twitter/twemoji` serves stale
  content). Attribution: "Includes proportions referenced from Twemoji (CC-BY 4.0)."
- Phosphor Icons (MIT): bulldozer/crane stroke skeletons.
- Craft-rule research (line hierarchy, region floors, print specs) synthesized from
  public publisher/print guidance; methods and facts, no copied expression.

## 2026-08 photo-pipeline additions
- OpenCV (`opencv-python-headless`, Apache-2.0): GrabCut subject segmentation,
  morphology, contour tracing for `lib/photolib.py`.
- YuNet face detection model (opencv_zoo, Apache-2.0, `assets/models/`):
  bundled ~230KB ONNX for local, offline face detection driving the
  `face`/`person` photo policies. OpenCV 5 removed Haar cascades; YuNet is
  the supported detector. No photo leaves the machine.

## 2026-09 sample photos (`assets/photos/`)
Real photographs used by the evaluation gate (`tools/eval_photo.py`, real-photo
tier) and, for the dog, by the showcase pages `17-photo` / `18-photo-sketch`.
Both are Wikimedia Commons files; EXIF/APP segments were stripped losslessly
(pixels untouched) so the PII gate stays clean. The pipeline never uploads
them; no photo of a child is in the repo.

| File | Source | Author | License |
|---|---|---|---|
| `dog.jpg` | [File:Agnes the Golden Retriever.jpg](https://commons.wikimedia.org/wiki/File:Agnes_the_Golden_Retriever.jpg) (1280px thumbnail), Wikimedia Commons, own work, 6 June 2015 | Golden Retriever Raseåd | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) |
| `teddy.jpg` | [File:Teddy bear produced in 1903 face detail, from- Teddy bear early 1900s - Smithsonian Museum of Natural History (cropped).jpg](https://commons.wikimedia.org/wiki/File:Teddy_bear_produced_in_1903_face_detail,_from-_Teddy_bear_early_1900s_-_Smithsonian_Museum_of_Natural_History_(cropped).jpg), Wikimedia Commons crop of a [Flickr photo](https://www.flickr.com/photos/23165290@N00/7237653442/) | Flickr user 23165290@N00, credited as "Smithsonian Museum of Natural History" | [CC BY-SA 2.0](https://creativecommons.org/licenses/by-sa/2.0/) |

Attribution lines for derived pages: "Agnes the Golden Retriever by Golden
Retriever Raseåd, CC BY-SA 4.0, via Wikimedia Commons" and "Teddy bear early
1900s, Smithsonian Museum of Natural History, CC BY-SA 2.0, via Wikimedia
Commons / Flickr". The traced showcase pages are derivatives of the dog photo
and are shared under the same CC BY-SA 4.0 terms.
