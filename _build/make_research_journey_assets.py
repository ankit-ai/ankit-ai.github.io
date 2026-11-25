#!/usr/bin/env python3
"""Import the illustrated recap assets and make the research landing-page share card."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "_build"


def font(size, bold=False):
    return ImageFont.truetype(
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold
        else "/System/Library/Fonts/Supplemental/Arial.ttf", size)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("slideshow", type=Path, help="Folder containing the verified eight-slide PDF, slides and assets")
    args = parser.parse_args()
    source = args.slideshow
    data = json.loads((BUILD / "research_journey.json").read_text())
    destination = ROOT / "assets/img/research-journey"
    destination.mkdir(parents=True, exist_ok=True)
    records = []
    for index, step in enumerate(data["steps"], 2):
        original = source / "slides" / f"slide-{index:02d}.png"
        image = Image.open(original).convert("RGB")
        assert image.size == (1200, 1500)
        target = ROOT / step["image"].lstrip("/")
        image.crop((55, 418, 1145, 995)).resize((960, 508), Image.Resampling.LANCZOS).save(
            target, format="WEBP", quality=89, method=6)
        records.append({
            "asset": step["image"], "source_slide": index,
            "source_sha256": hashlib.sha256(original.read_bytes()).hexdigest(),
            "illustration": "Original code-drawn explanation of an illustrative trip",
        })
    photo = Image.open(source / "assets/airplane-wing-anthony-wong.jpg").convert("RGB")
    hero = ImageOps.fit(photo.crop((0, 975, 2200, 2165)), (900, 900),
                        Image.Resampling.LANCZOS, centering=(.24, .5))
    hero.save(ROOT / data["hero_image"].lstrip("/"), format="WEBP", quality=87, method=6)
    pdf = ROOT / data["pdf"].lstrip("/")
    pdf.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source / "linkedin-slideshow.pdf", pdf)

    card = Image.new("RGB", (1200, 630), "#0b2239")
    flight = ImageOps.fit(hero, (500, 630), Image.Resampling.LANCZOS, centering=(.3, .5))
    card.paste(flight, (700, 0))
    pixels = card.load()
    # Fade the photo into the site's navy rather than placing text over the wing.
    for xx in range(700, 990):
        opacity = (1 - (xx-700)/290) * .95
        for yy in range(630):
            r, g, b = pixels[xx, yy]
            pixels[xx, yy] = tuple(round(c*(1-opacity)+n*opacity) for c, n in zip((r, g, b), (11, 34, 57)))
    draw = ImageDraw.Draw(card)
    draw.text((56, 48), "RESEARCH / 2026", fill="#bdabff", font=font(23, True))
    draw.text((56, 122), "Your agent remembers.", fill="#ffffff", font=font(58, True))
    draw.text((56, 201), "Can it finish the job?", fill="#ffffff", font=font(58, True))
    draw.text((58, 321), "Six questions beyond memory.", fill="#d9e7ef", font=font(29))
    draw.text((58, 384), "Remember · reuse · update", fill="#bdabff", font=font(25, True))
    draw.text((58, 429), "Hand off · find evidence · recover", fill="#d7f79a", font=font(25, True))
    draw.line((58, 506, 673, 506), fill="#3f5f77", width=2)
    draw.text((58, 546), "Ankit Chadha & collaborators", fill="#d9e7ef", font=font(25))
    card_target = ROOT / data["card"].lstrip("/")
    card.save(card_target, quality=94, optimize=True)
    (BUILD / "research_journey_assets.json").write_text(json.dumps({
        "checked": data["checked"], "photo": data["photo"], "illustrations": records,
        "pdf": data["pdf"], "pdf_sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
        "share_card": data["card"],
    }, indent=2)+"\n")
    print(json.dumps({"images": 8, "PDF_bytes": pdf.stat().st_size,
                      "share_card": str(card_target)}, indent=2))


if __name__ == "__main__":
    main()
