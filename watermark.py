"""
Stamp the wordmark and the address onto Maddy's photographs.

Her work gets reposted. Once an image is off this page — saved, screenshotted,
shared into a group chat — nothing but the pixels says whose hands did it. A
watermark is the only part of the site that survives that journey.

This runs at BUILD TIME, on the way from photos/ to public/img/. The files in
photos/ stay clean masters. That matters for two reasons: the stamp can be
redesigned without re-cropping nineteen photographs, and dedupe.py still
compares candidates against unmarked originals.

The mark is white-out: the favicon monogram locked up with the wordmark,
every shape one colour, nothing pink. The pink wordmark had to sit against
nineteen different palettes and lost against most of them; a single colour
at low opacity sits on anything. The monogram earns its place because a
script face turns to mush at the size a watermark should be, and one letter
does not.

It is drawn twice: a tight dark shadow, then the mark over it. White on a
sunlit pale hand is invisible without that, and pale hands in daylight are
most of this gallery. The shadow is tight and strong rather than a soft
glow — a glow washes out against a bright background exactly when needed.

The URL is the part that actually earns its place. A logo tells someone it is
a brand; the address tells them where to book.
"""

import pathlib

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageStat

ROOT = pathlib.Path(__file__).parent
BRAND = ROOT / "brand"

URL = "nailsbymaddy.co.uk"

# "brand"    = the logo in colour, picking the reversed or primary colourway
#              to suit whatever it lands on.
# "wordmark" = the same logo, mono white.
# "icon"     = the M monogram.
# One or the other, never both — two marks on one photograph is a signature
# with a second signature under it.
#
# The wordmark is the logo as signed off, and it is used unaltered. Her
# brand guidelines are explicit: "logo never re-typed", clear space equal to
# the height of the M, minimum 28 mm / 110 px.
#
# An earlier version of this file cut the NAILS BY line out of the mark
# because it measured badly at the size I had picked. That was re-typing the
# logo — the exact thing the guidelines forbid — and it deleted the name of
# the business from her own photographs to save a few pixels. The size is
# the variable here. The logo is not.
#
# The monogram stays available for genuinely small applications, which is
# what an icon is for, but it is not a substitute for the name on work that
# gets reposted.
MARK = "brand"

# Fractions of image width, so a stamp looks the same on any size.
# The lockup is far wider than the old stacked wordmark, so a smaller
# fraction of the width still reads — and the brief was smaller.
# Per mark, because they are shaped differently: the wordmark is a wide
# band, the monogram is nearly square and needs less width to read.
# 0.26 puts the logo at 312px on a 1200px image — 2.8x her 110px minimum,
# and 281px at Instagram size, still 2.5x. At that size NAILS BY has a
# 12.9px cap height and reads properly, which at 0.20 (9.9px, tracked out
# at 380) it did not.
MARK_WIDTH = {"icon": 0.085, "wordmark": 0.26, "brand": 0.26}
MARGIN = 0.034
# 0.022 of the width — 26px on a 1200px image, an 11px x-height. Measured
# rather than judged: that survives to 1080px (Instagram) still readable.
# It cannot survive to a 170px gallery tile, and nothing can — nineteen
# characters do not fit legibly across 170px at any size. The stamp exists
# for the copy someone saves or reposts, not for the thumbnail on the page.
URL_SIZE = 0.022

# Kept high on purpose, and it is worth knowing why, because "more
# transparent" sounds like the obvious way to make a watermark subtle and
# here it is the opposite. These strokes are thin. Drop the mark to 155 and
# the photograph shows through every one of them, so white stops being white
# and the whole lockup reads as grey smudge — louder, not quieter, because
# the eye catches dirt faster than it catches a clean shape. Subtlety comes
# from the mark being SMALL and one colour, not from being see-through.
# Full strength for the brand colourways: this is her logo in her colour,
# not a smudge to be half-hidden.
MARK_ALPHA = 255 if MARK == "brand" else 215

# No grey. The logo carries its own offset shadow — white on the reversed
# variant, Ink on the primary — and that shadow IS the outline. Adding a
# grey glow on top was me inventing a treatment the brand does not have,
# and it dulled the pink. Left at 0 for the brand colourways; the mono
# white mark still wants a little, since it has no shadow of its own.
SHADOW_ALPHA = 0.0 if MARK == "brand" else 0.5
HALO_DILATE = 7
HALO_BLUR = 2

_cache = {}


def _assets():
    """Load the chosen mark and the brand face once per run."""
    if not _cache:
        stems = (["brand-dark", "brand-light"] if MARK == "brand" else [MARK])
        mark_path = BRAND / f"photo-mark-{stems[0]}.png"
        font_path = BRAND / "outfit-600.ttf"
        if not mark_path.exists() or not font_path.exists():
            raise SystemExit(
                f"watermark assets missing — expected {mark_path} and {font_path}. "
                f"Run tools/build_brand_assets.py to regenerate them."
            )
        for stem in stems:
            f = BRAND / f"photo-mark-{stem}.png"
            if not f.exists():
                raise SystemExit(f"watermark asset missing: {f}")
            m = Image.open(f).convert("RGBA")
            _cache[stem] = m.crop(m.getchannel("A").getbbox())
        _cache["mark"] = _cache[stems[0]]
        _cache["font_path"] = str(font_path)
    return _cache


