#!/usr/bin/env python3
"""
Favicon set. Writes /favicon.svg, /favicon-32.png, /apple-touch-icon.png (180) and
/icon-512.png at the repo root.

A navy square with the initials in white. It is the same navy as the site header and
the social cards, which is the whole point: the tab, the bookmark, the share preview
and the page itself should look like one thing. The SVG is authored by hand so it is
a few hundred bytes and stays crisp at any size; the PNGs exist because Safari and
older Android ignore SVG icons.
"""

import os

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAVY = "#12467f"
SF = "/System/Library/Fonts/SFNS.ttf"

SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
<rect width="64" height="64" rx="10" fill="%s"/>
<text x="32" y="43.5" font-family="-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif" font-size="31" font-weight="640" fill="#fff" text-anchor="middle" letter-spacing="-1.2">AC</text>
</svg>
""" % NAVY


def png(size, path, radius_frac=0.16):
    # Drawn at 8x and downsampled, because a rounded corner rasterised directly at
    # 32 pixels is visibly stepped.
    s = size * 8
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, s - 1, s - 1], radius=int(s * radius_frac), fill=NAVY)
    f = ImageFont.truetype(SF, int(s * 0.49))
    try:
        f.set_variation_by_axes([100, 96, 400, 640])
    except Exception:
        pass
    box = d.textbbox((0, 0), "AC", font=f)
    d.text(((s - (box[2] - box[0])) / 2 - box[0],
            (s - (box[3] - box[1])) / 2 - box[1]), "AC", font=f, fill="#ffffff")
    im.resize((size, size), Image.LANCZOS).save(path, "PNG", optimize=True)
    return path


open(os.path.join(ROOT, "favicon.svg"), "w").write(SVG)
print("wrote favicon.svg")
for size, name in ((32, "favicon-32.png"), (180, "apple-touch-icon.png"),
                   (512, "icon-512.png")):
    # Apple's icon is composited onto a home screen tile, so it gets square corners
    # and iOS applies the mask itself; a pre-rounded one shows a dark halo.
    print("wrote", os.path.basename(
        png(size, os.path.join(ROOT, name),
            radius_frac=0.0 if name == "apple-touch-icon.png" else 0.16)))
