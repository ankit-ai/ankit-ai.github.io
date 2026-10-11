#!/usr/bin/env python3
"""
Static site generator for ankit-ai.github.io.

Reads:
  _build/site.json      site-wide config and prose
  _build/papers.json    hand-curated bibliographic metadata
  _build/content.json   per-paper page content (abstract, tldr, key results, bibtex)
  _build/figdims.json   natural pixel dimensions of each figure image

Writes, at the repo root:
  index.html
  publications/index.html
  papers/<slug>/index.html      plus a sibling PDF (required by Google Scholar)
  sitemap.xml  robots.txt  404.html  .nojekyll

Design constraints that are load-bearing, not stylistic:
  * One URL per paper. Google Scholar will not index two abstracts on one page.
  * citation_pdf_url must point at a file in the SAME directory as the HTML.
  * The complete author-written abstract must be plain visible text, above the fold.
  * citation_* tags appear ONLY on paper pages, never on the homepage or index.
  * All CSS is inlined so a paper page is one request and LCP is text.
"""

import html
import json
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(ROOT, "_build")


def load(name):
    with open(os.path.join(BUILD, name), encoding="utf-8") as fh:
        return json.load(fh)


SITE = load("site.json")
DATA = load("papers.json")
FIGDIMS = load("figdims.json")
try:
    CONTENT = load("content.json")
except FileNotFoundError:
    CONTENT = {}
# slug -> the one headline result drawn beside each paper in the list. Kept in its own
# file rather than in content.json because content.json is the paper's prose and this
# is a chart: it needs a metric ceiling, a direction, and two labelled values, none of
# which the prose has. check.py holds it to content.json's key_results, so the panel
# cannot drift from the numbers on the paper's own page.
try:
    HEAD = load("headline.json")
except FileNotFoundError:
    HEAD = {}

BASE = SITE["base_url"].rstrip("/")
PAPERS = DATA["papers"]
BY_SLUG = {p["slug"]: p for p in PAPERS}

# slug -> its one topic tag, inverted from site.json so the tag list stays in one
# place and a paper can never end up wearing two tags or none. Exactly one tag per
# paper is a deliberate limit: the tag exists so a reader skimming thirteen rows can
# see the shape of the work, and a row wearing three pills is slower to read than a
# row wearing none.
TAG_OF = {}
for _t in SITE.get("topic_tags", []):
    for _s in _t["papers"]:
        TAG_OF[_s] = _t["tag"]


def e(s):
    """Escape for use in an HTML attribute or text node."""
    return html.escape(str(s or ""), quote=True)


def url(path=""):
    return BASE + "/" + path.lstrip("/")


def iso(date_slashes):
    """'2026/8/26' -> '2026-08-26'.  '2026' -> '2026'."""
    parts = [p for p in str(date_slashes).split("/") if p]
    if len(parts) == 3:
        return "%04d-%02d-%02d" % (int(parts[0]), int(parts[1]), int(parts[2]))
    return parts[0] if parts else ""


def pages_split(pages):
    m = re.match(r"^\s*(\d+)\s*-\s*(\d+)\s*$", pages or "")
    return (m.group(1), m.group(2)) if m else (None, None)


def author_line_html(p):
    """Authors, with Ankit bolded. Plain text, no affiliations (Scholar rule for the tag,
    but this is the visible line so a self-bold is fine)."""
    out = []
    for a in p["authors"]:
        if a == "Ankit Chadha":
            out.append("<strong>Ankit Chadha</strong>")
        else:
            out.append(e(a))
    return ", ".join(out)


NUM_RE = re.compile(r"\d+(?:\.\d+)?%|\d+\.\d+")
# Do not emphasise model versions, dataset versions or cross-references.
# "SQuAD 2.0" and "Section 4.3" are names and pointers, not evidence, and
# bolding them competes with the measurements that are.
NUM_SKIP = ("Claude ", "GPT", "Sonnet ", "Haiku ", "Opus ", "Llama ", "Qwen ",
            "SQuAD ", "Section ", "Table ", "Figure ")


def nums(s):
    """Escape text and mark measured quantities so the evidence is scannable.

    Only wraps the run of characters that is already there. No text is added,
    removed or reordered; the visible string is byte-for-byte the source string.
    """
    s = str(s or "")
    out, last = [], 0
    for m in NUM_RE.finditer(s):
        if any(s[:m.start()].endswith(x) for x in NUM_SKIP):
            continue
        out.append(e(s[last:m.start()]))
        out.append('<span class="n">%s</span>' % e(m.group(0)))
        last = m.end()
    out.append(e(s[last:]))
    return "".join(out)


def pub_status(p):
    """Publication state: "published", "accepted" or "preprint".

    papers.json "status" is the source of truth. is_preprint is only a fallback
    for older data, because a paper accepted at a venue whose proceedings have
    not appeared yet is not a preprint and must not be badged as one.
    """
    return p.get("status") or ("preprint" if p.get("is_preprint") else "published")


def split_lead(s):
    """'Role sentence. Rest of it.' -> ('Role sentence.', 'Rest of it.')

    Used to give the homepage tagline two levels of emphasis without altering it.
    """
    s = str(s or "")
    i = s.find(". ")
    return (s[:i + 1], s[i + 2:]) if i > 0 else (s, "")


def plain_citation(p):
    names = p["authors"]
    if len(names) == 1:
        who = names[0]
    elif len(names) == 2:
        who = "%s and %s" % (names[0], names[1])
    else:
        who = ", ".join(names[:-1]) + ", and " + names[-1]
    bits = ["%s. %d. %s." % (who, p["year"], p["title"])]
    if p.get("venue_long"):
        bits.append("In <em>%s</em>" % e(p["venue_long"]))
        if p.get("pages"):
            bits[-1] += ", pages %s" % p["pages"].replace("-", "&ndash;")
        bits[-1] += "."
    elif p.get("arxiv_id"):
        bits.append("arXiv:%s." % e(p["arxiv_id"]))
    return " ".join(e(b) if i == 0 else b for i, b in enumerate(bits))


def bibtex_for(p, c):
    """Return the maintained citation, adding verified identifiers when absent."""
    text = c["bibtex"].strip()
    additions = []
    if p.get("doi") and not p["doi"].startswith("10.48550") and "doi" not in text.lower():
        additions.append("  doi           = {%s}" % p["doi"])
    venue_url = p.get("anthology_url") or p.get("publisher_url")
    if venue_url and "\n  url" not in text.lower():
        additions.append("  url           = {%s}" % venue_url)
    if additions:
        text = re.sub(r"\n}\s*$", ",\n" + ",\n".join(additions) + "\n}", text)
    return text


def artifact_note(p):
    has_code = bool(p.get("code_url"))
    has_data = bool(p.get("data_url") or p.get("data_urls"))
    if has_code and has_data:
        return "Public code and data are linked above."
    if has_code:
        return "Public code is linked above; no public dataset is listed."
    if has_data:
        return "Public datasets are linked above; no public code repository is listed."
    return "No public code or dataset is listed for this paper."


# Inline SVG only. Every icon here is a hand-written path drawn on a 24-unit grid
# with stroke:currentColor, so it inherits the colour of the text it sits beside,
# scales with the font, needs no icon font, and costs no network request. An icon
# font or an external sprite would be the one external subresource on the site and
# would leave every heading blank until it loaded.
ICONS = {
 "doc": "M7 3h7l4 4v14H7z M14 3v4h4",
 "why": "M12 3v2 M12 19v2 M4.2 12H2 M22 12h-2.2 M6 6 4.5 4.5 M18 6l1.5-1.5"
        " M9.5 15a4.5 4.5 0 1 1 5 0v2.5h-5z M10 20h4",
 "chart": "M4 20V9 M10 20V4 M16 20v-7 M22 20H2",
 "tag": "M4 4h7l9 9-7 7-9-9z M8 8h.01",
 "candid": "M3 12a9 9 0 0 1 18 0 9 9 0 0 1-18 0z M12 8v5 M12 16h.01",
 "quote": "M10.5 4C8 4 9 10 5.5 12c3.5 2 2.5 8 5 8 M13.5 4c2.5 0 1.5 6 5 8-3.5 2-2.5 8-5 8",
 "link": "M9 15l6-6 M11 6l1.5-1.5a4.2 4.2 0 0 1 6 6L17 12"
         " M13 18l-1.5 1.5a4.2 4.2 0 0 1-6-6L7 12",
 "check": "M4 12.5 9 17.5 20 6.5",
 "draft": "M14 3H7v18h11V7z M14 3v4h4 M10 12h5 M10 16h5",
 "patent": "M12 2 4 5.5v6c0 5 3.4 8.6 8 10.5 4.6-1.9 8-5.5 8-10.5v-6z M9 12l2.2 2.2L15.5 10",
 "clock": "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z M12 7.5V12l3.5 2",
 "grid": "M4 4.5h6.5V11H4z M13.5 4.5H20V11h-6.5z M4 13h6.5v6.5H4z M13.5 13H20v6.5h-6.5z",
 "cap": "M12 4 2.5 8.5 12 13l9.5-4.5z M6 10.5V16c0 1.7 2.7 3 6 3s6-1.3 6-3v-5.5",
 "badge": "M3 7.5h18v12H3z M9 7.5V5h6v2.5 M3 12.5h18",
 "mail": "M3 6h18v12H3z M3 7l9 6.5L21 7",
 "agents": "M12 7a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z"
           " M5 22a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z"
           " M19 22a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z"
           " M10.8 6.3 6.2 17.2 M13.2 6.3l4.6 10.9 M7.5 19.5h9",
 "pipeline": "M3 5h6v5H3z M15 14h6v5h-6z M9 7.5h4.5a3 3 0 0 1 3 3V14"
             " M13.5 12l3 2 3-2",
 "pdf": "M7 3h7l4 4v14H7z M14 3v4h4 M10 17v-5h1.6a1.7 1.7 0 0 1 0 3.4H10",
 "code": "M9.5 8 5 12l4.5 4 M14.5 8 19 12l-4.5 4",
 "data": "M12 3c4.4 0 8 1.1 8 2.5S16.4 8 12 8 4 6.9 4 5.5 7.6 3 12 3z"
         " M20 5.5v13C20 19.9 16.4 21 12 21s-8-1.1-8-2.5v-13 M4 12c0 1.4 3.6 2.5 8 2.5"
         "s8-1.1 8-2.5",
 "out": "M14 4h6v6 M20 4 11 13 M18 14v5H5V6h5",
 "book": "M4 5.5C4 4.1 6.7 3 10 3s6 1.1 6 2.5V21c0-1.4-2.7-2.5-6-2.5S4 19.6 4 21z"
         " M16 5.5C16 4.1 17.3 3 19 3v15.5c-1.7 0-3 1.1-3 2.5",
}


