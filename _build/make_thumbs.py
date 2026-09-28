#!/usr/bin/env python3
"""
NOT PART OF THE BUILD ANY MORE. Nothing on the site references its output.

The publication list used to show a cropped figure from each paper in its right-hand
column. Two designs were tried and both failed: the whole figure letterboxed into 4:3
was mostly white space at 176px, and the tighter crop of the one legible sub-region was
legible and still meaningless, because a fragment of a system diagram drawn for someone
who has read the paper does not tell a stranger what the paper did. That column is now
result_panel() in build.py, a small chart drawn from _build/headline.json.

This script is kept, and its output kept under _work/orphaned_thumbs/, because it is the
only record of how the crops were recovered: the three coordinate spaces below, the ratio
measured off the rendered page rather than assumed from the DPI, and the two boxes that
had to be recovered by cross-correlation. If a figure ever needs cutting again, start
here rather than from nothing. Output goes to _work/, which is gitignored, so running it
cannot put unreferenced images back into the published tree.

Why it renders from the PDF rather than the published figures: the first pass cut the
thumbnails out of the already
published figure images in assets/img/figs, which are 300 DPI crops. At 300 DPI the
smallest chosen crop is only 256 pixels wide, so the 2x file was an upscale of an
upscale and the small type inside it went to mush. This script goes back to the PDF
and re-renders the page at 600 DPI, so every 2x file below is native pixels and not
interpolation.

Three coordinate spaces are in play. Keeping them straight is the whole job:

  1. figspec space   the 110 DPI page render the figure boxes were first read off.
                     _work/figspec.json stores [page, x0, y0, x1, y1, w, h] there.
  2. figure space    the 300 DPI figure images in assets/img/figs. This is the space
                     the thumbnail boxes in _work/thumb_result.json are expressed in,
                     because that is what the crop-picking pass looked at.
  3. render space    the 600 DPI page render this script makes. Everything is scaled
                     into it by exact ratios measured from the rendered file, never
                     by an assumed DPI, because pdftoppm rounds page size to whole
                     pixels and letter and A4 round differently.
"""

import json
import os
import subprocess
import tempfile

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "_work", "orphaned_thumbs", "thumbs")
FIGS = os.path.join(ROOT, "assets", "img", "figs")
os.makedirs(OUT, exist_ok=True)

PAPERS = json.load(open(os.path.join(ROOT, "_build", "papers.json")))["papers"]
CONTENT = json.load(open(os.path.join(ROOT, "_build", "content.json")))
SPEC = json.load(open(os.path.join(ROOT, "_work", "figspec.json")))
PICKED = json.load(open(os.path.join(ROOT, "_work", "thumb_result.json")))

# The published sizes. 240x180 is the largest 4:3 box every crop can fill with real
# pixels at 600 DPI: the two tightest crops are 256x192 in figure space, which is
# 512x384 here, just over the 480x360 the 2x file needs. Going larger would start
# upscaling those two again, which is the defect this file was written to remove.
#
# 80x60 is the second pair, for the "What I work on" rail on the homepage. That rail
# is an index, not a reading surface: the job of the picture there is to let a reader
# recognise a paper they have already seen further down the page, so it needs shape
# and colour and not legible type. It is a separate file rather than the 240 one
# scaled down in CSS, because sending 13 copies of a 240x180 to draw 13 80x60 boxes
# is nine times the pixels for nothing.
SIZES = ((80, 60), (160, 120), (240, 180), (480, 360))

# One crop was rejected by the verification pass: it read as the middle of a larger
# figure that had been cut through its own content. This box is the replacement,
# chosen because it keeps the Server cloud, both Controller blocks and the
# Controller-1 label whole. Alt text is written here rather than inherited, because
# the rejected crop never got any.
REPLACE = {
    # wdrass has no entry on purpose. Its figure is a 4:1 pipeline with two rows of
    # boxes that are offset from each other, so no vertical cut is clean in both
    # rows: the one that clears the bottom row's "documents" box lands inside the
    # top row's "sentence splitter" box, and vice versa. Four candidates were
    # rendered at 240x180 and compared; the original box wins because the only thing
    # it clips is a thin orange edge with no text in it, which reads as a figure
    # continuing past the frame rather than as a mistake.
    "2112.06135": {
        "box": [391, 0, 735, 258],
        "motif": "the server and the two Controller layers it exchanges with",
        "alt": "A cloud labelled Server, with dashed arrows to two small blue "
               "Controller blocks sitting between the layers of a client network.",
    },
}

