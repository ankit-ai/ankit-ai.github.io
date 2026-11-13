#!/usr/bin/env python3
"""Recreate WK-Drift figure assets from the published, CC BY 4.0 proceedings PDF.

Requires PyMuPDF and Pillow. Figure 1 is on PDF page 6 (proceedings page 2724).
The crop preserves both panels, their labels, and the replacement pointer.
"""
from pathlib import Path
import pymupdf
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "assets" / "pdf" / "wk-drift-findings-aacl-2026.pdf"
with pymupdf.open(PDF) as doc:
    pix = doc[5].get_pixmap(
        matrix=pymupdf.Matrix(6, 6),
        clip=pymupdf.Rect(156, 68, 440, 281),
        alpha=False,
    )
image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
image = image.resize((1200, 900), Image.Resampling.LANCZOS)
figs = ROOT / "assets" / "img" / "figs"
featured = ROOT / "assets" / "img" / "featured"
figs.mkdir(parents=True, exist_ok=True)
featured.mkdir(parents=True, exist_ok=True)
image.save(figs / "wk-drift.jpg", quality=92, optimize=True, progressive=True)
image.save(figs / "wk-drift.webp", quality=90, method=6)
image.resize((600, 450), Image.Resampling.LANCZOS).save(
    featured / "wk-drift.jpg", quality=92, optimize=True, progressive=True
)
print("Wrote WK-Drift figure and homepage thumbnail.")