# Brand marks for the profile links, as filled inline SVG on each mark's own
# native grid so nothing is rescaled by hand and distorted.
#
# Which marks are real and which are generic is a deliberate split. GitHub,
# LinkedIn and X all publish brand guidelines that explicitly permit their mark
# to be used as a link to your own profile, so those three are the real marks and
# a reader recognises them instantly. Google, Amazon and the ACL do not grant
# that, so those three get a plain graduation cap, a flask and an open book: a
# generic icon in the right shape is honest, whereas an approximation of somebody
# else's trademark is neither honest nor legal. All six are single-colour and
# inherit currentColor, so the row still reads as one row.
BRANDS = {
 "GitHub": ("0 0 16 16",
   "M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38"
   " 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13"
   "-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66"
   ".07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15"
   "-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09"
   " 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15"
   " 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2"
   " 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8z"),
 "LinkedIn": ("0 0 24 24",
   "M22.22 0H1.77C.79 0 0 .77 0 1.73v20.54C0 23.22.79 24 1.77 24h20.45c.98 0"
   " 1.78-.78 1.78-1.73V1.73C24 .77 23.2 0 22.22 0zM7.12 20.45H3.55V9h3.57v11.45z"
   "M5.34 7.43a2.06 2.06 0 1 1 0-4.13 2.06 2.06 0 0 1 0 4.13zm15.11 13.02h-3.56"
   "v-5.57c0-1.33-.03-3.04-1.85-3.04-1.85 0-2.13 1.45-2.13 2.94v5.67H9.35V9h3.41"
   "v1.56h.05c.48-.9 1.63-1.85 3.36-1.85 3.6 0 4.27 2.37 4.27 5.45v6.29z"),
 "X": ("0 0 24 24",
   "M18.9 1.15h3.68l-8.04 9.19L24 22.85h-7.4l-5.8-7.58-6.63 7.58H.49l8.6-9.83"
   "L0 1.15h7.59l5.44 7.2 5.87-7.2zm-1.29 19.5h2.04L6.48 3.24H4.29l13.32 17.41z"),
 "Google Scholar": ("0 0 24 24",
   "M12 2.4 1 8.4l11 6 11-6-11-6zM4.6 12.1v3.6c0 2.1 3.3 3.8 7.4 3.8s7.4-1.7"
   " 7.4-3.8v-3.6L12 16.2l-7.4-4.1zm16.9-1.2v6.5h1.5v-7.3l-1.5.8z"),
 "ACL Anthology": ("0 0 24 24",
   "M11.2 4.9C8.9 3.6 5.9 3.1 2.4 3.4a.9.9 0 0 0-.9.9v13.9c0 .5.4.9.9.9"
   " 3.1-.2 5.9.2 8 1.3.4.2.8-.1.8-.5V5.7a.9.9 0 0 0-.4-.8zm1.6 0a.9.9 0 0 0-.4.8"
   "v14.2c0 .4.4.7.8.5 2.1-1.1 4.9-1.5 8-1.3.5 0 .9-.4.9-.9V4.3a.9.9 0 0 0-.9-.9"
   "c-3.5-.3-6.5.2-8.4 1.5z"),
 "Amazon Science": ("0 0 24 24",
   "M9.4 2h5.2c.5 0 .9.4.9.9s-.4.9-.9.9h-.4v4.5l5.5 9.9A2.6 2.6 0 0 1 17.4 22"
   "H6.6a2.6 2.6 0 0 1-2.3-3.8l5.5-9.9V3.8h-.4a.9.9 0 0 1 0-1.8zm2.3 1.8v5l-2.3 4.1"
   "h5.2l-2.3-4.1v-5h-.6z"),
}


def brand(label, cls="b"):
    """The mark for one profile link, or nothing if there is no mark for it."""
    if label not in BRANDS:
        return ""
    vb, d = BRANDS[label]
    return ('<svg class="%s" viewBox="%s" width="15" height="15" aria-hidden="true" '
            'focusable="false"><path d="%s"/></svg>' % (cls, vb, d))


def icon(key, cls="i"):
    """A 16-unit inline SVG. aria-hidden because every one of these sits next to a
    text label that already says the same thing; announcing it twice is noise."""
    return ('<svg class="%s" viewBox="0 0 24 24" width="16" height="16" '
            'aria-hidden="true" focusable="false"><path d="%s"/></svg>'
            % (cls, ICONS[key]))


def tag_pill(slug, count=None):
    """The topic tag for one paper, or the legend entry when count is given.

    Returns an empty string for a paper with no tag rather than raising, so adding
    a paper to papers.json can never take the build down; check.py is what fails
    on an untagged paper, which is where a data gap belongs.
    """
    t = TAG_OF.get(slug) if count is None else slug
    if not t:
        return ""
    c = '<span class="c">%d</span>' % count if count is not None else ""
    return '<span class="pill">%s%s</span>' % (e(t), c)


def h2(label, key=None, attrs=""):
    """Section heading, optionally with an icon. The icon is inside the h2 so the
    hairline rule above it stays a single element."""
    return "<h2%s>%s%s</h2>\n" % (attrs, icon(key) if key else "", e(label))


