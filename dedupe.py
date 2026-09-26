"""
Is this photograph already in the gallery?

    python3 dedupe.py ~/new-photos/*.jpg

Maddy sends photographs in batches from her camera roll and does not track
what she has already sent. Four batches in, three of them contained sets
that were already up — one batch was three repeats out of five.

A file hash does not catch this. The re-sends are re-exports: same
photograph, different bytes, different hash. Twice a hash check said "all
new" and only looking at the images side by side caught it. A hash proves
two files are the same; it can never prove they are different.

So this compares what the picture LOOKS like, with a difference hash:
shrink to 9x8 greyscale, record whether each pixel is brighter than the one
to its right, and keep those 64 bits. That describes the image's structure
rather than its bytes, so it survives re-export, re-compression and
resizing — which is what a camera roll and a messaging app do to a photo
on its way here.

WHAT IT COMPARES AGAINST, AND WHY IT MATTERS
The files in photos/ are square CROPS. A candidate arrives as the full
frame. Comparing the two directly does not work — the first version of
this script did exactly that and cheerfully passed a re-send whose source
file was byte-identical to one already up, because the crop had thrown
away half the picture. Cropping changes structure, and structure is the
whole basis of the comparison.

So photos/sources.json records the fingerprint of the ORIGINAL photograph
each crop was made from, and candidates are compared against those:
full frame against full frame, like for like. Add a photograph, add its
source fingerprint — build_site.py will not do it for you, and a missing
entry silently weakens this check rather than breaking it.

Distance is the number of differing bits. Re-exports of the same
photograph land near zero; genuinely different sets sit far higher. The
threshold is deliberately loose — a false "possible repeat" costs ten
seconds of looking, a missed repeat costs a round trip to Maddy, a wasted
crop, and the chance of the same set appearing twice on the live page.
"""

import json
import pathlib
import sys

from PIL import Image, ImageOps

import config as C

ROOT = pathlib.Path(__file__).parent
PHOTOS = ROOT / "photos"
SOURCES = PHOTOS / "sources.json"

# Measured, not guessed. Across the four batches every confirmed re-send
# scored exactly 0 — a re-export changes the bytes but not the picture. The
# closest pair of genuinely DIFFERENT sets scored 13 (work-02 and work-09,
# which share a pale hand on a dark background and nothing else).
#
# 8 sits with eight bits of room above the repeats and five below the
# nearest true pair. An earlier value of 12 left a one-bit margin, which is
# not a margin — it is a coincidence waiting to reject a real photograph.
# Re-run the spread check after adding photos; if a true pair ever drops
# near this, lower it rather than living with the false rejection.
THRESHOLD = 8


def dhash(path, size=8):
    """64-bit difference hash: is each pixel brighter than its right neighbour?"""
    im = ImageOps.exif_transpose(Image.open(path)).convert("L")
    im = im.resize((size + 1, size), Image.LANCZOS)
    px = list(im.getdata())
    bits = 0
    for row in range(size):
        for col in range(size):
            a = px[row * (size + 1) + col]
            b = px[row * (size + 1) + col + 1]
            bits = (bits << 1) | (a > b)
    return bits


def distance(a, b):
    return bin(a ^ b).count("1")


def main(paths):
    if not SOURCES.exists():
        print(f"{SOURCES} is missing — nothing to compare against.")
        return 2
    # A null value means the original full frame is not available, so there is
    # nothing honest to compare against. Those files stay out of `known` and
    # fall into `blind` below, which is exactly where they belong: named, and
    # reported as uncovered. Writing a hash of the square crop instead would
    # look right and never match — measured 10-21 bits away from the real
    # originals on the eighteen we do have.
    known = {k: int(v, 16)
             for k, v in json.loads(SOURCES.read_text()).items() if v is not None}

    gallery = [x["file"] for x in C.OUTSTANDING["gallery"]]
    blind = [f for f in gallery if f not in known]

    print(f"{len(paths)} candidate(s) against {len(known)} known originals")
    if blind:
        print(f"no source on file for {', '.join(blind)} — a repeat of those "
              f"will not be caught here, check those by eye")
    print()

    fresh, repeats = [], []
    for raw in paths:
        p = pathlib.Path(raw)
        if not p.exists():
            print(f"  ? {p.name} — not found")
            continue
        h = dhash(p)
        d, name = min((distance(h, k), n) for n, k in known.items())
        if d <= THRESHOLD:
            print(f"  ✗ {p.name} — already up as {name} (distance {d})")
            repeats.append(p)
        else:
            print(f"  ✓ {p.name} — new (nearest {name}, distance {d})")
            fresh.append(p)

    print()
    print(f"{len(fresh)} new, {len(repeats)} already up.")
    for p in fresh:
        print(f"  {p}")
    if blind:
        print("\nRemember the blind spots listed above before trusting a clean run.")
    return 0


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not args:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(args))
