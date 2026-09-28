#!/usr/bin/env python3
"""
Social share cards, 1200x630, one per paper, at assets/img/cards/<slug>-1200x630.jpg.

These are what Twitter, LinkedIn and Slack show when someone shares a paper page,
and they are the highest-leverage image on the site. The design rule is the same as
the site's: typography and one real number, no decoration, nothing invented. Every
headline figure below is a from/to pair that appears in the paper and was verified
against the PDF text by a second pass.
"""

import json
import os

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "img", "cards")
os.makedirs(OUT, exist_ok=True)

PAPERS = json.load(open(os.path.join(ROOT, "_build", "papers.json")))["papers"]
SITE = json.load(open(os.path.join(ROOT, "_build", "site.json")))

SF = "/System/Library/Fonts/SFNS.ttf"
SFI = "/System/Library/Fonts/SFNSItalic.ttf"
MONO = "/System/Library/Fonts/SFNSMono.ttf"


def font(path, size, weight=None):
    """SF is a variable font with four axes: Width, Optical Size, GRAD, Weight.
    All four must be supplied, in that order, or Pillow assigns the single value
    to Width and the text comes out the wrong shape at the default weight."""
    f = ImageFont.truetype(path, size)
    if weight is not None:
        try:
            f.set_variation_by_axes([100, min(96, max(17, size)), 400, weight])
        except Exception:
            pass
    return f


INK = (21, 21, 21)
MUT = (91, 97, 105)
ACC = (11, 92, 173)
LINE = (227, 230, 234)

# slug -> (metric label, from, to, what it is measured on)
# Each pair is quoted from the paper, with the comparator named.
HEADLINE = {
 "apex-mem-agentic-semi-structured-memory":
   ("Accuracy on LOCOMO memory questions", "85.38", "88.88",
    "best prior system to APEX-MEM, GPT-5"),
 "apex-em-procedural-episodic-experience-replay":
   ("Accuracy on unseen knowledge-graph questions", "42.0", "73.7",
    "no memory to APEX-EM, no retraining"),
 "routed-graph-handoff":
   ("Task success rate on tau-retail", "12.0", "24.7",
    "prose handoff to routed graph handoff"),
 "cross-lingual-knowledge-distillation-answer-sentence-selection":
   ("Arabic P@1 on Xtr-WikiQA", "64.2", "76.3",
    "supervised fine-tuning to cross-lingual distillation"),
 "wdrass-web-scale-document-retrieval-answer-sentence-selection":
   ("Hit at rank 1, WDRASS test set", "31.8", "41.4",
    "retriever trained on Natural Questions to one trained on WDRASS"),
 "question-context-alignment-answer-sentence-selection":
   ("P@1 on WikiQA", "68.09", "74.16",
    "sentence-concatenation context to aligned context"),
 "efficient-fine-tuning-knowledge-aware-response-planning":
   ("P@1 on WikiQA without ASNQ transfer", "63.24", "74.16",
    "TANDA to this paper's retriever"),
 "controlled-text-generation-hidden-representation-transformations":
   ("Toxicity of generated text, lower is better", "0.827", "0.085",
    "base GPT-2 medium to CHRT"),
 "federated-learning-mixed-domain-translation":
   ("Average BLEU, German to English", "32.00", "33.83",
    "best centralized baseline to the federated server model"),
 "communication-efficient-federated-learning-nmt":
   ("Parameters exchanged per round", "6x", "1x",
    "full-parameter federated training to Controller layers only"),
 "attribute-conditioning-multi-document-summarization":
   ("ROUGE-1 on MultiNews", "42.99", "50.12",
    "GraphSum to attribute-conditioned summarization"),
 "dr-sas-deep-reinforced-self-attention-masks":
   ("ROUGE-1 on CNN/DailyMail", "40.79", "41.89",
    "fine-tuned UniLM to DR.SAS"),
 "bertqa-attention-on-steroids":
   ("SQuAD 2.0 dev F1, BERT base", "74.15", "77.03",
    "BERT base to directed coattention"),
}