CSS = """
:root{--ink:#10202f;--ink2:#293b4a;--mut:#596b79;--faint:#748592;
 --line:#dce4e8;--hair:#edf1f3;--rule:#bdc9cf;--acc:#0d5c63;--acc2:#147983;
 --navy:#0b2239;--navy2:#153e58;--gold:#c99a4b;
 --tint:#edf6f5;--tintline:#cfe3e0;--flag:#8a5a00;--flagbg:#fdf8ee;
 --flagline:#ecdfc4;
 --bg:#fff;--soft:#f5f7f8;--warm:#faf8f3;--warmline:#e8e1d4}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);-webkit-font-smoothing:antialiased;
 font:17px/1.72 system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif}
.wrap{max-width:920px;margin:0 auto;padding:0 30px}
main.wrap{padding-top:48px}
a{color:var(--acc);text-decoration-thickness:1px;text-underline-offset:2px}
a:hover{text-decoration-thickness:2px}
:focus-visible{outline:2px solid var(--acc2);outline-offset:3px;border-radius:2px}
.skip{position:absolute;left:-9999px}
.skip:focus{left:14px;top:12px;z-index:9;background:#fff;padding:7px 13px;
 border:1px solid var(--acc);border-radius:3px}

/* ---- site chrome ---- */
/* The navy bar at the top is the one piece of brand that repeats everywhere,
   including on the social cards, so a shared page and a visited page look like
   the same site. The header stays 15px because Google Scholar reads relative font
   size to decide which line on a paper page is the title, and it must lose to the
   35px h1. Colour does not enter that calculation, so tinting it is free. */
header.site{border-top:3px solid var(--acc);background:rgba(255,255,255,.94);
 border-bottom:1px solid var(--line);position:sticky;top:0;z-index:8;
 backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px)}
header.site .wrap{display:flex;flex-wrap:wrap;gap:2px 22px;align-items:center;
 padding-top:16px;padding-bottom:15px}
header.site .who{font-size:15px;font-weight:720;letter-spacing:.01em;
 color:var(--navy);text-decoration:none}
header.site nav{font-size:14px;display:flex;gap:20px;margin-left:auto}
header.site nav a{color:var(--mut);text-decoration:none;padding-bottom:3px}
header.site nav a:hover{color:var(--acc)}
header.site nav a[aria-current]{color:var(--ink);font-weight:600;
 box-shadow:inset 0 -2px 0 var(--acc)}
footer.site{border-top:1px solid var(--line);margin-top:80px;padding:32px 0 64px;
 background:var(--navy);font-size:13.5px;color:#b8c8d3}
footer.site .wrap{display:flex;flex-wrap:wrap;gap:14px 40px}
footer.site p{margin:0}
/* flex:0 1, not flex:0 0. With shrink disabled this row of six links stayed at its
   454px natural width inside a 390px phone viewport, which pushed the document's
   scroll width to 472px and gave every page on the site a horizontal scrollbar and a
   clipped right edge. Shrink lets it wrap at the separators, which is what the
   separators are for. */
footer.site .links{flex:0 1 auto;min-width:0;color:#e5edf2}
footer.site .fine{flex:1 1 320px;font-size:12.5px;line-height:1.65;max-width:44em}
footer.site a{color:#dce7ed;text-decoration-color:#6e8492}
footer.site a:hover{color:#fff}

/* ---- type scale ---- */
h1{font-size:40px;line-height:1.12;font-weight:680;letter-spacing:-.035em;
 margin:0 0 .42em;text-wrap:balance}
h2{font-size:23px;line-height:1.3;font-weight:680;letter-spacing:-.022em;
 margin:2.35em 0 .7em;padding-top:1.05em;border-top:1px solid var(--line);
 display:flex;align-items:center;gap:9px;position:relative}
/* A short navy segment sitting on the left of the hairline, so a section break
   reads at a glance without a heavy rule or a coloured band. */
h2::before{content:"";position:absolute;top:-1px;left:0;width:26px;height:2px;
 background:var(--acc)}
h3{font-size:13px;line-height:1.4;font-weight:700;letter-spacing:.11em;
 text-transform:uppercase;color:var(--acc);margin:2.4em 0 .55em}

/* ---- brand marks ---- */
/* Filled, not stroked, because a 1.7px stroke at 15px turns the GitHub cat into
   a smudge. Optical size is tuned down to 14px for the two marks that fill their
   whole box, so all six read as the same weight in the row. */
svg.b{flex:0 0 auto;width:15px;height:15px;fill:currentColor;stroke:none}
.chips svg.b{color:var(--acc2);margin-right:8px}
.chips a:hover svg.b{color:var(--acc)}

/* ---- icons ---- */
svg.i{flex:0 0 auto;width:16px;height:16px;fill:none;stroke:var(--acc2);
 stroke-width:1.7;stroke-linecap:round;stroke-linejoin:round;overflow:visible}
h2 svg.i{width:18px;height:18px;stroke-width:1.55}
a svg.i,.qual svg.i{stroke:currentColor;vertical-align:-3px;margin-right:6px;
 stroke-width:1.8}
p{margin:0 0 1.15em}
ul,ol{margin:0 0 1.2em;padding-left:20px}
li{margin:.35em 0}
strong{font-weight:640}
.mut{color:var(--mut)}
.small{font-size:15px}
.tiny{font-size:12.5px;line-height:1.65;color:var(--mut)}
.lab{display:block;font-size:11px;font-weight:700;letter-spacing:.13em;
 text-transform:uppercase;color:var(--faint);margin:0 0 .5em}
.n{font-weight:600;font-variant-numeric:tabular-nums;color:var(--ink)}
.note{border-top:1px solid var(--hair);padding-top:13px;margin:1.6em 0 0}
nav.crumb{font-size:12.5px;color:var(--faint);margin:0 0 20px;letter-spacing:.01em}
nav.crumb a{color:var(--mut);text-decoration:none}
nav.crumb a:hover{text-decoration:underline}

/* ---- paper masthead ---- */
.byline{font-size:16px;font-weight:400;text-transform:none;letter-spacing:0;
 color:var(--ink2);margin:0 0 .5em;line-height:1.55}
.byline strong{font-weight:640;color:var(--ink)}
.venue{font-size:13.5px;color:var(--mut);margin:0 0 1.4em;line-height:1.6;
 font-variant-numeric:tabular-nums}
/* Amber, not grey, for "not peer reviewed": it is a caveat, and a caveat that
   looks like every other grey label is one nobody reads. One warm hue only. */
.flag{display:inline-block;font-size:10.5px;font-weight:700;letter-spacing:.09em;
 text-transform:uppercase;color:var(--flag);background:var(--flagbg);
 border:1px solid var(--flagline);border-radius:2px;padding:2px 7px;white-space:nowrap}
.actions{margin:0;font-size:13.5px;display:flex;flex-wrap:wrap;gap:8px;
 padding-bottom:28px;border-bottom:1px solid var(--line)}
.actions a,.chips a{display:inline-flex;align-items:center;padding:7px 13px;
 text-decoration:none;border:1px solid var(--line);border-radius:999px;background:#fff;
 color:var(--ink2)}
.actions a:hover,.chips a:hover{border-color:var(--acc2);color:var(--acc);
 background:var(--tint)}
.actions a:first-child{border-color:var(--acc2);color:var(--acc);font-weight:600;
 background:var(--tint)}

/* ---- the two signature blocks ---- */
.tldr{margin:28px 0 2px;border-left:3px solid var(--acc);padding:1px 0 1px 21px}
.tldr p{font-size:20px;line-height:1.5;letter-spacing:-.012em;color:var(--ink);margin:0}
.topics{font-size:15px;color:var(--mut)}
.candid{background:var(--warm);border:1px solid var(--warmline);border-radius:5px;
 padding:22px 26px;margin:2.5em 0 1.4em}
.candid h2{border-top:0;padding-top:0;margin:0 0 .45em;font-size:18px}
.candid h2::before{display:none}
.candid h2 svg.i{stroke:var(--flag)}
.candid p{margin:0;color:var(--ink2);font-size:16px;line-height:1.68}
.calib{background:var(--tint);border:1px solid var(--tintline);border-radius:5px;
 border-left:3px solid var(--acc2);padding:18px 22px;margin:.2em 0 1.9em;
 font-size:16px;line-height:1.68;color:var(--ink2);font-variant-numeric:tabular-nums}
.namenote{border-top:1px solid var(--hair);padding-top:14px;font-size:14px;
 line-height:1.65;color:var(--mut)}

/* ---- key results ---- */
ul.kr{list-style:none;padding:0;margin:.3em 0 0}
ul.kr li{margin:0;padding:13px 0;border-top:1px solid var(--hair);
 font-size:16px;line-height:1.62}
ul.kr li:first-child{border-top:0;padding-top:4px}
/* A result that was null or went the wrong way gets the warm hue, the same one
   the preprint caveat uses. The colour carries the meaning; it is not decoration. */
ul.kr li.neg{border-left:2px solid var(--flagline);padding-left:18px;color:var(--ink2)}
.qual{display:inline-block;font-size:10px;font-weight:700;letter-spacing:.1em;
 text-transform:uppercase;color:var(--flag);border:1px solid var(--flagline);
 background:var(--flagbg);border-radius:2px;padding:1px 6px;margin-right:8px;
 vertical-align:1.5px;white-space:nowrap}

/* ---- prose furniture ---- */
.abs{line-height:1.78}
figure{margin:2.1em 0 1.6em;padding:0}
figure img{max-width:100%;height:auto;display:block;border:1px solid var(--line);
 border-radius:3px;background:#fff}
figcaption{font-size:12.5px;color:var(--mut);margin-top:.75em;line-height:1.65}
pre{background:var(--soft);border:1px solid var(--line);border-radius:4px;
 padding:15px 17px;font-size:12.5px;line-height:1.55;margin:0 0 1.2em;
 white-space:pre-wrap;overflow-wrap:break-word}
code{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
.back{margin:2.6em 0 0;font-size:14px}
.back a{text-decoration:none;font-weight:600}
.back a:hover{text-decoration:underline}

/* ---- homepage ---- */
.home{background:linear-gradient(180deg,#f1f6f6 0,#fff 540px)}
.home main.wrap{padding-top:40px}
.hero{display:flex;gap:38px;align-items:center;margin:0 0 22px;padding:42px 44px;
 color:#fff;background:linear-gradient(135deg,var(--navy) 0%,var(--navy2) 72%,#17636b 100%);
 border-radius:18px;box-shadow:0 22px 60px rgba(10,34,55,.16);position:relative;overflow:hidden}
.hero::after{content:"";position:absolute;width:260px;height:260px;border-radius:50%;
 right:-100px;top:-130px;border:1px solid rgba(255,255,255,.16);
 box-shadow:0 0 0 48px rgba(255,255,255,.035),0 0 0 96px rgba(255,255,255,.025)}
.hero picture{position:relative;z-index:1}
.hero img{width:154px;height:154px;border-radius:14px;flex:0 0 auto;
 border:1px solid rgba(255,255,255,.3);object-fit:cover;box-shadow:0 14px 34px rgba(0,0,0,.22)}
.hero .lead{flex:1 1 auto;min-width:0}
.hero h1{margin:0 0 .25em;color:#fff;font-size:48px;font-weight:680}
.eyebrow{margin:0 0 12px;color:#9fd3d2;font-size:11.5px;font-weight:750;
 letter-spacing:.15em;text-transform:uppercase}
.tag{font-size:18px;color:#d6e3ea;margin:0;line-height:1.58;max-width:54ch}
.tag .role{color:#fff;font-weight:680}
.chips{display:flex;flex-wrap:wrap;gap:8px;font-size:13px;margin:0 0 34px;padding:0;
 list-style:none}
.home .chips a{background:rgba(255,255,255,.82);border-color:#d4e2e4;
 box-shadow:0 3px 12px rgba(15,45,58,.06)}
.home .chips a:hover{background:#fff;transform:translateY(-1px)}
.home .bp{font-size:18px;line-height:1.72;color:var(--ink2);max-width:76ch}
.signal-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin:28px 0 16px}
.signal{position:relative;padding:21px 20px 20px;border:1px solid var(--line);
 border-radius:10px;background:#fff;box-shadow:0 8px 28px rgba(15,42,55,.055);
 overflow:hidden}
.signal::before{content:"";position:absolute;inset:0 auto auto 0;width:100%;height:3px;
 background:linear-gradient(90deg,var(--acc),var(--acc2) 44%,transparent 88%)}
.signal-head{display:flex;align-items:baseline;justify-content:space-between;
 gap:12px;margin-bottom:11px}
.signal .lab{color:var(--acc);margin:0}
.signal-mark{display:grid;place-items:center;flex:0 0 auto;width:31px;height:31px;
 border-radius:8px;background:var(--tint);border:1px solid var(--tintline)}
.signal-mark svg.i{width:17px;height:17px;stroke:var(--acc2);stroke-width:1.65}
.signal p{font-size:14.5px;line-height:1.58;color:var(--mut);margin:0}
.signal p strong{display:block;margin-bottom:4px;color:var(--ink);
 font-size:16px;line-height:1.38;letter-spacing:-.008em}
.contact-tabs{margin:.5em 0 1.5em;border:1px solid var(--line);border-radius:12px;
 background:#fff;box-shadow:0 8px 28px rgba(15,42,55,.05);overflow:hidden}
.contact-tabs>input{position:absolute;opacity:0;pointer-events:none}
.contact-tab-list{display:flex;gap:4px;padding:7px;border-bottom:1px solid var(--line);
 background:var(--soft)}
.contact-tab-list label{padding:9px 14px;border-radius:7px;color:var(--mut);
 font-size:12.5px;font-weight:680;cursor:pointer}
#contact-general:checked~.contact-tab-list label[for="contact-general"],
#contact-speaking:checked~.contact-tab-list label[for="contact-speaking"]{
 color:var(--ink);background:#fff;box-shadow:0 1px 5px rgba(15,42,55,.1)}
#contact-general:focus-visible~.contact-tab-list label[for="contact-general"],
#contact-speaking:focus-visible~.contact-tab-list label[for="contact-speaking"]{
 outline:2px solid var(--acc2);outline-offset:2px}
.contact-panel{display:none;padding:22px 24px 23px}
.contact-panel p{max-width:68ch;margin:0;color:var(--ink2);line-height:1.68}
.contact-panel p+p{margin-top:10px}
.contact-panel .contact-lead{font-size:17px;font-weight:650;color:var(--ink)}
#contact-general:checked~.contact-panels .contact-general,
#contact-speaking:checked~.contact-panels .contact-speaking{display:block}
ul.tl{list-style:none;padding:0;margin:.2em 0 1.4em}
ul.tl li{margin:0;padding:10px 0;border-top:1px solid var(--hair)}
ul.tl li:first-child{border-top:0}
ul.tl>li>a,ul.tl .t{font-size:16px;line-height:1.45;color:var(--ink);font-weight:600;
 letter-spacing:-.008em}
ul.tl>li>a{text-decoration:underline;text-decoration-color:var(--rule);
 text-underline-offset:3px}
ul.tl>li>a:hover{color:var(--acc);text-decoration-color:var(--acc)}
ul.tl .v{display:block;font-size:12.5px;line-height:1.5;color:var(--faint);
 margin-top:3px;font-variant-numeric:tabular-nums}
ul.tl .v a{color:var(--mut);text-decoration-color:var(--rule)}

/* ---- what I work on ---- */
/* Two columns, not four stacked blocks. This section used to be a heading, then a
   paragraph, then a list of long paper titles, four times over, which is one wall of
   text with no way into it. Now the left rail answers "what, when, how many" and the
   right column answers "which papers", so a reader can go down the left edge, pick a
   topic, and only then read across. The rail is 186px because the longest heading
   wraps to two lines there and no further. */
.work{margin:.3em 0 1.7em;padding:0}
.work .row{display:grid;grid-template-columns:210px 1fr;gap:34px;
 padding:26px 0;border-top:1px solid var(--line)}
.work .row:first-child{border-top:0;padding-top:8px}
.work dt{margin:0;font-size:16.5px;font-weight:650;color:var(--ink);
 line-height:1.32;letter-spacing:-.01em}
/* The year span and the count are computed from papers.json, never typed, so the
   rail cannot drift from the list beside it. */
.work .when{display:block;margin-top:6px;font-size:12.5px;color:var(--faint);
 font-variant-numeric:tabular-nums;line-height:1.5}
.work .pill{margin-top:8px}
.work dd{margin:0;min-width:0}
.work dd .g{margin:0 0 4px;font-size:15.5px;line-height:1.56;color:var(--mut);
 max-width:60ch}
.work dd ul.tl{margin:.55em 0 0}
.work dd ul.tl li{padding:9px 0}
.work dd ul.tl>li>a{font-size:15px;font-weight:600;text-decoration:none;
 border-bottom:1px solid var(--rule)}
.work dd ul.tl>li>a:hover{border-bottom-color:var(--acc)}
/* The one-line form of the result panel. This rail is an index, so it carries the
   size of the result and what it was measured on, and leaves the bars and the
   baseline's own number to the panel further down the page. Tabular numerals so the
   deltas line up down the column and can be compared without reading each one. */
.work dd ul.tl .d{display:block;margin-top:3px;font-size:12.5px;font-weight:650;
 color:var(--acc);font-variant-numeric:tabular-nums;letter-spacing:-.005em}
.work dd ul.tl .d .on{font-weight:400;color:var(--faint);letter-spacing:0}

/* ---- experience ---- */
/* Same left-rail idea as above, narrower, because a year range is short and fixed
   width. Years only, no months: months read as a resume, and the useful signal here
   is the shape of the path, not its precise boundaries. */
ol.cv{list-style:none;margin:.3em 0 1.7em;padding:0}
ol.cv>li{display:grid;grid-template-columns:118px 1fr;gap:24px;
 padding:16px 0;border-top:1px solid var(--hair)}
ol.cv>li:first-child{border-top:0;padding-top:6px}
ol.cv .yr{font-size:13px;color:var(--faint);font-variant-numeric:tabular-nums;
 line-height:1.62;white-space:nowrap}
ol.cv .role{margin:0;font-size:16px;font-weight:650;color:var(--ink);
 line-height:1.42;letter-spacing:-.008em}
ol.cv .org{display:block;margin-top:2px;font-size:13.5px;font-weight:400;
 color:var(--acc2)}
ol.cv .g{margin:6px 0 0;font-size:15px;line-height:1.55;color:var(--mut);
 max-width:64ch}

/* ---- topic tags ---- */
/* Named .pill and not .tag: .tag is the homepage tagline, and when this rule was
   called .tag it won on specificity and rendered the tagline as a 10.5px uppercase
   letter-spaced blue pill, which is unreadable. Two different things must not
   share a class name just because the same English word fits both.

   One tint, not five. Five tags in five different hues would look like a
   dashboard and would imply a colour taxonomy that does not exist; the tag is
   here to be read, not decoded. Uppercase at 10.5px because it has to lose to
   both the venue line beside it and the title beneath it. */
.pill{display:inline-flex;align-items:center;font-size:10.5px;font-weight:700;
 letter-spacing:.1em;text-transform:uppercase;color:var(--acc);
 background:var(--tint);border:1px solid var(--tintline);border-radius:2px;
 padding:3px 7px;white-space:nowrap;line-height:1.35}
/* The legend is the only place the counts appear, so a reader can see that the
   current line of work has three papers and the oldest has two, without
   counting rows. */
.legend{display:flex;flex-wrap:wrap;gap:8px;align-items:center;
 margin:0 0 2.1em;padding-bottom:1.5em;border-bottom:1px solid var(--hair)}
.legend .lg{display:inline-flex;align-items:center;gap:7px;font-size:12.5px;
 color:var(--mut);margin-right:4px}
.legend .pill .c{margin-left:6px;color:var(--faint);font-weight:400;letter-spacing:0}

/* ---- publication cards ---- */
.pub{display:flex;gap:24px;align-items:flex-start;
 padding:28px 0;border-top:1px solid var(--line)}
.pub .body{flex:1 1 auto;min-width:0}
/* ---- the result panel ---- */
/* The right-hand column of a publication row. This was a cropped figure through two
   designs; see result_panel() in build.py for why it stopped being one. 240px is
   inherited from that crop, which was itself the widest box the layout could give up
   without squeezing the title column, and it turns out to be about the narrowest a
   two-bar chart with a label under each bar can be.

   No fixed height, unlike the image it replaced: the panel is the shorter of the two
   columns in every row, so it cannot make a row taller, and letting it size itself
   avoids either clipping a long baseline label or padding a short one. */
.pub .res{flex:0 0 250px;order:2;margin-top:4px;padding:14px 15px 13px;
 border:1px solid var(--line);border-radius:9px;background:var(--soft)}
.pub .res .hd{display:flex;gap:8px;align-items:baseline;justify-content:space-between;
 margin:0}
/* The benchmark name is the heading here, not the metric: a reader who knows the
   field recognises LOCOMO or SQuAD instantly, and one who does not gets the metric
   spelled out in words on the next line.

   Not uppercased, unlike every other small label on this site. Benchmark names are
   proper nouns with their own capitalisation, and text-transform destroyed it: it
   turned Xtr-WikiQA into XTR-WIKIQA, KGQAGen-10k into KGQAGEN-10K, and worst of all
   turned tau-bench, whose name starts with a Greek tau, into T-BENCH, which is a
   different benchmark's name. A style rule is not worth misspelling somebody's
   dataset. */
.pub .res .bm{font-size:11.5px;font-weight:700;letter-spacing:.005em;
 color:var(--acc);line-height:1.32}
/* The gap is derived from the two values in build.py, never typed. It is the only
   number on the panel allowed to be this size, because it is the one thing a reader
   skimming thirteen rows is comparing. */
.pub .res .dl{font-size:13px;font-weight:700;color:var(--acc);white-space:nowrap;
 font-variant-numeric:tabular-nums;letter-spacing:-.01em}
.pub .res .mt{margin:2px 0 0;font-size:11.5px;line-height:1.4;color:var(--mut)}
.pub .res .bars{margin-top:11px;display:flex;flex-direction:column;gap:8px}
/* Value, bar, then label under both. The value sits before the bar so the numbers
   share one left edge and can be read as a column without the eye tracking across
   bars of different lengths. */
.pub .res .r{display:grid;grid-template-columns:44px 1fr;gap:2px 9px;
 align-items:center}
.pub .res .r .n{font-size:13px;font-weight:600;color:var(--faint);text-align:right;
 font-variant-numeric:tabular-nums;letter-spacing:-.01em}
.pub .res .r.us .n{font-size:15px;font-weight:700;color:var(--acc)}
.pub .res .r .t{height:13px;border-radius:2px;background:#fff;
 border:1px solid var(--line);position:relative;overflow:hidden}
.pub .res .r .t i{position:absolute;left:0;top:0;bottom:0;background:var(--rule)}
.pub .res .r.us .t i{background:var(--acc)}
.pub .res .r .l{grid-column:2;font-size:10.5px;line-height:1.35;color:var(--faint)}
.pub .res .r.us .l{color:var(--mut)}
/* The footnote is where a result that cuts both ways is admitted at the same size as
   the result itself, rather than being left for the paper page to disclose. */
.pub .res .fn{margin:10px 0 0;padding-top:9px;border-top:1px solid var(--line);
 font-size:10.5px;line-height:1.42;color:var(--faint)}
h2+.pub,p+.pub{border-top:0;padding-top:4px}
.pub .meta{display:flex;flex-wrap:wrap;gap:3px 12px;align-items:baseline;margin:0 0 .3em;
 font-size:12.5px;line-height:1.5;color:var(--mut);font-variant-numeric:tabular-nums}
.pub .cites{margin-left:auto;white-space:nowrap;color:var(--faint)}
.pub h3{margin:0 0 .32em;font-size:20px;line-height:1.3;font-weight:660;
 letter-spacing:-.016em;text-transform:none;color:var(--ink)}
.pub h3 a{color:var(--ink);text-decoration:underline;
 text-decoration-color:var(--rule);text-underline-offset:3px}
.pub h3 a:hover{color:var(--acc);text-decoration-color:var(--acc)}
.pub .who{font-size:13.5px;color:var(--mut);margin:0 0 .5em;line-height:1.55}
.pub .who strong{color:var(--ink2);font-weight:640}
.pub .sum{font-size:15px;line-height:1.62;margin:0;color:var(--ink2)}
.contribution{margin:12px 0 0;padding:11px 13px;border-left:3px solid var(--acc2);
 border-radius:0 6px 6px 0;background:var(--tint);font-size:14px;line-height:1.55;
 color:var(--ink2)}
.contribution .lab{display:inline;margin:0 7px 0 0;color:var(--acc);font-size:10px}
.pub.featured{margin:14px 0;padding:22px;border:1px solid var(--line);border-radius:14px;
 background:#fff;box-shadow:0 10px 34px rgba(15,42,55,.065);gap:24px}
.pub.featured+.pub.featured{border-top:1px solid var(--line)}
.paperthumb{flex:0 0 224px;display:block;align-self:flex-start;border-radius:9px;
 overflow:hidden;background:var(--soft);border:1px solid var(--line)}
.paperthumb picture{display:block}
.paperthumb img{display:block;width:100%;height:auto;aspect-ratio:4/3;object-fit:contain}
.paperthumb:hover{border-color:var(--acc2);box-shadow:0 8px 24px rgba(13,92,99,.14)}
.impact{display:inline-flex;align-items:center;border-radius:999px;padding:3px 9px;
 color:var(--acc);background:var(--tint);border:1px solid var(--tintline);
 font-size:11px;font-weight:720;white-space:nowrap;font-variant-numeric:tabular-nums}

/* ---- reading measure ---- */
/* 68 characters is the top of the comfortable range for prose that is read
   start to finish. The wrap stays 740px because the list rows, the figures and
   the action buttons all want that width; only the blocks somebody actually
   reads through are narrowed. The panels and metadata lines are left alone on
   purpose: capping a block that has a background makes it look misaligned
   rather than considered. */
p.bp,p.abs,p.topics,section.candid p,.pub .sum,.tldr p{max-width:68ch}
/* The abstract is the longest single block on the site and the one Google
   Scholar reads, so it gets the most generous leading of anything here. */
p.abs{line-height:1.78}

/* ---- earlier work table ---- */
table.earlier{width:100%;border-collapse:collapse;font-size:14px;margin:.4em 0 1.4em;
 font-variant-numeric:tabular-nums}
table.earlier th,table.earlier td{text-align:left;padding:11px 14px 11px 0;
 border-bottom:1px solid var(--hair);vertical-align:top}
table.earlier thead th{font-size:10.5px;font-weight:700;letter-spacing:.12em;
 text-transform:uppercase;color:var(--faint);padding-bottom:8px;
 border-bottom:1px solid var(--rule)}
table.earlier .n{text-align:right;white-space:nowrap;padding:11px 0 11px 16px;width:1%;
 color:var(--ink2);font-weight:400}
table.earlier td a{color:var(--ink);font-weight:600;
 text-decoration-color:var(--rule);text-underline-offset:3px}
table.earlier td a:hover{color:var(--acc)}
table.earlier .tiny{display:block;margin-top:2px;font-weight:400}

@media (max-width:640px){
 body{font-size:16px;line-height:1.68}
 .wrap{padding:0 18px}
 main.wrap{padding-top:26px}
 h1{font-size:27px;letter-spacing:-.02em}
 h2{font-size:19px;margin-top:2.3em;padding-top:.95em}
 footer.site{margin-top:44px}
 footer.site .wrap{gap:12px}
 .home main.wrap{padding-top:18px}
 .hero{flex-direction:column;align-items:flex-start;gap:18px;margin-bottom:20px;
  padding:26px 24px;border-radius:12px}
 .hero img{width:104px;height:104px;border-radius:10px}
 .hero h1{font-size:34px}
 .eyebrow{margin-bottom:8px}
 .tag{font-size:16px}
 .signal-grid{grid-template-columns:1fr;gap:9px}
 .signal{padding:16px 17px}
 .contact-panel{padding:18px}
 .contact-tab-list label{padding:8px 10px}
 .tldr{margin-top:24px;padding-left:16px}
 .tldr p{font-size:18px}
 .candid,.calib{padding:16px 18px}
 .abs{line-height:1.72}
 .pub{padding:19px 0;gap:14px;flex-direction:column}
 /* The row stacks on a phone and the panel goes under the summary, not above the
    title. A 240px chart squeezed into a 300px column beside the text is unreadable,
    and putting it first would push the title, which is what a reader is scanning for,
    below the fold of every row. order is what moves it; flex-direction:column keeps
    it full width once it is there. */
 .pub .res{flex:1 1 auto;width:100%;margin-top:12px}
 .pub .res .r{grid-template-columns:52px 1fr}
 .pub h3{font-size:17px}
 .pub .meta,.pub .cites{display:block;margin-left:0}
 .pub.featured{padding:16px;gap:17px}
 .paperthumb{width:100%;flex:1 1 auto}
 .impact{display:inline-flex;margin-top:6px}
 /* Both rails collapse to one column on a phone. A 186px label column next to a
    140px text column is worse than no rail at all. */
 .work .row,ol.cv>li{grid-template-columns:1fr;gap:8px}
 .work .when{margin-top:4px}
 ol.cv .yr{order:-1;font-size:12.5px}
 ul.kr li{font-size:15.5px}
}
""".strip()


