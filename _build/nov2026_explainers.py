"""Reader-facing explanations of two November 2026 papers.

Diagrams are drawn from the papers' mechanisms, rather than reproducing figure
pixels. Agent-Kernel uses the paper's vendor-price example (§3.3 / Figure 2).
The graph-retrieval diagram uses explicitly fictional entities to explain
Figure 1 / §3.2–3.6. Results remain separate from the illustrative examples.
"""
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

INK = "#172b32"
MUTED = "#50636b"
GREEN = "#096c66"
PALE_GREEN = "#e3f2eb"
RED = "#a44337"
PALE_RED = "#faeae5"
BLUE = "#245e91"
PALE_BLUE = "#eaf1f8"
LINE = "#ccdcd6"
BACKGROUND = "#edf4f2"
FONT = "/System/Library/Fonts/SFNS.ttf"
FALLBACK = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
SCALE = 2
LAYOUT_CHECKS = []


def font(size, weight=500):
    face = ImageFont.truetype(FONT if Path(FONT).exists() else FALLBACK,
                              round(size * SCALE))
    try:
        face.set_variation_by_axes([100, min(96, max(17, size)), 400, weight])
    except (OSError, AttributeError, ValueError):
        pass
    return face


class Drawing:
    """Draw at twice the output resolution; check every text box before saving."""

    def __init__(self, width, height, background=BACKGROUND):
        self.width, self.height = width, height
        self.image = Image.new("RGB", (width * SCALE, height * SCALE), background)
        self.draw = ImageDraw.Draw(self.image)

    def box(self, x, y, width, height, fill="white", border=LINE, radius=16):
        coords = tuple(round(v * SCALE) for v in (x, y, x + width, y + height))
        self.draw.rounded_rectangle(coords, radius=round(radius * SCALE),
                                    fill=fill, outline=border, width=2 * SCALE)

    def text(self, value, x, y, width, size=28, fill=INK, weight=500,
             height=None, align="left", leading=1.22):
        face = font(size, weight)
        lines = []
        for paragraph in value.split("\n"):
            current = ""
            for word in paragraph.split():
                candidate = (current + " " + word).strip()
                if current and self.draw.textlength(candidate, font=face) > width * SCALE:
                    lines.append(current)
                    current = word
                else:
                    current = candidate
            lines.append(current)
        step = math.ceil(size * leading)
        used = step * len(lines)
        assert height is None or used <= height, (value, used, height)
        assert x >= 0 and y >= 0 and x + width <= self.width + 1, value
        assert y + used <= self.height, value
        for index, line in enumerate(lines):
            line_width = self.draw.textlength(line, font=face) / SCALE
            assert line_width <= width, (line, line_width, width)
            pos = x + (width - line_width) / 2 if align == "center" else x
            self.draw.text((round(pos * SCALE), round((y + index * step) * SCALE)),
                           line, font=face, fill=fill, anchor="lt")
        LAYOUT_CHECKS.append({"text": value, "size": size, "lines": len(lines),
                              "within_box": True})
        return y + used

    def arrow(self, points, fill=MUTED, width=3, head=10):
        scaled = [(round(x * SCALE), round(y * SCALE)) for x, y in points]
        self.draw.line(scaled, fill=fill, width=width * SCALE, joint="curve")
        x, y = points[-1]
        px, py = points[-2]
        angle = math.atan2(y - py, x - px)
        a = (x - head * math.cos(angle - math.pi / 6),
             y - head * math.sin(angle - math.pi / 6))
        b = (x - head * math.cos(angle + math.pi / 6),
             y - head * math.sin(angle + math.pi / 6))
        self.draw.polygon([(round(vx * SCALE), round(vy * SCALE))
                           for vx, vy in [(x, y), a, b]], fill=fill)

    def paste(self, image, x, y, width, height):
        ratio = min(width * SCALE / image.width, height * SCALE / image.height)
        fitted = image.resize((round(image.width * ratio), round(image.height * ratio)),
                              Image.Resampling.LANCZOS)
        self.image.paste(fitted, (round(x * SCALE), round(y * SCALE)))

    def finish(self):
        return self.image.resize((self.width, self.height), Image.Resampling.LANCZOS)