def wrap(draw, text, fnt, maxw):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=fnt) <= maxw:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def card(p):
    W, H = 1200, 630
    PAD = 66
    im = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(im)

    # A single hairline rule at the top, in the accent, as the only ornament.
    d.rectangle([0, 0, W, 7], fill=ACC)

    f_kick = font(SF, 21, 590)
    f_title = font(SF, 45, 700)
    f_num = font(SF, 82, 760)
    f_arrow = font(SF, 40, 400)
    f_lab = font(SF, 20, 500)
    f_sub = font(SF, 19, 400)
    f_name = font(SF, 22, 620)
    f_ven = font(SF, 20, 400)

    # Measure first, then place, so short and long titles both sit balanced
    # between the top rule and the footer rule instead of leaving dead space.
    # The double hyphen in two titles is a LaTeX artifact carried by arXiv. The
    # metadata keeps it verbatim so the record still matches; the card, which no
    # indexer reads, shows a proper dash.
    shown_title = p["title"].replace(" -- ", " – ")
    title_lines = wrap(d, shown_title, f_title, W - 2 * PAD)[:3]
    lab, frm, to, comp = HEADLINE[p["slug"]]
    author_lines = wrap(d, ", ".join(p["authors"]), f_sub, W - 2 * PAD)[:2]
    FOOT = H - 104
    block = (40 + 56 * len(title_lines) + 14 + 32 + 100 + 26
             + 18 + 26 * len(author_lines))
    y = max(PAD + 4, (FOOT - block) // 2)

    kick = p["venue_short"]
    if p.get("is_preprint") and "preprint" not in kick.lower():
        kick = "Preprint  ·  " + kick
    d.text((PAD, y), kick.upper(), font=f_kick, fill=ACC)
    y += 40

    for ln in title_lines:
        d.text((PAD, y), ln, font=f_title, fill=INK)
        y += 56
    y += 14

    d.text((PAD, y), lab, font=f_lab, fill=MUT)
    y += 32

    x = PAD
    d.text((x, y), frm, font=f_num, fill=(150, 156, 163))
    x += d.textlength(frm, font=f_num) + 26
    d.text((x, y + 22), "→", font=f_arrow, fill=MUT)
    x += d.textlength("→", font=f_arrow) + 26
    d.text((x, y), to, font=f_num, fill=ACC)
    y += 100

    d.text((PAD, y), comp, font=f_sub, fill=MUT)
    y += 18 + 26

    for ln in author_lines:
        d.text((PAD, y), ln, font=f_sub, fill=(120, 126, 133))
        y += 26

    # Footer: who, and where the paper lives.
    d.line([PAD, FOOT, W - PAD, FOOT], fill=LINE, width=1)
    d.text((PAD, FOOT + 20), SITE["name"], font=f_name, fill=INK)
    d.text((PAD, FOOT + 50), "%s  ·  ankit-ai.github.io" % SITE["job_title"],
           font=f_ven, fill=MUT)

    path = os.path.join(OUT, "%s-1200x630.jpg" % p["slug"])
    im.save(path, "JPEG", quality=90, optimize=True, progressive=True)
    return path


def counts():
    """The publication tally, computed rather than typed, so the share cards can
    never drift from papers.json the way a hand-written number would."""
    data = json.load(open(os.path.join(ROOT, "_build", "papers.json")))
    st = [x.get("status") or ("preprint" if x.get("is_preprint") else "published")
          for x in data["papers"]]
    return {
        "published": st.count("published"),
        "accepted": st.count("accepted"),
        "preprint": st.count("preprint"),
        "earlier": len(data["earlier_work"]),
        "patents": len(data["patents"]),
    }


def profile_card(name, kicker, lines, out_name):
    """The 1200x630 share card for a page that is about the person rather than a
    paper. The home page and 404 previously declared og:image 1200x630 while
    pointing at the 800x800 headshot, so every scraper that trusts the declared
    size cropped it wrong. Same grid as the paper cards, plus the portrait."""
    W, H = 1200, 630
    PAD = 66
    im = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, 7], fill=ACC)

    # Portrait, circular, on the right. Drawn first so the text column can be
    # measured against the space that is actually left.
    DIA = 306
    px, py = W - PAD - DIA, (H - DIA) // 2 + 6
    hs = os.path.join(ROOT, "assets", "img", "headshot-800.jpg")
    if os.path.exists(hs):
        por = Image.open(hs).convert("RGB").resize((DIA, DIA), Image.LANCZOS)
        mask = Image.new("L", (DIA * 4, DIA * 4), 0)
        ImageDraw.Draw(mask).ellipse([0, 0, DIA * 4 - 1, DIA * 4 - 1], fill=255)
        im.paste(por, (px, py), mask.resize((DIA, DIA), Image.LANCZOS))
    colw = px - PAD - 48

    f_kick = font(SF, 21, 590)
    f_name = font(SF, 58, 730)
    f_role = font(SF, 25, 500)
    f_line = font(SF, 21, 400)
    f_ven = font(SF, 20, 400)

    role_lines = wrap(d, "%s at %s" % (SITE["job_title"], SITE["employer"]),
                      f_role, colw)
    body = []
    for ln in lines:
        body += wrap(d, ln, f_line, colw)
    FOOT = H - 104
    block = 40 + 66 + 12 + 34 * len(role_lines) + 20 + 30 * len(body)
    y = max(PAD + 4, (FOOT - block) // 2)

    d.text((PAD, y), kicker.upper(), font=f_kick, fill=ACC)
    y += 40
    d.text((PAD, y), name, font=f_name, fill=INK)
    y += 66 + 12
    for ln in role_lines:
        d.text((PAD, y), ln, font=f_role, fill=MUT)
        y += 34
    y += 20
    for ln in body:
        d.text((PAD, y), ln, font=f_line, fill=(120, 126, 133))
        y += 30

    d.line([PAD, FOOT, W - PAD, FOOT], fill=LINE, width=1)
    d.text((PAD, FOOT + 20), "ankit-ai.github.io", font=font(SF, 22, 620), fill=INK)
    d.text((PAD, FOOT + 50), "Every paper has its own page, abstract and PDF.",
           font=f_ven, fill=MUT)

    path = os.path.join(OUT, out_name)
    im.save(path, "JPEG", quality=90, optimize=True, progressive=True)
    return path


made = 0
for p in PAPERS:
    if p["slug"] not in HEADLINE:
        print("NO HEADLINE for %s, skipped" % p["slug"])
        continue
    card(p)
    made += 1

n = counts()
tally = ("%d papers in published proceedings, %d accepted and not yet in "
         "proceedings, %d preprints." % (n["published"], n["accepted"], n["preprint"]))
patents = "%d granted patents, and %d earlier papers from 2013 to 2015." % (
    n["patents"], n["earlier"])
profile_card(SITE["name"], "Agent memory and retrieval",
             [tally, patents], "site-1200x630.jpg")
profile_card(SITE["name"], "Publications", [tally, patents],
             "publications-1200x630.jpg")
made += 2
print("wrote %d cards to %s" % (made, OUT))
