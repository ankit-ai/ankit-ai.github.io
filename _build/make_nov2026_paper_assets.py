#!/usr/bin/env python3
"""Keep original paper figures and render accessible companion explainers.

Body figures remain unchanged PDF crops. Social, featured and share cards use
purpose-drawn explanations with named tasks, expanded terms and scoped results.
"""
import argparse
import json
from pathlib import Path

import fitz
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
PAPERS = json.loads((ROOT / "_build/papers.json").read_text())["papers"]
BY_ID = {p.get("arxiv_id"): p for p in PAPERS}

SPECS = {
    "2611.31727": {"page": 4, "rect": [317, 203, 516, 302], "figure": "Figure 2"},
    "2611.31771": {"page": 4, "rect": [88, 69, 508, 199], "figure": "Figure 1"},
}


def original(pid, spec):
    paper = BY_ID[pid]
    doc = fitz.open(ROOT / "assets/pdf" / paper["pdf_local"])
    pix = doc[spec["page"] - 1].get_pixmap(
        matrix=fitz.Matrix(8, 8), clip=fitz.Rect(*spec["rect"]), alpha=False
    )
    return Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

def card(pid, spec, image, kind):
    from nov2026_explainers import card as explanatory_card
    return explanatory_card(pid, kind)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--social-dir", type=Path, help="Optional output folder for LinkedIn/X upload images.")
    args = parser.parse_args()
    dims = json.loads((ROOT / "_build/figdims.json").read_text())
    provenance = {}
    for pid, spec in SPECS.items():
        paper = BY_ID[pid]
        native = original(pid, spec)
        web = native.copy()
        web.thumbnail((1200, 1200), Image.Resampling.LANCZOS)
        directory = ROOT / "assets/img/figs"
        web.save(directory / (pid + ".jpg"), quality=95, optimize=True, progressive=True)
        web.save(directory / (pid + ".webp"), quality=95, method=6)
        dims[pid] = list(web.size)
        paper["img_w"], paper["img_h"] = web.size
        for kind, target in [
            ("og", ROOT / "assets/img/cards" / (paper["slug"] + "-1200x630.jpg")),
            ("featured", ROOT / "assets/img/featured" / (pid + ".jpg")),
        ]:
            target.parent.mkdir(parents=True, exist_ok=True)
            card(pid, spec, native, kind).save(target, quality=95, optimize=True, progressive=True)
        if args.social_dir:
            out = args.social_dir / paper["slug"]
            out.mkdir(parents=True, exist_ok=True)
            native.save(out / "figure-original.png", optimize=True)
            for kind in ["linkedin", "x"]:
                card(pid, spec, native, kind).save(out / (kind + "-figure.png"), optimize=True)
            from nov2026_explainers import diagram
            explained = diagram(pid)
            explained.resize((1100, 580 if pid == "2611.31727" else 650),
                             Image.Resampling.LANCZOS).save(out / "figure-explained.png", optimize=True)
        provenance[pid] = {
            "source": "https://arxiv.org/pdf/" + pid + "v1", "page": spec["page"],
            "figure": spec["figure"], "crop_pdf_points": spec["rect"],
            "native_pixels": list(native.size), "website_pixels": list(web.size),
            "annotation": "Paper-page figure is an unchanged crop. Social, featured and share images are newly drawn paper-based explainers.",
            "explainer_source": "Figure 2 and Section 3.3's vendor-price example" if pid == "2611.31727" else "Figure 1 and Sections 3.2–3.6; fictional film/director entities illustrate the mechanism.",
        }
    (ROOT / "_build/figdims.json").write_text(json.dumps(dims, indent=1, sort_keys=True) + "\n")
    source_data = json.loads((ROOT / "_build/papers.json").read_text())
    source_data["papers"] = PAPERS
    (ROOT / "_build/papers.json").write_text(json.dumps(source_data, indent=2, ensure_ascii=False) + "\n")
    (ROOT / "_build/nov2026_figure_sources.json").write_text(json.dumps(provenance, indent=2) + "\n")
    print(json.dumps(provenance, indent=2))

if __name__ == "__main__":
    main()