def kernel_diagram():
    d = Drawing(1100, 580)
    d.box(0, 0, 1100, 92, fill="white")
    d.text("Compare prices from three vendors.", 22, 13, 1056, 32, weight=700)
    d.text("Vendor A fails. Prices from B and C are already saved.",
           22, 57, 1056, 25, MUTED)
    for left, selective in [(0, True), (570, False)]:
        color = GREEN if selective else RED
        tint = PALE_GREEN if selective else PALE_RED
        d.box(left, 113, 530, 467, fill="white")
        d.text("Agent-Kernel" if selective else "Whole-workflow restart",
               left + 20, 130, 490, 31 if selective else 29,
               color, 700, align="center")
        d.text("Sub-Graph Recovery (SGR)" if selective else "FullReplan baseline",
               left + 20, 174, 490, 25, MUTED, align="center")
        centers = []
        for index, vendor in enumerate("ABC"):
            x = left + 20 + index * 166
            kept = selective and index > 0
            node_color = GREEN if kept else RED
            d.box(x, 233, 158, 112,
                  fill=PALE_GREEN if kept else PALE_RED, border=node_color)
            d.text("Vendor " + vendor, x + 8, 250, 142, 26,
                   INK, 650, align="center")
            d.text("KEEP PRICE" if kept else "RETRY" if selective else "FETCH AGAIN",
                   x + 8, 293, 142, 20, node_color, 700, align="center")
            centers.append(x + 79)
        for center in centers:
            d.arrow([(center, 351), (left + 265, 392)], GREEN if selective else RED)
        d.box(left + 72, 397, 386, 98, fill=tint, border=color)
        d.text("Compare all three prices", left + 84, 415, 362, 26,
               INK, 650, align="center")
        d.text("Run after A recovers" if selective else "Run after re-fetching all three",
               left + 84, 455, 362, 22, MUTED, align="center")
        d.text("Reuse 2 completed results" if selective else "Repeat 2 successful fetches",
               left + 20, 523, 490, 27, color, 650, align="center")
    return d.image


def sparql_diagram():
    d = Drawing(1100, 650)
    d.box(0, 0, 1100, 90, fill="white")
    d.text("ILLUSTRATIVE QUESTION · FICTIONAL ENTITIES",
           22, 13, 1056, 18, GREEN, 650)
    d.text("Where was the director of Film X born?",
           22, 45, 1056, 32, INK, 700)
    d.box(24, 114, 462, 170, fill="white")
    d.text("1  Search + check text", 44, 135, 422, 30, BLUE, 700)
    d.text("Find the Film X passage.\nKeep relevant facts; identify gaps.",
           44, 184, 422, 24, INK, height=90)
    d.box(568, 114, 508, 170, fill="white")
    d.text("2  Plan missing links", 588, 135, 468, 30, GREEN, 700)
    d.text("SPARQL: a query language for graph data.\nParse the plan into individual lookups.",
           588, 184, 468, 23, INK, height=90)
    d.arrow([(490, 200), (559, 200)], GREEN)
    d.text("If evidence is missing, use a graph plan:",
           36, 309, 1030, 25, MUTED)
    d.box(24, 351, 1052, 175, fill="white")
    d.text("3  Follow one graph relation per lookup",
           44, 369, 1012, 29, GREEN, 700)
    for x, label in [(44, "Film X"), (431, "Director Y"), (818, "City Z")]:
        d.box(x, 425, 236, 70, fill=PALE_BLUE, border=BLUE)
        d.text(label, x + 10, 445, 216, 29, INK, 650, align="center")
    d.text("director", 282, 415, 146, 21, MUTED, align="center")
    d.arrow([(290, 464), (419, 464)], BLUE)
    d.text("birthplace", 669, 415, 146, 21, MUTED, align="center")
    d.arrow([(677, 464), (806, 464)], BLUE)
    d.arrow([(550, 532), (550, 557)], GREEN)
    d.box(24, 563, 1052, 87, fill=PALE_GREEN, border=GREEN)
    d.text("4  Search again using the new names; confirm the text.",
           44, 577, 1012, 26, GREEN, 650)
    d.text("Answer from passages. Repeat the loop if evidence is still missing.",
           44, 615, 1012, 22, INK)
    # Feedback returns the newly discovered entities to text retrieval.
    d.arrow([(23, 606), (7, 606), (7, 258), (23, 258)], GREEN, width=3)
    return d.image


