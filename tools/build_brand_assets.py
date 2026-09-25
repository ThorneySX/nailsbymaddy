"""
Regenerate the derived files in brand/ that watermark.py needs.

Both are derived, not authored, so they are rebuilt from the sources in the
brand pack rather than edited by hand:

  photo-mark-*.png  the two white marks, rasterised from their authored
                    SVGs; watermark.MARK picks which one is stamped.
  outfit-600.ttf  the site's own face, decompressed from woff2 because
                  Pillow cannot load woff2 and the address on a photograph
                  should be set in the same type as the address on the page.

    python3 tools/build_brand_assets.py
"""
import pathlib
import re
import sys

import cairosvg
from fontTools.ttLib import TTFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
BRAND = ROOT / "brand"
BRAND.mkdir(exist_ok=True)

# Two photo marks, each authored as an SVG and only rasterised here:
#
#   photo-mark-icon.svg      the favicon's M and sparkle, no disc, no shadow
#   photo-mark-wordmark.svg  NAILS BY over Maddy, no drop shadow
#
# Only one is ever stamped on a photograph — watermark.MARK picks which.
# Both are pure white by design: the pink wordmark had to sit against
# nineteen different palettes and lost against most of them, and one colour
# at one opacity sits on anything. A stray fill here would print onto every
# photograph, so it is refused rather than warned about.
for stem, width in (("photo-mark-icon", 900), ("photo-mark-wordmark", 1600),
                    ("photo-mark-brand-dark", 1600), ("photo-mark-brand-light", 1600)):
    src = BRAND / f"{stem}.svg"
    if not src.exists():
        sys.exit(f"{src} is missing — it is the authored source for that mark.")
    mark = src.read_text()
    # Only brand colours may reach a photograph. White-out marks are white
    # alone; the two brand colourways add Polish Pink and, on the light-
    # background variant, Ink.
    allowed = r'#FFFFFF|#fff|white'
    if stem.startswith('photo-mark-brand'):
        allowed += r'|#E8378A' + (r'|#141414' if stem.endswith('-light') else '')
    stray = re.search(rf'fill="(?!{allowed})([^"]+)"', mark, re.I)
    if stray:
        sys.exit(
            f"{src.name} contains fill={stray.group(1)!r}, which is not white. "
            f"Photo marks carry brand colours only."
        )
    cairosvg.svg2png(bytestring=mark.encode(), write_to=str(BRAND / f"{stem}.png"),
                     output_width=width)

font = TTFont(ROOT / "public" / "fonts" / "outfit-latin-600-normal.woff2")
font.flavor = None
font.save(str(BRAND / "outfit-600.ttf"))

print(f"wrote photo-mark-icon.png, photo-mark-wordmark.png and outfit-600.ttf in {BRAND}")