def head(title, desc, canonical, og_type, og_image, og_image_alt,
         extra_meta="", jsonld=(), img_w=1200, img_h=630):
    gv = SITE.get("google_site_verification") or ""
    ver = ('<meta name="google-site-verification" content="%s">\n' % e(gv)) if gv else ""
    blocks = "\n".join(
        '<script type="application/ld+json">\n%s\n</script>'
        % json.dumps(b, indent=2, ensure_ascii=False)
        for b in jsonld
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<link rel="canonical" href="{e(canonical)}">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="icon" href="/favicon-32.png" sizes="32x32" type="image/png">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<meta name="description" content="{e(desc)}">
<meta name="author" content="{e(SITE['name'])}">
{ver}<meta property="og:type" content="{e(og_type)}">
<meta property="og:site_name" content="{e(SITE['name'])}">
<meta property="og:locale" content="en_US">
<meta property="og:url" content="{e(canonical)}">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:image" content="{e(og_image)}">
<meta property="og:image:width" content="{img_w}">
<meta property="og:image:height" content="{img_h}">
<meta property="og:image:alt" content="{e(og_image_alt)}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:site" content="{e(SITE['twitter'])}">
<meta name="twitter:creator" content="{e(SITE['twitter'])}">
<meta name="twitter:title" content="{e(title)}">
<meta name="twitter:description" content="{e(desc)}">
<meta name="twitter:image" content="{e(og_image)}">
<meta name="twitter:image:alt" content="{e(og_image_alt)}">
{extra_meta}<style>{CSS}</style>
{blocks}
</head>
"""


def site_header(active=""):
    def link(href, label, key):
        cur = ' aria-current="page"' if key == active else ""
        return '<a href="%s"%s>%s</a>' % (href, cur, label)
    body_class = ' class="home"' if active == "home" else ""
    return """<body%s>
<a class="skip" href="#main">Skip to content</a>
<header class="site"><div class="wrap">
<a class="who" href="/" aria-label="Ankit Chadha, home">AC</a>
<nav aria-label="Site">%s %s %s %s %s</nav>
</div></header>
<main class="wrap" id="main">
""" % (
        body_class,
        link("/", "About", "home"),
        link("/research/", "Research", "research"),
        link("/publications/", "Publications", "pubs"),
        '<a href="%s" rel="me">Scholar</a>' % e(SITE["links"][0]["url"]),
        link("/contact/", "Contact me", "contact"),
    )


def site_footer():
    ln = " &middot; ".join(
        '<a href="%s" rel="me noopener">%s</a>' % (e(l["url"]), e(l["label"]))
        for l in SITE["links"]
    )
    return """</main>
<footer class="site"><div class="wrap">
<p class="links">%s</p>
<p class="fine">%s, %s.</p>
</div></footer>
</body>
</html>
""" % (
        ln,
        e(SITE["name"]),
        e(SITE["location"]),
    )


# ---------------------------------------------------------------- JSON-LD

def person_node():
    node = {
        "@context": "https://schema.org",
        "@type": "Person",
        "@id": url("#person"),
        "name": SITE["name"],
        "givenName": SITE["given_name"],
        "familyName": SITE["family_name"],
        "alternateName": SITE["alternate_names"],
        "url": url("/"),
        "mainEntityOfPage": {"@id": url("#profilepage")},
        "image": url("/assets/img/headshot-800.jpg"),
        "jobTitle": SITE["job_title"],
        "description": SITE["tagline"],
        # schema.org has no "different from" property, so disambiguatingDescription
        # is the designated slot for this. Every namesake below was checked at
        # source: the power-electronics and clinical-medicine work sits in the same
        # merged Semantic Scholar record as his, and Wikidata Q55958099 is an
        # Indian writer of the same name who died in 2018. Google requires markup
        # to reflect visible content, so the same substance is in the bio.
        "disambiguatingDescription": SITE["disambiguating_description"],
        "worksFor": {"@type": "Organization", "name": SITE["employer"],
                     "url": "https://www.amazon.com/"},
        "affiliation": {"@type": "Organization", "name": SITE["employer"],
                        "url": "https://www.amazon.com/"},
        # alumniOf only for a school that granted a degree. Stanford is listed under
        # Education because the graduate AI courses are real and relevant, but they
        # were coursework, so claiming alumniOf there would assert a degree that does
        # not exist. Gated on an explicit flag rather than on parsing the degree
        # string, so the claim is a decision in the data and not a side effect.
        "alumniOf": [
            {"@type": "CollegeOrUniversity", "name": ed["school"], "url": ed["url"]}
            for ed in SITE["education"] if ed.get("alumni")
        ],
        "knowsAbout": SITE["knows_about"],
        # Entity resolution works by corroboration across independent registries,
        # and this name is shared by at least four other published researchers
        # plus a near-namesake who is a real co-author on two of the early papers.
        # More verified identifiers is the single highest-value fix for that.
        # ORCID 0000-0002-5029-0136 was confirmed by fetching the public record:
        # its homepage field is ankitrchadha.com, the same URL on his Scholar
        # profile, and its three works are exactly three of his undergraduate
        # papers. OpenAlex has him split across two records, both Amazon.
        "identifier": [
            {"@type": "PropertyValue", "propertyID": "ORCID",
             "value": "0000-0002-5029-0136"},
            {"@type": "PropertyValue", "propertyID": "Google Scholar",
             "value": "hcslcm0AAAAJ"},
            {"@type": "PropertyValue", "propertyID": "OpenAlex",
             "value": "A5027218595"},
        ],
        "sameAs": SITE["same_as"],
    }
    return node


def website_node():
    return {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "@id": url("#website"),
        "url": url("/"),
        "name": SITE["name"],
        "inLanguage": "en",
        "publisher": {"@id": url("#person")},
    }


def profilepage_node():
    return {
        "@context": "https://schema.org",
        "@type": "ProfilePage",
        "@id": url("#profilepage"),
        "url": url("/"),
        "name": SITE["name"],
        "dateModified": SITE["build_date"],
        "isPartOf": {"@id": url("#website")},
        "mainEntity": {"@id": url("#person")},
    }


def article_node(p, c):
    slug = p["slug"]
    canon = url("/papers/%s/" % slug)
    authors = []
    for a in p["authors"]:
        node = {"@type": "Person", "name": a}
        if a == "Ankit Chadha":
            # Point at the fully described Person on the homepage instead of
            # repeating a blank node 13 times. Same @id means a consumer can
            # merge paper, author and institution into one graph; without it,
            # each page describes an anonymous person who happens to share a
            # name with at least four other published researchers.
            node["@id"] = url("#person")
            node["url"] = url("/")
            node["sameAs"] = SITE["same_as"][:1]
            node["affiliation"] = {"@type": "Organization", "name": "Amazon"}
        authors.append(node)
    ident, same = [], []
    if p.get("doi"):
        ident.append({"@type": "PropertyValue", "propertyID": "DOI", "value": p["doi"]})
        same.append("https://doi.org/" + p["doi"])
    if p.get("arxiv_id"):
        ident.append({"@type": "PropertyValue", "propertyID": "arXiv",
                      "value": p["arxiv_id"]})
        same.append("https://arxiv.org/abs/" + p["arxiv_id"])
    node = {
        "@context": "https://schema.org",
        "@type": ["ScholarlyArticle", "Article"],
        "@id": canon + "#article",
        "mainEntityOfPage": canon,
        "url": canon,
        "headline": p["title"],
        "name": p["title"],
        "abstract": c["abstract"],
        "description": c["tldr"],
        "inLanguage": "en",
        "datePublished": iso(p["citation_publication_date"]),
        "dateModified": SITE["build_date"],
        "author": authors,
        "keywords": c["topics"],
        "image": [url("/assets/img/figs/%s.jpg" % p["img"])],
        "encoding": {"@type": "MediaObject",
                     "contentUrl": canon + p["pdf_filename"],
                     "encodingFormat": "application/pdf"},
    }
    # publisher is who issued the proceedings, not who wrote the paper. Pointing
    # it at the author claimed he published ACL, NAACL, CIKM, Interspeech and
    # Springer. Omitted entirely where there is no publisher: the workshop, the
    # preprints, and the two papers accepted but not yet in proceedings.
    if p.get("publisher"):
        node["publisher"] = {"@type": "Organization", "name": p["publisher"]}
    if p.get("venue_long"):
        # publication takes a PublicationEvent. isPartOf does not: its range is
        # CreativeWork or URL, so a PublicationEvent there was a range violation,
        # and it carried nothing that publication does not already carry.
        node["publication"] = {"@type": "PublicationEvent", "name": p["venue_long"]}
    if p.get("pages"):
        fp, lp = pages_split(p["pages"])
        node["pagination"] = p["pages"].replace("-", "–")
        # pageStart and pageEnd are the parsed form. Both are valid on Article and
        # both are what a reference manager reads; pagination alone makes it guess.
        node["pageStart"], node["pageEnd"] = fp, lp
    if ident:
        node["identifier"] = ident
    if same:
        node["sameAs"] = same
    # codeRepository is deliberately NOT emitted here: schema.org scopes it to
    # SoftwareSourceCode, so on a ScholarlyArticle it is a domain violation of the
    # same kind isPartOf was. The visible "Code" link is the honest place for it.
    if p.get("license_url"):
        node["license"] = p["license_url"]
    if p.get("arxiv_id"):
        node["isBasedOn"] = "https://arxiv.org/abs/" + p["arxiv_id"]
    return node


def breadcrumb_node(p):
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Publications",
             "item": url("/publications/")},
            {"@type": "ListItem", "position": 2, "name": p["title"]},
        ],
    }


# ---------------------------------------------------------------- paper page

def citation_meta(p, c):
    canon = url("/papers/%s/" % p["slug"])
    m = ['<meta name="citation_title" content="%s">' % e(p["title"])]
    for a in p["authors"]:
        parts = a.rsplit(" ", 1)
        m.append('<meta name="citation_author" content="%s">'
                 % e("%s, %s" % (parts[1], parts[0]) if len(parts) == 2 else a))
    m.append('<meta name="citation_publication_date" content="%s">'
             % e(p["citation_publication_date"]))
    if p.get("arxiv_date"):
        m.append('<meta name="citation_online_date" content="%s">'
                 % e(p["arxiv_date"].replace("-", "/")))
    # Venue. Conference title only, never alongside a journal title, and never on a preprint.
    if p.get("venue_long"):
        m.append('<meta name="citation_conference_title" content="%s">'
                 % e(p["venue_long"]))
    fp, lp = pages_split(p.get("pages"))
    if fp:
        m.append('<meta name="citation_firstpage" content="%s">' % fp)
        m.append('<meta name="citation_lastpage" content="%s">' % lp)
    if p.get("doi"):
        m.append('<meta name="citation_doi" content="%s">' % e(p["doi"]))
    if p.get("arxiv_id"):
        m.append('<meta name="citation_arxiv_id" content="%s">' % e(p["arxiv_id"]))
    m.append('<meta name="citation_pdf_url" content="%s">' % e(canon + p["pdf_filename"]))
    m.append('<meta name="citation_abstract" content="%s">' % e(c["abstract"]))
    m.append('<meta name="citation_keywords" content="%s">' % e("; ".join(c["topics"])))
    m.append('<meta name="citation_language" content="en">')
    # Dublin Core, for reference managers and non-Google harvesters.
    m.append('<meta name="DC.title" content="%s">' % e(p["title"]))
    for a in p["authors"]:
        parts = a.rsplit(" ", 1)
        m.append('<meta name="DC.creator" content="%s">'
                 % e("%s, %s" % (parts[1], parts[0]) if len(parts) == 2 else a))
    m.append('<meta name="DC.issued" content="%s">'
             % e(iso(p["citation_publication_date"])))
    if p.get("venue_long"):
        m.append('<meta name="DC.relation.ispartof" content="%s">' % e(p["venue_long"]))
    m.append('<meta name="DC.identifier" content="%s">' % e(canon + p["pdf_filename"]))
    m.append('<meta name="DC.language" content="en">')
    # Article namespace
    d = iso(p["citation_publication_date"])
    if len(d) == 10:
        m.append('<meta property="article:published_time" content="%sT00:00:00Z">' % d)
    m.append('<meta property="article:modified_time" content="%sT00:00:00Z">'
             % SITE["build_date"])
    m.append('<meta property="article:author" content="%s">' % url("/"))
    for t in c["topics"][:6]:
        m.append('<meta property="article:tag" content="%s">' % e(t))
    return "\n".join(m) + "\n"


def paper_page(p):
    c = CONTENT.get(p["slug"])
    if not c:
        return None
    slug = p["slug"]
    canon = url("/papers/%s/" % slug)
    fw, fh = FIGDIMS[p["img"]]

    desc = c.get("meta_description") or c["tldr"]
    if len(desc) > 320:
        desc = desc[:317].rsplit(" ", 1)[0] + "..."

    card = url("/assets/img/cards/%s-1200x630.jpg" % slug)

    parts = [head(
        title="%s | %s" % (p["title"], SITE["name"]),
        desc=desc,
        canonical=canon,
        og_type="article",
        og_image=card,
        og_image_alt=c["figure_alt"],
        extra_meta=citation_meta(p, c),
        jsonld=[article_node(p, c), breadcrumb_node(p)],
    )]
    parts.append(site_header())
    parts.append('<nav class="crumb" aria-label="Breadcrumb">'
                 '<a href="/">Home</a> / <a href="/publications/">Publications</a>'
                 '</nav>\n<article>\n')
    parts.append('<h1 class="citation_title">%s</h1>\n' % e(p["title"]))
    parts.append('<h3 class="citation_author byline">%s</h3>\n' % author_line_html(p))

    ven = [e(p["venue_short"])]
    if p.get("pages"):
        ven.append("pages " + p["pages"].replace("-", "&ndash;"))
    ven = ", ".join(ven) + " &middot; " + e(p["affiliations"])
    if pub_status(p) == "preprint":
        ven += ' <span class="flag">Preprint, not peer reviewed</span>'
    if p.get("accepted_note"):
        # Same block as the venue, one step quieter: it is the provenance of the
        # venue line, and it explains why the citation below points at arXiv.
        ven += '<br><span class="tiny">%s</span>' % e(p["accepted_note"])
    # The tag sits at the head of the venue line rather than above the title,
    # because Google Scholar reads the paper page top down looking for the title
    # and the byline, and anything inserted between them is a risk for no gain.
    parts.append('<p class="venue">%s%s</p>\n' % (tag_pill(p["slug"]), ven))

    # The PDF is first and stays first: it is the thing a reader came for, and it
    # is the file Google Scholar cross-checks against the citation meta block.
    acts = ['<a href="%s">%sPDF</a>' % (e(p["pdf_filename"]), icon("pdf"))]
    if p.get("arxiv_id"):
        acts.append('<a href="https://arxiv.org/abs/%s" rel="noopener">%sarXiv</a>'
                    % (e(p["arxiv_id"]), icon("out")))
    if p.get("doi") and not p["doi"].startswith("10.48550"):
        acts.append('<a href="https://doi.org/%s" rel="noopener">%sDOI</a>'
                    % (e(p["doi"]), icon("link")))
    if p.get("anthology_url") and not p.get("doi", "").startswith("10.48550"):
        acts.append('<a href="%s" rel="noopener">%sPublisher page</a>'
                    % (e(p["anthology_url"]), icon("book")))
    if p.get("code_url"):
        acts.append('<a href="%s" rel="noopener">%sCode</a>'
                    % (e(p["code_url"]), icon("code")))
    for d in p.get("data_urls") or ([{"label": "Data", "url": p["data_url"]}]
                                    if p.get("data_url") else []):
        acts.append('<a href="%s" rel="noopener">%s%s</a>'
                    % (e(d["url"]), icon("data"), e(d["label"])))
    acts.append('<a href="#cite">%sBibTeX</a>' % icon("quote"))
    parts.append('<p class="actions">%s</p>\n' % "\n".join(acts))
    parts.append('<p class="tiny note">%s</p>\n' % e(artifact_note(p)))

    parts.append('<div class="tldr"><span class="lab">In one sentence</span>'
                 '<p>%s</p></div>\n' % nums(c["tldr"]))
    if c.get("contribution"):
        parts.append('<p class="contribution"><span class="lab">Research contribution</span>'
                     '%s</p>\n' % e(c["contribution"]))

    parts.append(h2("Abstract", "doc") + '<p class="abs">%s</p>\n' % e(c["abstract"]))

    parts.append(h2("Why it matters", "why") + "<p>%s</p>\n" % nums(c["why_it_matters"]))

    if c.get("key_results"):
        parts.append(h2("Key results", "chart") + '<ul class="kr">\n')
        for r in c["key_results"]:
            if r.get("is_negative_or_null"):
                parts.append('<li class="neg">'
                             '<span class="qual">Null or negative</span>%s</li>\n'
                             % nums(r["text"]))
            else:
                parts.append("<li>%s</li>\n" % nums(r["text"]))
        parts.append("</ul>\n")
        parts.append('<p class="tiny note">Every number above appears in the paper. '
                     'Results that were null or went the wrong way are included and '
                     'marked.</p>\n')

    parts.append("""<figure>
<picture>
<source srcset="/assets/img/figs/{img}.webp" type="image/webp">
<img src="/assets/img/figs/{img}.jpg" width="{w}" height="{h}"
 loading="lazy" decoding="async" alt="{alt}">
</picture>
<figcaption>{cap} Taken from the paper.</figcaption>
</figure>
""".format(img=e(p["img"]), w=fw, h=fh, alt=e(c["figure_alt"]),
           cap=e(c["figure_caption"])))

    parts.append(h2("Topics", "tag") + '<p class="topics">%s</p>\n' % e(c["topics_sentence"]))

    if c.get("honesty_note"):
        parts.append('<section class="candid">'
                     + h2("What this paper does not show", "candid")
                     + "<p>%s</p></section>\n" % nums(c["honesty_note"]))

    parts.append(h2("How to cite", "quote", ' id="cite"') + '<p>%s</p>\n'
                 % plain_citation(p))
    parts.append("<pre><code>%s</code></pre>\n" % e(bibtex_for(p, c)))

    rel = [BY_SLUG[s] for s in p.get("related", []) if s in BY_SLUG and s in CONTENT]
    if rel:
        parts.append(h2("Related work of mine", "link") + '<ul class="tl">\n')
        for r in rel:
            parts.append('<li><a href="/papers/%s/">%s</a>'
                         '<span class="v">%s</span></li>\n'
                         % (e(r["slug"]), e(r["title"]), e(r["venue_short"])))
        parts.append("</ul>\n")

    note = []
    if p.get("pdf_note"):
        note.append(e(p["pdf_note"]))
    if note:
        parts.append('<p class="tiny note">%s</p>\n' % " ".join(note))

    parts.append('</article>\n<p class="back"><a href="/publications/">'
                 '&larr; All publications</a></p>\n')
    parts.append(site_footer())
    return "".join(parts)


# ---------------------------------------------------------------- index pages

def delta(h):
    """How far the metric moved, and the string to print for it.

    Computed here and never typed into headline.json, so it cannot disagree with the
    two numbers it sits between.

    The sign is the metric's own, not the paper's: on the one row where lower is
    better the number printed is negative, because toxicity really did go down. The
    alternative, flipping the sign so that every row shows a plus, would mean printing
    "+0.74" beside a toxicity score that fell, which is the kind of small dishonesty
    nobody would ever catch. "lower is better" is stated on the line underneath.
    """
    b, o = float(h["base"]["value"]), float(h["ours"]["value"])
    d = o - b
    # Two decimals, then drop a trailing zero, so a 3.50 point gain prints as +3.5
    # and a 0.74 one keeps both digits. Rounded through the string so that
    # 88.88 - 85.38 cannot print as +3.5000000000000284.
    s = "%+.2f" % d
    return d, s[:-1] if s.endswith("0") else s


def result_panel(p):
    """The headline result for one paper, as a small chart in the column where a
    cropped figure used to be.

    A crop of a paper's own system diagram is recognisable but not self-explanatory:
    it shows some boxes and arrows from a figure drawn for someone who has already
    read the paper. This panel answers the question a reader of a publication list is
    actually asking, which is what was measured, against what, and by how much.

    It is markup and CSS rather than a generated image on purpose. The numbers stay
    selectable and searchable as text, they scale with the reader's font size, a
    translator can reach the labels, and there is no second copy of a number that can
    fall out of step with content.json.

    The bars are value/scale against the metric's real ceiling and are never
    normalised to the pair, so a 3.50 point gain looks like a 3.50 point gain. The
    numerals beside them carry the precision the bars cannot.
    """
    h = HEAD.get(p["slug"])
    if not h:
        return ""
    d, dtxt = delta(h)
    unit = (" " + h["delta_unit"]) if h.get("delta_unit") else ""
    sc = float(h["scale"])
    rows = []
    for key, cls in (("base", ""), ("ours", " us")):
        v = h[key]
        pct = max(1.5, min(100.0, float(v["value"]) / sc * 100.0))
        rows.append(
            '<div class="r%s"><span class="n">%s</span>'
            '<span class="t"><i style="width:%.1f%%"></i></span>'
            '<span class="l">%s</span></div>'
            % (cls, e(v["value"]), pct, e(v["label"])))
    return """<div class="res">
<p class="hd"><span class="bm">{bench}</span><span class="dl">{dtxt}{unit}</span></p>
<p class="mt">{metric}</p>
<div class="bars">{rows}</div>{note}
</div>
""".format(bench=e(h["bench"]), metric=e(h["metric"]), dtxt=e(dtxt), unit=e(unit),
           rows="\n".join(rows),
           note=('\n<p class="fn">%s</p>' % e(h["note"])) if h.get("note") else "")


def pub_card(p, c, featured=False):
    """One row of the publication list: thumbnail, topic tag, metadata, title,
    authors, and the measured claim.

    The right column is a result panel, not a picture. It was a picture through two
    designs: first the whole figure letterboxed into 4:3, which at 176px was mostly
    white space, then a crop of the one legible sub-region, re-cut from a 600 DPI
    render of the PDF page so that nothing was upscaled. The second version was
    legible and still failed, because a fragment of a system diagram drawn for
    someone who has read the paper does not tell a stranger what the paper did.
    result_panel() answers that instead. The paper's own figure is still on the
    paper's own page, full width, with a real description.
    """
    where = e(p["venue_short"])
    if p.get("pages"):
        where += ", pages " + p["pages"].replace("-", "&ndash;")
    if pub_status(p) == "preprint":
        where += ' <span class="flag">Preprint</span>'
    contribution = ""
    if c.get("contribution"):
        contribution = ('<p class="contribution"><span class="lab">Research contribution'
                        '</span>%s</p>' % e(c["contribution"]))

    visual = result_panel(p)
    impact = ""
    card_class = "pub"
    if featured:
        card_class += " featured"
        thumb_name = c.get("featured_thumbnail")
        thumb_src = ("/assets/img/featured/%s.jpg" % e(thumb_name)
                     if thumb_name else
                     "/assets/img/papers/%s-600x450.jpg" % e(p["img"]))
        thumb_alt = c.get("featured_thumbnail_alt") or c["figure_alt"]
        visual = """<a class="paperthumb" href="/papers/{slug}/" aria-label="Read {title}">
<picture>
<img src="{src}" width="600" height="450"
 loading="lazy" decoding="async" alt="{alt}">
</picture>
</a>""".format(slug=e(p["slug"]), title=e(p["title"]), src=thumb_src,
              alt=e(thumb_alt))
        h = HEAD.get(p["slug"])
        if h:
            d, dtxt = delta(h)
            unit = (" " + h["delta_unit"]) if h.get("delta_unit") else ""
            impact = '<span class="impact">%s%s on %s</span>' % (
                e(dtxt), e(unit), e(h["bench"]))

    return """<div class="{card_class}">
{thumb}<div class="body">
<p class="meta">{tag}<span>{where}</span>{impact}</p>
<h3><a href="/papers/{slug}/">{title}</a></h3>
<p class="who">{who}</p>
<p class="sum">{tldr}</p>
{contribution}
</div>
</div>
""".format(slug=e(p["slug"]), title=e(p["title"]), thumb=visual,
           tag=tag_pill(p["slug"]), who=author_line_html(p), where=where,
           impact=impact, tldr=nums(c["tldr"]),
           contribution=contribution, card_class=card_class)


HUBS = {
    "agent-memory": {
        "title": "Agent memory: changing facts and reusable procedures",
        "description": ("A guide to two complementary agent-memory designs: temporal "
                        "event memory and procedural experience replay."),
        "intro": ("An agent may need to resolve what is true now, or reuse how it "
                  "solved a task before. These are related but distinct memory problems."),
        "papers": [
            ("apex-mem-agentic-semi-structured-memory",
             "For changing conversational facts",
             "An append-only property graph represents dated, entity-centric events and a multi-tool retrieval agent resolves conflicting or evolving information at query time.",
             "Reported results include 88.88% on LOCOMO and 86.2% on LongMemEval."),
            ("apex-em-procedural-episodic-experience-replay",
             "For repeated procedures",
             "A typed Procedural Knowledge Graph stores complete successful and failed traces, retrieved through semantic search, structural signatures, and graph traversal—without changing model weights during deployment.",
             "On a blind KGQAGen-10k test split with frozen memory, the paper reports 73.7% versus 42.0% without memory."),
        ],
        "caveat": ("These papers address complementary settings, not a universal memory "
                   "solution. Their evaluation settings and model backbones differ."),
    },
    "agent-delegation": {
        "title": "Adaptive handoffs for multi-agent systems",
        "description": ("A practical reading guide to choosing a typed dependency graph "
                        "or natural-language handoff for each agent task."),
        "intro": ("A delegation need not always be prose or always be structured. "
                  "Routed Graph Handoff selects a typed dependency graph or natural language "
                  "for each task, then relies on an executor that understands the chosen form."),
        "papers": [
            ("routed-graph-handoff",
             "Route the handoff format, not just the task",
             "The system routes between a typed DAG and prose fallback. The contribution is adaptive selection; graph-only handoff is not presented as universally better.",
             "The paper reports a 12.7-point gain on τ-bench retail and an 8.7-point gain on BrowseComp against named prose baselines."),
        ],
        "caveat": ("The paper reports parity rather than universal wins on some benchmarks, "
                   "and graph-only handoff regresses on AppWorld. Preserve a natural-language "
                   "fallback for tasks that need adaptive reasoning."),
    },
    "web-qa": {
        "title": "Web QA: retrieve evidence, rank answers, extend to more languages",
        "description": ("A research lineage from web-scale training data to context-aware "
                        "answer ranking and low-resource multilingual supervision."),
        "intro": ("This is a reading map rather than one end-to-end system: WDRASS supplies "
                  "data and evaluation, Question–Context Alignment improves candidate ranking, "
                  "and Cross-Lingual Knowledge Distillation extends answer selection to lower-resource languages."),
        "papers": [
            ("wdrass-web-scale-document-retrieval-answer-sentence-selection",
             "Train and evaluate at web scale",
             "WDRASS connects document retrieval, passage reranking, and answer sentence selection with roughly 64,000 questions and more than 800,000 labeled passages and sentences drawn from 30 million documents.",
             "In its Open retrieval setting, the paper reports H@50 of 0.903 for WDRASS-trained DPR versus 0.777 for the NQ-trained comparison."),
            ("question-context-alignment-answer-sentence-selection",
             "Use question–context dependencies when ranking answers",
             "The method aligns question and surrounding-context words with optimal transport, represents dependencies as a sentence graph, and derives candidate representations with a graph convolutional network.",
             "On non-fine-tuned WikiQA, the paper reports P@1 of 74.16 versus 68.09 for the comparison."),
            ("cross-lingual-knowledge-distillation-answer-sentence-selection",
             "Transfer answer selection across languages",
             "A strong English teacher supplies soft scores so target-language models can be trained without target-language labels.",
             "On Xtr-WikiQA Arabic in the named configuration, the paper reports P@1 of 76.3 versus 64.2."),
        ],
        "caveat": ("The multilingual results are configuration- and language-dependent. "
                   "The paper reports weaker results than supervised training in some settings."),
    },
}


def hub_paper_card(slug, lens, mechanism, evidence):
    p, c = BY_SLUG[slug], CONTENT[slug]
    fw, fh = FIGDIMS[p["img"]]
    actions = [
        '<a href="/papers/%s/">%sRead the paper page</a>' % (e(slug), icon("doc")),
        '<a href="/papers/%s/%s">%sPDF</a>' % (e(slug), e(p["pdf_filename"]), icon("pdf")),
        '<a href="/papers/%s/">%sCitation + BibTeX</a>' % (e(slug), icon("quote")),
    ]
    return """<section>
%s
<p class="lab">%s</p>
<h3 style="font-size:19px;letter-spacing:-.015em;text-transform:none;color:var(--ink);margin:0 0 .55em">%s</h3>
<p>%s</p>
<p class="calib">%s</p>
<figure>
<picture><source srcset="/assets/img/figs/%s.webp" type="image/webp">
<img src="/assets/img/figs/%s.jpg" width="%d" height="%d" loading="lazy" decoding="async" alt="%s"></picture>
<figcaption>%s Taken from the paper.</figcaption>
</figure>
<p class="actions">%s</p>
</section>
""" % (h2(lens, "why"), e(lens), e(p["title"]), e(mechanism), nums(evidence),
       e(p["img"]), e(p["img"]), fw, fh, e(c["figure_alt"]), e(c["figure_caption"]),
       "\n".join(actions))


def research_hub_page(key):
    hub = HUBS[key]
    out = [head(
        title=hub["title"] + " | " + SITE["name"],
        desc=hub["description"],
        canonical=url("/research/%s/" % key),
        og_type="article",
        og_image=url("/assets/img/cards/site-1200x630.jpg"),
        og_image_alt="Share card: Ankit Chadha research guide.",
    )]
    out.append(site_header("research"))
    out.append('<nav class="crumb" aria-label="Breadcrumb"><a href="/">Home</a> / '
               '<a href="/research/">Research</a> / %s</nav>\n' % e(hub["title"]))
    out.append("<article><h1>%s</h1><p class=\"bp\">%s</p>\n"
               % (e(hub["title"]), e(hub["intro"])))
    for card in hub["papers"]:
        out.append(hub_paper_card(*card))
    out.append('<section class="candid">' + h2("Scope and limits", "candid")
               + "<p>%s</p></section>\n" % e(hub["caveat"]))
    out.append("</article>")
    out.append(site_footer())
    return "".join(out)


def research_index_page():
    out = [head(
        title="Research guides | " + SITE["name"],
        desc=("Research guides connecting Ankit Chadha's work on agent memory, "
              "multi-agent delegation, web-scale question answering, and multilingual NLP."),
        canonical=url("/research/"),
        og_type="website",
        og_image=url("/assets/img/cards/site-1200x630.jpg"),
        og_image_alt="Share card: Ankit Chadha research guides.",
    )]
    out.append(site_header("research"))
    out.append('<nav class="crumb" aria-label="Breadcrumb"><a href="/">Home</a> / Research</nav>\n')
    out.append("<h1>Research guides</h1><p class=\"bp\">These guides connect related "
               "papers around a practical question. They are not substitutes for the papers; "
               "each guide links to the primary paper, PDF, and citation.</p>\n")
    for key, hub in HUBS.items():
        out.append(h2(hub["title"], "grid"))
        out.append("<p>%s</p><p class=\"actions\"><a href=\"/research/%s/\">%sRead the guide</a></p>\n"
                   % (e(hub["description"]), e(key), icon("out")))
    out.append(site_footer())
    return "".join(out)


def publications_page():
    live = [p for p in PAPERS if p["slug"] in CONTENT]
    # Accepted-but-not-yet-in-proceedings papers have been through peer review,
    # so they belong in the reviewed group, not with the preprints.
    reviewed = [p for p in live if pub_status(p) != "preprint"]
    pre = [p for p in live if pub_status(p) == "preprint"]
    key = lambda p: (-p["year"], -p.get("scholar_citations", 0), p["title"])
    reviewed.sort(key=key)
    pre.sort(key=key)

    items = reviewed + pre
    coll = {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "@id": url("/publications/#collection"),
        "url": url("/publications/"),
        "name": "Publications - " + SITE["name"],
        # Falls back to the page's own meta description when there is no visible
        # intro paragraph, because structured data has to describe what a reader
        # actually sees and there is no longer an intro to quote.
        "description": (SITE["publications_intro"] or [
            "Peer-reviewed papers and preprints by Ankit Chadha on agent memory, "
            "retrieval-augmented generation, answer sentence selection and federated "
            "learning, each with a plain-language summary."])[0],
        "inLanguage": "en",
        "isPartOf": {"@id": url("#website")},
        "about": {"@id": url("#person")},
        "mainEntity": {
            "@type": "ItemList",
            "itemListOrder": "https://schema.org/ItemListOrderDescending",
            "numberOfItems": len(items),
            "itemListElement": [
                {"@type": "ListItem", "position": i + 1,
                 "url": url("/papers/%s/" % p["slug"]), "name": p["title"]}
                for i, p in enumerate(items)
            ],
        },
    }

    out = [head(
        title="Publications - " + SITE["name"],
        desc=("Peer-reviewed papers and preprints by Ankit Chadha on agent memory, "
              "retrieval-augmented generation, answer sentence selection and federated "
              "learning, each with a plain-language summary."),
        canonical=url("/publications/"),
        og_type="website",
        og_image=url("/assets/img/cards/publications-1200x630.jpg"),
        og_image_alt=("Share card: Ankit Chadha, Director of Applied Science at "
                      "Amazon, with the publication and patent counts."),
        jsonld=[coll],
    )]
    out.append(site_header("pubs"))
    out.append('<nav class="crumb" aria-label="Breadcrumb"><a href="/">Home</a> / '
               "Publications</nav>\n")
    out.append("<h1>Publications</h1>\n")
    out.append('<p class="actions"><a href="/publications.bib">%sDownload all BibTeX</a></p>\n'
               % icon("quote"))
    for para in SITE["publications_intro"]:
        out.append('<p class="bp">%s</p>\n' % e(para))

    # The tag legend. It is not a filter, because filtering needs JavaScript and
    # this site has none; it is a contents page. Counting the papers per topic is
    # the fastest way to see what the work actually is, and it makes the small
    # topics visible as small instead of hiding them among the large ones.
    if SITE.get("topic_tags"):
        out.append('<p class="legend"><span class="lg">%sTopics on this page</span>'
                   % icon("tag"))
        for t in SITE["topic_tags"]:
            live_n = len([x for x in t["papers"] if x in CONTENT])
            if live_n:
                out.append(tag_pill(t["tag"], live_n))
        out.append("</p>\n")

    out.append(h2("Peer reviewed", "check"))
    for p in reviewed:
        out.append(pub_card(p, CONTENT[p["slug"]]))
    out.append(h2("Preprints", "draft"))
    out.append('<p class="small mut">Not peer reviewed. Listed separately on purpose.</p>\n')
    for p in pre:
        out.append(pub_card(p, CONTENT[p["slug"]]))

    out.append(h2("Patents", "patent") + '<ul class="tl">\n')
    for pt in DATA["patents"]:
        out.append('<li><span class="t">%s</span><span class="v">%s. %s. '
                   "Assigned to %s.</span></li>\n"
                   % (e(pt["title"]), e(pt["number"]), e(pt["inventors"]),
                      e(pt["assignee"])))
    out.append("</ul>\n")

    out.append(h2("Earlier work, 2013 to 2015", "clock"))
    out.append("<p>%s</p>\n" % e(SITE["earlier_work_note"]))
    out.append('<table class="earlier">\n<thead><tr><th scope="col">Paper</th>'
               '<th scope="col" class="n">Year</th>'
               '<th scope="col" class="n">Citations</th></tr></thead>\n<tbody>\n')
    for w in DATA["earlier_work"]:
        link = ('<a href="https://arxiv.org/abs/%s" rel="noopener">%s</a>'
                % (e(w["arxiv_id"]), e(w["title"]))) if w.get("arxiv_id") else e(w["title"])
        out.append("<tr><td>%s<span class=\"tiny\">%s. %s.</span></td>"
                   "<td class=\"n\">%d</td><td class=\"n\">%d</td></tr>\n"
                   % (link, e(w["authors"]), e(w["venue"]), w["year"], w["citations"]))
    out.append("</tbody>\n</table>\n")
    out.append(site_footer())
    return "".join(out)


def contact_tabs():
    linkedin = next(l["url"] for l in SITE["links"] if l["label"] == "LinkedIn")
    return """
<div class="contact-tabs">
<input type="radio" name="contact-tab" id="contact-general" checked>
<input type="radio" name="contact-tab" id="contact-speaking">
<div class="contact-tab-list" role="tablist" aria-label="Contact options">
<label for="contact-general" role="tab">General</label>
<label for="contact-speaking" role="tab">Speaking engagements</label>
</div>
<div class="contact-panels">
<div class="contact-panel contact-general">
<p class="contact-lead">%s.</p>
</div>
<div class="contact-panel contact-speaking">
<p class="contact-lead">Speaking engagements</p>
<p>Open to talks at conferences, workshops, podcasts, and university lectures on multimodal LLMs, post-training and alignment, agentic architectures, grounded RAG, and scaling applied research organizations.</p>
<p>To invite me to a talk, panel, or guest lecture, reach out at %s or via <a href="%s" rel="me noopener">LinkedIn</a>.</p>
</div>
</div>
</div>
""" % (e(SITE["email_display"]), e(SITE["email_display"]), e(linkedin))


def contact_page():
    out = [head(
        title="Contact Ankit Chadha",
        desc=("Contact Ankit Chadha for research conversations, conference talks, "
              "workshops, podcasts, panels, and university lectures."),
        canonical=url("/contact/"),
        og_type="website",
        og_image=url("/assets/img/cards/site-1200x630.jpg"),
        og_image_alt=("Share card: Ankit Chadha, Director of Applied Science at "
                      "Amazon, with the publication and patent counts."),
    )]
    out.append(site_header("contact"))
    out.append("<h1>Contact me</h1>\n")
    out.append(contact_tabs())
    out.append(site_footer())
    return "".join(out)


def home_page():
    live = [p for p in PAPERS if p["slug"] in CONTENT]
    featured = [BY_SLUG[s] for s in DATA["featured"] if s in CONTENT]

    out = [head(
        title="Ankit Chadha - Applied Science, Agent Memory and Retrieval",
        desc=SITE["meta_description"][:300],
        canonical=url("/"),
        # og:type=profile is the type Open Graph defines for a page about one
        # person, and it is what lets the profile:* properties below mean anything.
        og_type="profile",
        # A real 1200x630 card, not the square headshot. twitter:card is
        # summary_large_image, so a square image gets centre-cropped to a band
        # across the face by every scraper that honours the declared size.
        og_image=url("/assets/img/cards/site-1200x630.jpg"),
        og_image_alt=("Share card: Ankit Chadha, Director of Applied Science at "
                      "Amazon, with the publication and patent counts."),
        extra_meta=(
            '<meta property="profile:first_name" content="%s">\n'
            '<meta property="profile:last_name" content="%s">\n'
            '<meta property="profile:username" content="ankit-ai">\n'
            % (e(SITE["given_name"]), e(SITE["family_name"]))),
        jsonld=[profilepage_node(), person_node(), website_node()],
    )]
    out.append(site_header("home"))
    role, rest = split_lead(SITE["tagline"])
    out.append("""<div class="hero">
<picture>
<source srcset="/assets/img/headshot-400.webp" type="image/webp">
<img src="/assets/img/headshot-400.jpg" width="116" height="116"
 alt="" fetchpriority="high">
</picture>
<div class="lead">
<p class="eyebrow">Applied science leadership &middot; Amazon AGI</p>
<h1>Ankit Chadha</h1>
<p class="tag"><span class="role">%s</span><br>%s</p>
</div></div>
""" % (e(role), e(rest)))

    out.append('<ul class="chips">\n')
    for l in SITE["links"]:
        out.append('<li><a href="%s" rel="me noopener">%s%s</a></li>\n'
                   % (e(l["url"]), brand(l["label"]), e(l["label"])))
    out.append("</ul>\n")

    # class="bp" marks running prose, which is the only thing capped at a 68
    # character measure. Everything else on the page is a row, a panel or a
    # metadata line, and those want the full 740px column.
    for para in SITE["bio"]:
        out.append('<p class="bp">%s</p>\n' % e(para))

    out.append("""<div class="signal-grid" aria-label="Leadership and research focus">
<div class="signal"><div class="signal-head"><span class="lab">Frontier systems</span><span class="signal-mark">%s</span></div><p><strong>Agents that reason from evidence.</strong>Grounded reasoning across text, images, and structured data, supported by memory, web-scale retrieval, and long-horizon planning.</p></div>
<div class="signal"><div class="signal-head"><span class="lab">Research to production</span><span class="signal-mark">%s</span></div><p><strong>Research that reaches real systems.</strong>Turning advances in post-training, alignment, and evaluation into reliable AI systems that operate at web scale.</p></div>
<div class="signal"><div class="signal-head"><span class="lab">Research record</span><span class="signal-mark">%s</span></div><p><strong>A sustained publication record.</strong>Peer-reviewed work across ACL, NAACL, CIKM, INTERSPEECH, and ECML PKDD, with additional work at NeurIPS workshops.</p></div>
</div>
""" % (icon("agents"), icon("pipeline"), icon("book")))

    out.append(h2("Selected research contributions", "chart"))
    out.append('<p class="small mut">For the live publication and citation record, '
               'see <a href="%s">my Google Scholar profile</a>.</p>\n'
               % e(SITE["links"][0]["url"]))
    for p in featured:
        out.append(pub_card(p, CONTENT[p["slug"]], featured=True))

    out.append('<p class="back"><a href="/publications/">All %d papers, with abstracts '
               "and numbers &rarr;</a></p>\n" % len(live))

    out.append(h2("Research guides", "grid"))
    out.append('<p class="small mut">Practical reading guides that connect related papers '
               'without replacing their primary evidence.</p><ul class="tl">\n')
    for key, hub in HUBS.items():
        out.append('<li><a href="/research/%s/">%s</a>'
                   '<span class="v">%s</span></li>\n'
                   % (e(key), e(hub["title"]), e(hub["description"])))
    out.append("</ul>\n")

    out.append(h2("Research and systems", "grid"))
    # The year span, the paper count, and which theme is current are all computed from
    # papers.json. "Current" is simply the theme holding the newest paper, so it moves
    # by itself when a new paper lands and can never be left pointing at old work.
    spans = {}
    for t in SITE["themes"]:
        ys = [BY_SLUG[s]["year"] for s in t["papers"] if s in CONTENT]
        spans[t["heading"]] = (min(ys), max(ys), len(ys)) if ys else (0, 0, 0)
    # Ties on the newest year are broken by paper count, not alphabetically, because
    # two themes now share 2026 and an alphabetical tiebreak would hand "Current" to
    # whichever heading happened to sort last.
    newest = max((v[1], v[2], k) for k, v in spans.items())[2] if spans else None

    out.append('<dl class="work">\n')
    for t in SITE["themes"]:
        lo, hi, n = spans[t["heading"]]
        when = str(lo) if lo == hi else "%d&ndash;%d" % (lo, hi)
        out.append('<div class="row">\n<dt>%s<span class="when">%s<br>'
                   "%d paper%s</span>%s</dt>\n"
                   % (e(t["heading"]), when, n, "" if n == 1 else "s",
                      '<span class="pill">Current</span>'
                      if t["heading"] == newest else ""))
        out.append('<dd>\n<p class="g">%s</p>\n<ul class="tl">\n' % e(t["body"]))
        for s in t["papers"]:
            if s not in CONTENT:
                continue
            p = BY_SLUG[s]
            # The rail is an index, so it gets the one-line form of the result panel
            # rather than the panel: benchmark and gap, no bars. Same numbers, same
            # source, a tenth of the space.
            h = HEAD.get(s)
            chip = ""
            if h:
                d, dtxt = delta(h)
                chip = ('<span class="d">%s%s <span class="on">on %s</span></span>'
                        % (e(dtxt), e((" " + h["delta_unit"])
                                      if h.get("delta_unit") else ""),
                           e(h["bench"])))
            out.append('<li><a href="/papers/%s/">%s</a>'
                       '<span class="v">%s</span>%s</li>\n'
                       % (e(p["slug"]), e(p["title"]),
                          e(p["venue_short"]), chip))
        out.append("</ul>\n</dd>\n</div>\n")
    out.append("</dl>\n")

    # Experience before education, because the work is the evidence and the degree is
    # context.
    #
    # The last row is two jobs on one line, Samsung 2018-2019 and Apple 2016-2018, under
    # a single 2016-2019 span. They were collapsed on purpose: both were the same role,
    # neither carries a description because the profile they came from gives none, and
    # inventing one would be the only dishonest line on the page. Two dateless rows in a
    # column of described ones read as gaps in the record rather than as jobs, so the
    # merged row says less and implies less. The individual dates are still on LinkedIn.
    out.append(h2("Experience", "badge") + '<ol class="cv">\n')
    for x in SITE["experience"]:
        span = "%d &ndash; %s" % (x["from"], x["to"] or "now")
        org = x["org"] + (", " + x["team"] if x.get("team") else "")
        out.append('<li><div class="yr">%s</div><div>\n'
                   '<p class="role">%s<span class="org">%s</span></p>\n'
                   % (span, e(x["role"]), e(org)))
        if x.get("what"):
            out.append('<p class="g">%s</p>\n' % e(x["what"]))
        out.append("</div></li>\n")
    out.append("</ol>\n")

    out.append(h2("Education", "cap") + '<ul class="tl">\n')
    for ed in SITE["education"]:
        out.append('<li><span class="t">%s</span>'
                   '<span class="v"><a href="%s" rel="noopener">%s</a></span></li>\n'
                   % (e(ed["degree"]), e(ed["url"]), e(ed["school"])))
    out.append("</ul>\n")

    out.append(site_footer())
    return "".join(out)


def error_page():
    live = [p for p in PAPERS if p["slug"] in CONTENT][:5]
    out = [head(
        title="Page not found - " + SITE["name"],
        desc="That page does not exist. Links to the homepage and the publication list.",
        canonical=url("/404.html"),
        og_type="website",
        og_image=url("/assets/img/cards/site-1200x630.jpg"),
        og_image_alt=("Share card: Ankit Chadha, Director of Applied Science at "
                      "Amazon, with the publication and patent counts."),
    )]
    out.append(site_header())
    out.append("<h1>Page not found</h1>\n<p>That URL does not exist on this site. "
               "Try one of these.</p>\n<ul>\n")
    out.append('<li><a href="/">About Ankit Chadha</a></li>\n')
    out.append('<li><a href="/publications/">All publications</a></li>\n')
    for p in live:
        out.append('<li><a href="/papers/%s/">%s</a></li>\n'
                   % (e(p["slug"]), e(p["title"])))
    out.append("</ul>\n")
    out.append(site_footer())
    return "".join(out)


def sitemap():
    rows = [(url("/"), SITE["build_date"]),
            (url("/research/"), SITE["build_date"]),
            (url("/publications/"), SITE["build_date"]),
            (url("/contact/"), SITE["build_date"])]
    for key in HUBS:
        rows.append((url("/research/%s/" % key), SITE["build_date"]))
    for p in PAPERS:
        if p["slug"] not in CONTENT:
            continue
        lm = p.get("arxiv_date") or iso(p["citation_publication_date"])
        lm = lm if len(lm) == 10 else SITE["build_date"]
        rows.append((url("/papers/%s/" % p["slug"]), SITE["build_date"]))
        rows.append((url("/papers/%s/%s" % (p["slug"], p["pdf_filename"])), lm))
    body = "\n".join(
        "  <url>\n    <loc>%s</loc>\n    <lastmod>%s</lastmod>\n  </url>"
        % (e(loc), lm) for loc, lm in rows)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            + body + "\n</urlset>\n")


def robots():
    """robots.txt.

    A crawler obeys only the single most specific user-agent group that matches
    it, not the union of all matching groups. So a bare "User-agent: Googlebot /
    Allow: /" block would make Googlebot ignore every rule in the "*" group,
    including the Disallow below. Every rule is therefore emitted into every
    group, from one list, so that trap cannot come back.

    /_build/ is disallowed because .nojekyll makes GitHub Pages serve
    underscore-prefixed directories, and _build/content.json holds the same
    abstracts as the paper pages. Indexed, it would be duplicate content
    competing with the pages that carry the Scholar metadata.
    """
    agents = ["*"]
    # /assets/pdf/ holds the master copies. Every one is byte-identical to the
    # sibling next to its paper page, and only the sibling may be crawled,
    # because that is the path citation_pdf_url points at and Scholar checks
    # that the PDF sits in the same directory as the abstract page.
    disallow = ["/_build/", "/_work/", "/assets/pdf/"]
    out = ["# %s" % url("/robots.txt")]
    for a in agents:
        out.append("User-agent: %s" % a)
        out.append("Allow: /")
        out += ["Disallow: %s" % d for d in disallow]
        out.append("")
    out.append("Sitemap: %s" % url("/sitemap.xml"))
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- write

def write(rel, text):
    path = os.path.join(ROOT, rel)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


def main():
    if not CONTENT:
        sys.exit("_build/content.json is missing. Nothing to build.")

    made, skipped = [], []
    for p in PAPERS:
        page = paper_page(p)
        if page is None:
            skipped.append(p["slug"])
            continue
        d = "papers/%s" % p["slug"]
        made.append(write("%s/index.html" % d, page))
        src = os.path.join(ROOT, "assets", "pdf", p["pdf_local"])
        dst = os.path.join(ROOT, d, p["pdf_filename"])
        size = os.path.getsize(src)
        if size > 5 * 1024 * 1024:
            sys.exit("%s is %.1f MB, over the Google Scholar 5 MB cap."
                     % (p["pdf_local"], size / 1048576.0))
        shutil.copyfile(src, dst)

    made.append(write("research/index.html", research_index_page()))
    for key in HUBS:
        made.append(write("research/%s/index.html" % key, research_hub_page(key)))
    made.append(write("publications/index.html", publications_page()))
    made.append(write("contact/index.html", contact_page()))
    made.append(write("index.html", home_page()))
    made.append(write("404.html", error_page()))
    made.append(write("sitemap.xml", sitemap()))
    made.append(write("robots.txt", robots()))
    made.append(write("publications.bib", "\n\n".join(
        bibtex_for(p, CONTENT[p["slug"]]) for p in PAPERS if p["slug"] in CONTENT
    ) + "\n"))
    write(".nojekyll", "")
    key = SITE.get("indexnow_key")
    if key:
        write("%s.txt" % key, key + "\n")

    print("built %d files" % (len(made) + 1))
    for m in made:
        print("  " + os.path.relpath(m, ROOT))
    if skipped:
        print("SKIPPED (no content.json entry): " + ", ".join(skipped))


if __name__ == "__main__":
    main()