def metrics(d, pid, x, y, width, height):
    d.box(x, y, width, height, fill="white")
    if pid == "2611.31727":
        label = "Task success in the synthetic transient-failure test"
        values = [("100.0%", "Agent-Kernel"), ("56.2%", "Whole-workflow restart")]
        scope = "Retry budget 3: per failed node vs per whole workflow · Table 6"
    else:
        label = "Exact match: answer matches the reference answer"
        values = [("67.7%", "Graph-guided method (bounded)"), ("55.2%", "T2RAG retrieval baseline")]
        scope = "2WikiMultiHopQA · 1,000 questions · same reader and corpus"
    d.text(label, x + 24, y + 17, width - 48, 25, MUTED, 600)
    colw = (width - 72) / 2
    for index, (value, name) in enumerate(values):
        cx = x + 24 + index * (colw + 24)
        d.text(value, cx, y + 62, colw, 52, GREEN if index == 0 else MUTED, 750)
        d.text(name, cx, y + 130, colw, 24, INK, 600)
    d.text(scope, x + 24, y + 178, width - 48, 21, MUTED)
    if pid == "2611.31771":
        d.text("3,082 vs 3,218 model tokens per question · Tables 1 and 5",
               x + 24, y + 211, width - 48, 21, MUTED)


def diagram(pid):
    return kernel_diagram() if pid == "2611.31727" else sparql_diagram()


def compact(pid, high_resolution=False):
    """Small share previews carry the mechanism, without a dense result panel."""
    d = Drawing(1200, 630)
    kernel = pid == "2611.31727"
    d.text("NEW PREPRINT · ANKIT CHADHA", 40, 28, 1120, 21, GREEN, 650)
    d.text("One tool fails. Keep the work that succeeded." if kernel
           else "Use graph links to find the missing evidence.",
           40, 74, 1120, 43, INK, 700, height=105)
    d.text("Agent-Kernel · Sub-Graph Recovery (SGR)" if kernel
           else "SPARQL: a query language for graph data",
           40, 142, 1120, 27, MUTED, 600)
    if kernel:
        for x, label, action, color, tint in [
            (40, "Vendor A failed", "Retry this fetch", RED, PALE_RED),
            (435, "Vendor B finished", "Keep its price", GREEN, PALE_GREEN),
            (830, "Vendor C finished", "Keep its price", GREEN, PALE_GREEN),
        ]:
            d.box(x, 237, 330, 140, fill=tint, border=color)
            d.text(label, x + 15, 263, 300, 29, INK, 650, align="center")
            d.text(action, x + 15, 315, 300, 26, color, 650, align="center")
            d.arrow([(x + 165, 384), (600, 448)], color)
        d.box(300, 454, 600, 88, fill="white")
        d.text("Compare prices once all three are ready.",
               316, 479, 568, 27, INK, 650, align="center")
    else:
        d.box(40, 216, 1120, 80, fill="white")
        d.text('Example: "Where was the director of Film X born?"',
               58, 239, 1084, 30, INK, 650)
        for x, label in [(40, "Film X"), (465, "Director Y"), (890, "City Z")]:
            d.box(x, 355, 270, 87, fill=PALE_BLUE, border=BLUE)
            d.text(label, x + 12, 381, 246, 30, INK, 650, align="center")
        for x, label in [(320, "director"), (745, "birthplace")]:
            d.text(label, x, 333, 135, 23, MUTED, align="center")
            d.arrow([(x, 403), (x + 135, 403)], BLUE)
        d.text("One relation per lookup → search again → answer from text",
               40, 492, 1120, 30, GREEN, 650)
    d.text(f"Paper-based explainer · arXiv:{pid} · ankitrchadha.com",
           40, 588, 1120, 22, MUTED)
    return d.image if high_resolution else d.finish()