def pdf_path(img):
    """The master PDF for an image id. papers.json names the master copy in
    pdf_local, which is not derivable from the image id for the two papers that did
    not come from arXiv, so read it rather than guessing."""
    for p in PAPERS:
        if p["img"] == img:
            f = os.path.join(ROOT, "assets", "pdf", p["pdf_local"])
            return f if os.path.exists(f) else None
    return None


def render(pdf, page, dpi=600):
    with tempfile.TemporaryDirectory() as td:
        base = os.path.join(td, "p")
        subprocess.run(["pdftoppm", "-r", str(dpi), "-f", str(page), "-l", str(page),
                        "-png", pdf, base], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        f = [x for x in os.listdir(td) if x.endswith(".png")][0]
        return Image.open(os.path.join(td, f)).convert("RGB")


def main():
    out = {}
    rows = []
    for entry in PICKED["shipped"] + PICKED["rejected"]:
        img = entry["img"]
        if img not in SPEC:
            print("SKIP %s: no page spec, cannot re-render" % img)
            continue
        rep = REPLACE.get(img, {})
        box = rep.get("box", entry["box"])
        alt = rep.get("alt", entry.get("alt"))
        motif = rep.get("motif", entry.get("motif"))
        if not alt:
            print("SKIP %s: no alt text, a thumbnail without one is not shippable" % img)
            continue

        page, fx0, fy0, fx1, fy1, sw, sh = SPEC[img]
        pdf = pdf_path(img)
        if not pdf:
            print("SKIP %s: no master PDF found" % img)
            continue
        pg = render(pdf, page)

        # figspec space -> render space, by measured ratio.
        rx, ry = pg.width / float(sw), pg.height / float(sh)
        fig = pg.crop((int(round(fx0 * rx)), int(round(fy0 * ry)),
                       int(round(fx1 * rx)), int(round(fy1 * ry))))

        # figure space -> this render, by the width of the published figure.
        pub = Image.open(os.path.join(FIGS, "%s.jpg" % img))
        k = fig.width / float(pub.width)
        l, t, r, b = [int(round(v * k)) for v in box]
        l, t = max(0, l), max(0, t)
        r, b = min(fig.width, r), min(fig.height, b)
        crop = fig.crop((l, t, r, b))

        # Force exact 4:3 by trimming the long side from the centre, so no file is
        # ever letterboxed or squashed to fit the fixed box the layout reserves.
        w, h = crop.size
        if abs(w / float(h) - 4 / 3.0) > 0.005:
            if w / float(h) > 4 / 3.0:
                nw = int(round(h * 4 / 3.0))
                off = (w - nw) // 2
                crop = crop.crop((off, 0, off + nw, h))
            else:
                nh = int(round(w * 3 / 4.0))
                off = (h - nh) // 2
                crop = crop.crop((0, off, w, off + nh))

        native = crop.size
        for tw, th in SIZES:
            im = crop.resize((tw, th), Image.LANCZOS)
            im.save(os.path.join(OUT, "%s-%dx%d.jpg" % (img, tw, th)),
                    "JPEG", quality=88, optimize=True, progressive=True)
            im.save(os.path.join(OUT, "%s-%dx%d.webp" % (img, tw, th)),
                    "WEBP", quality=86, method=6)
        crop.save(os.path.join(ROOT, "_work", "thumb_native_%s.png" % img))

        out[img] = {"alt": alt, "box": box, "motif": motif}
        rows.append((img, native, native[0] / float(SIZES[-1][0])))

    with open(os.path.join(OUT, "..", "thumbs.json"), "w") as fh:
        json.dump(out, fh, indent=1, sort_keys=True, ensure_ascii=False)
        fh.write("\n")

    print("%d thumbnails at %s" % (len(out), " and ".join("%dx%d" % s for s in SIZES)))
    for img, native, ratio in sorted(rows, key=lambda x: x[2]):
        flag = "  UPSCALED" if ratio < 1 else ""
        print("  %-12s native %4dx%-4d  %.2fx the 2x file%s"
              % (img, native[0], native[1], ratio, flag))
    missing = [p["img"] for p in PAPERS
               if p["slug"] in CONTENT and p["img"] not in out]
    if missing:
        print("no thumbnail for: %s" % ", ".join(missing))


if __name__ == "__main__":
    main()
