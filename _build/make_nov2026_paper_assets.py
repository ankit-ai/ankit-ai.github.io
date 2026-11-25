#!/usr/bin/env python3
"""Render actual paper figures and compose website/share assets.

Uses the committed arXiv PDFs, PyMuPDF and Pillow. No generated replacement
diagram: the figure pixels come directly from the source PDF. Editorial text
outside the unchanged crop explains the figure and labels the result's scope.
"""
import argparse
import json
from pathlib import Path

import fitz
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
PAPERS = json.loads((ROOT / "_build/papers.json").read_text())["papers"]
BY_ID = {p.get("arxiv_id"): p for p in PAPERS}
INK = "#172b32"
MUTED = "#50636b"
ACCENT = "#096c66"
BACKGROUND = "#edf4f2"
LINE = "#cfdfda"
FONT = "/System/Library/Fonts/SFNS.ttf"
FALLBACK = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

SPECS = {
    "2611.31727": {
        "page": 4, "rect": [317, 203, 516, 302], "figure": "Figure 2",
        "hook": "Keep the work that already succeeded.",
        "short_title": "fork() for Agents · Agent-Kernel",
        "explain": "a = failed task; b and c = completed siblings; s = dependent task.\nRetry a and s. Reuse the completed outputs of b and c.",
        "metric": "100.0% vs 56.2%",
        "scope": "Agent-Kernel vs FullReplan: task success with transient failures.\nSame retry budget: 3 · Table 6.",
        "metric_short": "100.0%\nvs 56.2%",
        "scope_short": "Task success\nAgent-Kernel vs FullReplan\nTransient-failure ablation\nRetry budget 3",
        "license": "CC BY-NC-ND 4.0",
    },
    "2611.31771": {
        "page": 4, "rect": [88, 69, 508, 199], "figure": "Figure 1",
        "hook": "Write a graph plan. Run one hop at a time.",
        "short_title": "SPARQL-planned multi-hop question answering",
        "explain": "Dense search finds candidate evidence. Wikidata supplies bridge entities.\nConfirm the useful passages, refine the query, and search again.",
        "metric": "67.7 vs 55.2 EM",
        "scope": "Bounded method vs T2RAG · 2WikiMultiHopQA · n = 1,000.\n3,082 vs 3,218 query-time LLM tokens · Tables 1 and 5.",
        "metric_short": "67.7 EM\nvs 55.2",
        "scope_short": "Bounded method vs T2RAG\n2WikiMultiHopQA · n = 1,000\n3,082 vs 3,218 tokens",
        "license": "CC BY-NC-SA 4.0",
    },
}

def font(size, weight=500):
    path = FONT if Path(FONT).exists() else FALLBACK
    obj = ImageFont.truetype(path, size)
    try:
        obj.set_variation_by_axes([100, min(96, max(17, size)), 400, weight])
    except (OSError, AttributeError, ValueError):
        pass
    return obj

def text(draw, value, x, y, width, size, fill=INK, weight=500, leading=1.22):
    face = font(size, weight)
    lines = []
    for paragraph in value.split("\n"):
        current = ""
        for word in paragraph.split():
            candidate = current + (" " if current else "") + word
            if current and draw.textlength(candidate, font=face) > width:
                lines.append(current)
                current = word
            else:
                current = candidate
        lines.append(current)
    for line in lines:
        draw.text((x, y), line, font=face, fill=fill)
        y += int(size * leading)
    return y

def paste_figure(canvas, image, box):
    x, y, width, height = box
    fitted = image.copy()
    fitted.thumbnail((int(width), int(height)), Image.Resampling.LANCZOS)
    canvas.paste(fitted, (int(x + (width - fitted.width) / 2),
                         int(y + (height - fitted.height) / 2)))

def original(pid, spec):
    paper = BY_ID[pid]
    doc = fitz.open(ROOT / "assets/pdf" / paper["pdf_local"])
    pix = doc[spec["page"] - 1].get_pixmap(
        matrix=fitz.Matrix(8, 8), clip=fitz.Rect(*spec["rect"]), alpha=False
    )
    return Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