def card(pid, kind):
    if kind == "og":
        return compact(pid)
    if kind == "x":
        width, height, diagram_y = 1600, 900, 217
        d = Drawing(width, height)
        kernel = pid == "2611.31727"
        d.text("NEW PREPRINT", 50, 29, 1500, 23, GREEN, 650)
        d.text("One tool fails. Keep the work that succeeded." if kernel
               else "Use graph links to find the missing evidence.",
               50, 74, 1500, 54, INK, 700, height=80)
        d.text("Agent-Kernel · Sub-Graph Recovery (SGR)" if kernel
               else "Search text. Plan missing links. Follow one relation at a time.",
               50, 157, 1500, 30, MUTED, 600)
        native = diagram(pid)
        # The diagram occupies the full-height left column; results are separate.
        d.paste(native, 50, diagram_y, 1095, 647 if not kernel else 577)
        d.box(1180, 217, 370, 565, fill="white")
        if kernel:
            d.text("Task success", 1204, 242, 322, 29, INK, 650)
            d.text("100.0%", 1204, 296, 322, 55, GREEN, 750)
            d.text("Agent-Kernel", 1204, 365, 322, 27, INK, 600)
            d.text("56.2%", 1204, 416, 322, 55, MUTED, 750)
            d.text("Whole-workflow restart", 1204, 487, 322, 25, INK, 600)
            d.text("Synthetic transient-failure test.\nRetry budget 3: per node vs per workflow.\nTable 6.",
                   1204, 571, 322, 25, MUTED, height=200)
        else:
            d.text("Exact-match answers", 1204, 242, 322, 27, INK, 650)
            d.text("67.7%", 1204, 293, 322, 55, GREEN, 750)
            d.text("Graph-guided method\n(bounded)", 1204, 362, 322, 25, INK, 600)
            d.text("55.2%", 1204, 432, 322, 55, MUTED, 750)
            d.text("T2RAG retrieval baseline", 1204, 501, 322, 25, INK, 600)
            d.text("2WikiMultiHopQA\n1,000 questions\n3,082 vs 3,218 model tokens/question",
                   1204, 584, 322, 24, MUTED, height=185)
        if kernel:
            d.text("Retry the failed task and its dependents; preserve unrelated completed outputs.",
                   50, 818, 1500, 26, INK, 550)
        d.text(f"Paper-based explainer · arXiv:{pid} · Preprint · ankitrchadha.com",
               50, 867, 1500, 21, MUTED)
        return d.finish()
    if kind == "featured":
        # Home-page crops use the compact explanation at a larger aspect ratio.
        d = Drawing(1200, 900)
        d.paste(compact(pid, high_resolution=True), 0, 114, 1200, 630)
        return d.finish()

    d = Drawing(1200, 1500)
    kernel = pid == "2611.31727"
    d.text("NEW PREPRINT · AGENT SYSTEMS" if kernel else "NEW PREPRINT · RETRIEVAL",
           50, 38, 1100, 24, GREEN, 650)
    d.text("One tool fails.\nKeep the work that succeeded." if kernel
           else "Use graph links to find\nthe missing evidence.",
           50, 94, 1100, 57, INK, 700, height=155)
    d.text("fork() for Agents · Agent-Kernel" if kernel
           else "SPARQL-planned multi-hop question answering",
           50, 266, 1100, 30, MUTED, 600)
    native = diagram(pid)
    d.paste(native, 50, 342, 1100, 580 if kernel else 650)
    if kernel:
        d.text("Retry the failed task and its dependents.\nPreserve unrelated completed outputs.",
               50, 958, 1100, 30, INK, 550, height=95)
    else:
        d.text("The graph guides retrieval.\nThe reader answers from confirmed text passages.",
               50, 1020, 1100, 28, INK, 550, height=80)
    metrics(d, pid, 50, 1080 if kernel else 1120, 1100, 220 if kernel else 258)
    credit = ("Explanation of Figure 2 + the vendor-price example in §3.3."
              if kernel else "Explanation of Figure 1. Film X, Director Y and City Z are illustrative.")
    d.text(credit, 50, 1343 if kernel else 1397, 1100, 22, MUTED)
    d.text(f"arXiv:{pid} · Preprint · ankitrchadha.com",
           50, 1442, 1100, 24, MUTED)
    return d.finish()