def _clearest_corner(im, box):
    """Top-left coordinate of whichever corner has least going on.

    A fixed bottom-right corner lands on the nails about a third of the
    time, which is the one thing a mark on this page must not do: the nails
    are the product. So each corner is scored and the quietest wins.

    Two signals, because either alone is fooled by these photographs:

      edges      nails are sharp — a painted tip, a French line, the rim of
                 a gel dome. Skin and blurred background are smooth. This
                 does most of the work.
      saturation the art is colourful and skin is not, so this catches a
                 glossy red nail that is large, smooth and low on edges
                 while still being the last place to put a signature.

    Both are measured on a downscaled copy: the decision is about broad
    areas, and it keeps nineteen photographs quick to stamp.
    """
    W, H = im.size
    bw, bh = box
    mx, my = int(W * MARGIN), int(H * MARGIN)

    small = im.convert("RGB").resize((W // 4, H // 4), Image.BILINEAR)
    edges = small.convert("L").filter(ImageFilter.FIND_EDGES)
    sat = small.convert("HSV").getchannel("S")

    corners = {
        "bottom-right": (W - bw - mx, H - bh - my),
        "bottom-left": (mx, H - bh - my),
        "top-right": (W - bw - mx, my),
        "top-left": (mx, my),
    }

    # A little breathing room around the mark, so it is judged on the space
    # it will actually occupy rather than on its exact bounding box.
    pad = int(min(bw, bh) * 0.25)

    best, best_score = None, None
    for name, (x, y) in corners.items():
        crop = (max(0, (x - pad) // 4), max(0, (y - pad) // 4),
                min(W // 4, (x + bw + pad) // 4), min(H // 4, (y + bh + pad) // 4))
        if crop[2] - crop[0] < 2 or crop[3] - crop[1] < 2:
            continue
        e = ImageStat.Stat(edges.crop(crop)).mean[0]
        sr = ImageStat.Stat(sat.crop(crop)).mean[0]
        # Edges dominate; saturation is a tiebreaker weighted to matter only
        # when it is high. Scaled so the two are roughly comparable.
        score = e + sr * 0.12
        if best_score is None or score < best_score:
            best, best_score = (x, y), score
    return best


def stamp(im):
    """Return a copy of `im` with the wordmark and address in the corner."""
    a = _assets()
    mark_src = a["mark"]

    im = im.convert("RGBA")
    W, H = im.size

    w = int(W * MARK_WIDTH[MARK])
    h = max(1, round(mark_src.height * w / mark_src.width))

    size = max(8, int(W * URL_SIZE))
    font = ImageFont.truetype(a["font_path"], size)
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    tw = int(probe.textlength(URL, font=font))
    th = int(size * 1.25)
    gap = int(H * 0.012)
    box = (max(w, tw), h + gap + th)

    x, y = _clearest_corner(im, box)

    # Which colourway. The brand pack has two for exactly this reason: the
    # reversed logo carries a white shadow, white NAILS BY and white
    # sparkles and is made for dark ground; the primary carries them in Ink
    # and is made for light. Stamping one of them everywhere is what made
    # the white half disappear on a sunlit hand — the answer was never to
    # add a grey glow under the logo, it was to use the variant the
    # guidelines already provide for that background.
    if MARK == "brand":
        patch = im.convert("L").crop((x, y, x + box[0], y + box[1]))
        light = ImageStat.Stat(patch).mean[0] > 128
        mark_src = a["brand-light" if light else "brand-dark"]
        url_fill = (20, 20, 20, 255) if light else (255, 255, 255, 255)
    else:
        url_fill = (255, 255, 255, 255)

    mark = mark_src.resize((w, h), Image.LANCZOS)
    layer = Image.new("RGBA", box, (0, 0, 0, 0))
    layer.paste(mark, ((layer.width - w) // 2, 0), mark)
    ImageDraw.Draw(layer).text(
        ((layer.width - tw) // 2, h + gap), URL, font=font, fill=url_fill
    )

    # Shadow pass — a halo OUTSIDE the glyphs, never underneath them.
    #
    # The first version blurred the mark and laid the result under it. That
    # greys the mark: the strokes are semi-transparent, so a black shadow
    # sitting directly beneath shows straight through and white stops being
    # white. Subtracting the mark's own alpha from the blurred copy leaves
    # only the halo around the edges, which is what gives separation on a
    # pale hand while the strokes stay the colour they were drawn.
    placed = Image.new("RGBA", im.size, (0, 0, 0, 0))
    placed.paste(layer, (x, y), layer)
    own = placed.getchannel("A")
    # Dilate FIRST, then blur, then subtract the glyphs. Blurring on its own
    # spreads the halo inward as well as outward, and on strokes this thin
    # "inward" is most of the stroke — which is how the previous attempt
    # still came out grey even after the subtraction.
    halo = own.filter(ImageFilter.MaxFilter(HALO_DILATE))
    halo = halo.filter(ImageFilter.GaussianBlur(HALO_BLUR))
    halo = ImageChops.subtract(halo, own)
    shadow = Image.new("RGBA", im.size, (0, 0, 0, 0))
    shadow.putalpha(halo.point(lambda v: int(v * SHADOW_ALPHA)))
    im = Image.alpha_composite(im, shadow)

    # Mark pass.
    layer.putalpha(layer.getchannel("A").point(lambda v: int(v * MARK_ALPHA / 255)))
    top = Image.new("RGBA", im.size, (0, 0, 0, 0))
    top.paste(layer, (x, y), layer)
    return Image.alpha_composite(im, top).convert("RGB")


def stamp_file(src, dest, quality=82):
    stamp(Image.open(src)).save(
        dest, "JPEG", quality=quality, optimize=True, progressive=True
    )