def card(pid, spec, image, kind):
    paper = BY_ID[pid]
    if kind == "linkedin":
        canvas = Image.new("RGB", (1200, 1500), BACKGROUND)
        d = ImageDraw.Draw(canvas)
        text(d, "NEW PREPRINT · AGENTS / RETRIEVAL", 64, 52, 1072, 25, ACCENT, 650)
        text(d, spec["hook"], 64, 108, 1072, 59, INK, 700)
        text(d, spec["short_title"], 64, 265, 1072, 31, MUTED, 600)
        d.rounded_rectangle((56, 350, 1144, 904), radius=20, fill="white", outline=LINE, width=2)
        paste_figure(canvas, image, (80, 374, 1040, 506))
        text(d, spec["explain"], 64, 935, 1072, 30, INK, 500)
        d.rounded_rectangle((56, 1060, 1144, 1260), radius=18, fill="#deeee8")
        text(d, spec["metric"], 80, 1078, 1024, 60, ACCENT, 720)
        text(d, spec["scope"], 80, 1160, 1024, 25, MUTED, 500)
        text(d, paper["title"], 64, 1292, 1072, 26, INK, 600)
        text(d, f'{spec["figure"]} from the paper · arXiv:{pid} · Nov 24, 2026', 64, 1395, 1072, 24, MUTED)
        text(d, f'Preprint · {spec["license"]} · ankitrchadha.com', 64, 1440, 1072, 22, MUTED)
    elif kind == "x":
        canvas = Image.new("RGB", (1600, 900), BACKGROUND)
        d = ImageDraw.Draw(canvas)
        text(d, "NEW PREPRINT", 64, 42, 1472, 25, ACCENT, 650)
        text(d, spec["hook"], 64, 91, 1472, 62, INK, 700)
        text(d, spec["short_title"], 64, 181, 1472, 30, MUTED, 600)
        d.rounded_rectangle((48, 259, 1030, 740), radius=20, fill="white", outline=LINE, width=2)
        paste_figure(canvas, image, (64, 280, 950, 438))
        text(d, spec["metric_short"], 1070, 286, 470, 64, ACCENT, 720)
        text(d, spec["scope_short"], 1070, 464, 470, 29, MUTED, 500)
        text(d, spec["explain"], 64, 763, 1472, 27, INK, 500)
        text(d, f'{spec["figure"]} from the paper · arXiv:{pid} · Preprint', 64, 852, 1472, 22, MUTED)
    elif kind == "og":
        canvas = Image.new("RGB", (1200, 630), BACKGROUND)
        d = ImageDraw.Draw(canvas)
        text(d, "ARXIV PREPRINT · ANKIT CHADHA", 40, 30, 1120, 21, ACCENT, 650)
        text(d, spec["hook"], 40, 75, 1120, 42, INK, 700)
        text(d, spec["short_title"], 40, 147, 1120, 24, MUTED, 600)
        d.rounded_rectangle((30, 220, 760, 536), radius=12, fill="white", outline=LINE)
        paste_figure(canvas, image, (44, 236, 702, 282))
        text(d, spec["metric_short"], 800, 228, 360, 48, ACCENT, 700)
        text(d, spec["scope_short"], 800, 355, 360, 23, MUTED)
        text(d, f'{spec["figure"]} · arXiv:{pid} · ankitrchadha.com', 40, 575, 1120, 23, MUTED)
    else:
        canvas = Image.new("RGB", (1200, 900), "white")
        d = ImageDraw.Draw(canvas)
        text(d, spec["short_title"], 48, 38, 1104, 36, INK, 650)
        paste_figure(canvas, image, (40, 145, 1120, 530))
        text(d, spec["explain"], 48, 720, 1104, 28, INK)
        text(d, f'{spec["figure"]} · arXiv:{pid} · Preprint', 48, 850, 1104, 23, MUTED)
    return canvas

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
        provenance[pid] = {
            "source": "https://arxiv.org/pdf/" + pid + "v1", "page": spec["page"],
            "figure": spec["figure"], "crop_pdf_points": spec["rect"],
            "native_pixels": list(native.size), "website_pixels": list(web.size),
            "annotation": "Source figure unchanged; explanatory text added outside the crop.",
        }
    (ROOT / "_build/figdims.json").write_text(json.dumps(dims, indent=1, sort_keys=True) + "\n")
    source_data = json.loads((ROOT / "_build/papers.json").read_text())
    source_data["papers"] = PAPERS
    (ROOT / "_build/papers.json").write_text(json.dumps(source_data, indent=2, ensure_ascii=False) + "\n")
    (ROOT / "_build/nov2026_figure_sources.json").write_text(json.dumps(provenance, indent=2) + "\n")
    print(json.dumps(provenance, indent=2))

if __name__ == "__main__":
    main()
