#!/usr/bin/env python3
"""
Pre-publish checker. Run after every build.

This exists because the two things that silently break an academic site are both
invisible in a browser: a malformed Google Scholar meta block (Scholar then treats
the page as having no metadata at all) and a broken internal reference (a 404 that
only a crawler ever hits). Everything here is a rule from Scholar's own inclusion
guidelines, Google's structured-data rules, or plain link hygiene.

Exit code is nonzero if any FAIL is printed.
"""

import glob
import html
import json
import os
import re
import sys
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = json.load(open(os.path.join(ROOT, "_build", "site.json")))
PAPERS = json.load(open(os.path.join(ROOT, "_build", "papers.json")))["papers"]
CONTENT = json.load(open(os.path.join(ROOT, "_build", "content.json")))
BASE = SITE["base_url"].rstrip("/")

fails, warns = [], []

# BibTeX citation key -> the page that emitted it. Two papers sharing a key means
# a reader who cites both gets a LaTeX duplicate-entry error or, worse, a silently
# dropped reference. That is a functional defect in the one thing this site is for,
# so it is a hard failure and not a style warning. Keys must also never change
# after publishing, because someone may already have cited the old one.
bibtex_keys = {}


def fail(m):
    fails.append(m)


def warn(m):
    warns.append(m)


class Text(HTMLParser):
    """Visible text only. Anything inside script/style/head, or inside a details
    element, does not count as visible, which is exactly the distinction Scholar
    cares about for the abstract."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip = 0
        self.out = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "head", "details", "template"):
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style", "head", "details", "template") and self.skip:
            self.skip -= 1

    def handle_data(self, d):
        if not self.skip:
            self.out.append(d)

    def text(self):
        return re.sub(r"\s+", " ", "".join(self.out))


def pixel_size(path):
    """(width, height) of a JPEG or PNG, read from the file header.

    Done by hand rather than with Pillow so the pre-publish check has no
    third-party dependency: it has to be runnable on any machine that is about to
    push, including one where the image toolchain is not installed.
    """
    with open(path, "rb") as fh:
        d = fh.read(32)
        if d[:8] == b"\x89PNG\r\n\x1a\n":
            return (int.from_bytes(d[16:20], "big"),
                    int.from_bytes(d[20:24], "big"))
        if d[:2] != b"\xff\xd8":
            return None
        fh.seek(2)
        while True:
            b = fh.read(1)
            if not b:
                return None
            if b != b"\xff":
                continue
            marker = fh.read(1)
            while marker == b"\xff":
                marker = fh.read(1)
            if not marker:
                return None
            m = marker[0]
            # Start-of-frame markers carry the dimensions. C4, C8 and CC are
            # tables, not frames, and standalone markers have no length field.
            if m in (0xD8, 0xD9) or 0xD0 <= m <= 0xD7:
                continue
            ln = int.from_bytes(fh.read(2), "big")
            if 0xC0 <= m <= 0xCF and m not in (0xC4, 0xC8, 0xCC):
                seg = fh.read(ln - 2)
                return (int.from_bytes(seg[3:5], "big"),
                        int.from_bytes(seg[1:3], "big"))
            fh.seek(ln - 2, 1)


def check_og_image(name, md):
    """og:image must exist, and the declared size must be the real size.

    A wrong declaration is worse than no declaration: twitter:card is
    summary_large_image, so a scraper that trusts the numbers crops the file to
    the aspect ratio it was told about and the result is a band across the middle
    of whatever the picture actually is.
    """
    if len(md.get("og:image", [])) != 1:
        fail("%s: expected exactly one og:image" % name)
        return
    ogi = md["og:image"][0]
    if not ogi.startswith(BASE):
        return
    f = os.path.join(ROOT, ogi[len(BASE) + 1:])
    if not os.path.exists(f):
        fail("%s: og:image file missing: %s" % (name, os.path.relpath(f, ROOT)))
        return
    real = pixel_size(f)
    if not real:
        warn("%s: could not read the size of %s" % (name, os.path.basename(f)))
        return
    try:
        dec = (int(md.get("og:image:width", ["0"])[0]),
               int(md.get("og:image:height", ["0"])[0]))
    except ValueError:
        fail("%s: og:image:width or og:image:height is not a number" % name)
        return
    if dec != real:
        fail("%s: og:image declares %dx%d but %s is %dx%d"
             % (name, dec[0], dec[1], os.path.basename(f), real[0], real[1]))


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


def metas(h):
    """[(name_or_property, content)] for every meta tag."""
    out = []
    for tag in re.findall(r"<meta\b[^>]*>", h, re.I):
        n = re.search(r'(?:name|property)\s*=\s*"([^"]+)"', tag, re.I)
        c = re.search(r'content\s*=\s*"([^"]*)"', tag, re.I)
        if n:
            out.append((n.group(1), c.group(1) if c else ""))
    return out


def jsonlds(h):
    out = []
    for m in re.finditer(
            r'<script type="application/ld\+json">(.*?)</script>', h, re.S):
        try:
            out.append(json.loads(m.group(1)))
        except Exception as ex:
            fail("JSON-LD does not parse: %s" % ex)
    return out


# ---------------------------------------------------------------- paper pages

print("== paper pages ==")
for p in PAPERS:
    slug = p["slug"]
    rel = "papers/%s/index.html" % slug
    path = os.path.join(ROOT, rel)
    if not os.path.exists(path):
        if slug in CONTENT:
            fail("%s: page missing" % slug)
        continue
    h = read(rel)
    m = metas(h)
    md = {}
    for k, v in m:
        md.setdefault(k, []).append(v)
    c = CONTENT[slug]

    # The three tags Scholar requires. Missing any one voids the whole block.
    for req in ("citation_title", "citation_author", "citation_publication_date"):
        if req not in md:
            fail("%s: missing %s" % (slug, req))
    if md.get("citation_title", [""])[0] != p["title"]:
        fail("%s: citation_title does not match the title in papers.json" % slug)
    if len(md.get("citation_author", [])) != len(p["authors"]):
        fail("%s: %d citation_author tags for %d authors"
             % (slug, len(md.get("citation_author", [])), len(p["authors"])))
    for a in md.get("citation_author", []):
        if any(w in a.lower() for w in ("university", "amazon", "phd", "dr.", "prof")):
            fail("%s: citation_author carries an affiliation or title: %r" % (slug, a))
    d = md.get("citation_publication_date", [""])[0]
    if not re.match(r"^\d{4}(/\d{1,2}/\d{1,2})?$", d):
        fail("%s: citation_publication_date %r is not YYYY or YYYY/M/D" % (slug, d))

    # Venue tags, gated on status: published, accepted, or preprint.
    if "citation_conference_title" in md and "citation_journal_title" in md:
        fail("%s: has both citation_conference_title and citation_journal_title" % slug)
    status = p.get("status", "preprint" if p.get("is_preprint") else "published")
    has_venue = "citation_conference_title" in md or "citation_journal_title" in md
    if status == "preprint" and has_venue:
        fail("%s: preprint asserts a venue tag" % slug)
    if status == "accepted":
        # Accepted is not published. The proceedings have no page range and no
        # venue DOI yet, so a venue tag here would put an uncheckable citation
        # into other people's reference lists, and Scholar takes 6 to 9 months
        # to correct a bad record. The acceptance is stated in visible text.
        if has_venue:
            fail("%s: accepted-not-yet-published paper asserts a venue tag" % slug)
        for k in ("citation_firstpage", "citation_lastpage"):
            if k in md:
                fail("%s: accepted paper claims %s, but the proceedings do not exist"
                     % (slug, k))
        if not p.get("accepted_note"):
            fail("%s: status is accepted but papers.json has no accepted_note" % slug)
    if status == "published" and "citation_conference_title" not in md:
        warn("%s: published paper has no citation_conference_title" % slug)

    # citation_pdf_url must be a sibling file in this same directory.
    pdf = md.get("citation_pdf_url", [""])[0]
    want = "%s/papers/%s/%s" % (BASE, slug, p["pdf_filename"])
    if pdf != want:
        fail("%s: citation_pdf_url is %r, expected %r" % (slug, pdf, want))
    local = os.path.join(ROOT, "papers", slug, p["pdf_filename"])
    if not os.path.exists(local):
        fail("%s: sibling PDF %s missing" % (slug, p["pdf_filename"]))
    else:
        sz = os.path.getsize(local)
        if sz > 5 * 1024 * 1024:
            fail("%s: PDF is %.1f MB, over Scholar's 5 MB cap" % (slug, sz / 1048576.0))

    # Abstract must be complete, visible, ungated.
    vis = Text()
    vis.feed(h)
    vt = vis.text()
    ab = re.sub(r"\s+", " ", c["abstract"])
    if ab not in vt:
        fail("%s: the verbatim abstract is not in the visible text" % slug)
    if "<details" in h.lower():
        fail("%s: uses <details>, which can hide the abstract from Scholar" % slug)
    for r in c["key_results"]:
        if re.sub(r"\s+", " ", r["text"]) not in vt:
            fail("%s: a key result is not visible on the page" % slug)
    if re.sub(r"\s+", " ", c["honesty_note"]) not in vt:
        fail("%s: the honesty note is not visible on the page" % slug)
    if p.get("accepted_note") and \
            re.sub(r"\s+", " ", p["accepted_note"]) not in vt:
        fail("%s: the acceptance note is not visible on the page" % slug)
    for stale in ("This is a preprint", "is a preprint"):
        if status != "preprint" and stale in vt:
            fail("%s: status is %s but the page still calls it a preprint"
                 % (slug, status))
            break

    # BibTeX keys, unique across the whole site.
    found = re.findall(r"@[a-z]+\{([^,\s]+),", h)
    if not found:
        fail("%s: no BibTeX entry on the page" % slug)
    for k in found:
        if k in bibtex_keys and bibtex_keys[k] != slug:
            fail("%s: BibTeX key %r is also used by %s" % (slug, k, bibtex_keys[k]))
        bibtex_keys[k] = slug

    # Scholar's meta-tag-free fallback classes.
    if 'class="citation_title"' not in h:
        fail("%s: h1 lost class=citation_title" % slug)
    if "citation_author" not in re.sub(r"<meta[^>]*>", "", h):
        fail("%s: byline lost class=citation_author" % slug)

    # Unique visible body text, excluding the abstract, 300-900 words.
    body = vt.replace(ab, " ")
    wc = len(body.split())
    if wc < 300:
        warn("%s: only %d words of visible text outside the abstract" % (slug, wc))
    if wc > 1400:
        warn("%s: %d words outside the abstract, may be diluted" % (slug, wc))

    # Canonical, JSON-LD, no stray homepage tags.
    can = re.search(r'<link rel="canonical" href="([^"]+)"', h)
    if not can or can.group(1) != "%s/papers/%s/" % (BASE, slug):
        fail("%s: canonical wrong or missing" % slug)
    ld = jsonlds(h)
    types = [x.get("@type") for x in ld]
    if not any(t == ["ScholarlyArticle", "Article"] or t == "ScholarlyArticle"
               for t in types):
        fail("%s: no ScholarlyArticle JSON-LD" % slug)
    if not any(t == "BreadcrumbList" for t in types):
        warn("%s: no BreadcrumbList JSON-LD" % slug)
    for x in ld:
        s = json.dumps(x)
        for banned in ("interactionStatistic", "aggregateRating", "AggregateRating"):
            if banned in s:
                fail("%s: JSON-LD contains %s, a spam-policy violation"
                     % (slug, banned))
    check_og_image(slug, md)
    print("  ok  %-56s %5.1f KB  %4d words" % (slug, len(h) / 1024.0, wc))

# ---------------------------------------------------------------- index pages

print("== index pages ==")
for rel, name in (("index.html", "home"), ("publications/index.html", "publications"),
                  ("404.html", "404")):
    h = read(rel)
    m = metas(h)
    bad = [k for k, _ in m if k.startswith("citation_")]
    if bad:
        fail("%s: carries citation_* tags, which confuses Scholar: %s" % (name, bad))
    md = {}
    for k, v in m:
        md.setdefault(k, []).append(v)
    check_og_image(name, md)
    jsonlds(h)
    print("  ok  %-20s %5.1f KB" % (name, len(h) / 1024.0))

# Topic tags. Exactly one per paper: a paper with none is invisible to anyone
# skimming the list by topic, and a paper with two makes the tag column stop
# being scannable, which is the only reason the tags exist.
tagged = {}
for t in SITE.get("topic_tags", []):
    for s_ in t["papers"]:
        if s_ in tagged:
            fail("topic_tags: %s is tagged both %r and %r" % (s_, tagged[s_], t["tag"]))
        tagged[s_] = t["tag"]
    if not [x for x in t["papers"] if x in CONTENT]:
        warn("topic_tags: %r has no live papers and will not appear" % t["tag"])
for p in PAPERS:
    if p["slug"] in CONTENT and p["slug"] not in tagged:
        fail("topic_tags: %s has no topic tag" % p["slug"])
for s_ in tagged:
    if s_ not in {p["slug"] for p in PAPERS}:
        fail("topic_tags: %r is not a paper in papers.json" % s_)
pubs = read("publications/index.html")
for want in set(tagged.values()):
    # Compare against the escaped form, so a tag containing & or a quote still
    # matches the page instead of failing here for no reason.
    if html.escape(want, quote=True) not in pubs:
        fail("publications: topic tag %r never appears on the page" % want)
print("  %d papers, each with exactly one of %d topic tags"
      % (len(tagged), len(SITE.get("topic_tags", []))))

# Result panels. This is the check that matters most on this page, because the panel
# restates a number that also appears in prose two inches away and on the paper's own
# page: two copies of a number is exactly how a site ends up quoting a figure the
# paper does not contain. So every value in headline.json must appear verbatim in the
# key_results entry it names, and a value that is arithmetic on a stated figure rather
# than a stated figure itself is only allowed through if it says so in a derived note.
try:
    HEAD = json.load(open(os.path.join(ROOT, "_build", "headline.json")))
except FileNotFoundError:
    HEAD = {}
n_head = 0
for p in PAPERS:
    slug = p["slug"]
    if slug not in CONTENT:
        continue
    h = HEAD.get(slug)
    if not h:
        fail("headline.json: %s has no headline result, its row will have no panel"
             % slug)
        continue
    n_head += 1
    krs = CONTENT[slug]["key_results"]
    i = h.get("source_kr", 1) - 1
    if not 0 <= i < len(krs):
        fail("headline.json: %s names key result %d, which does not exist"
             % (slug, i + 1))
        continue
    src = krs[i]["text"]
    for side in ("base", "ours"):
        v = h[side]
        if v["value"] not in src:
            if v.get("derived"):
                warn("headline.json: %s %s value %s is not stated in key result %d, "
                     "allowed because it is derived: %s"
                     % (slug, side, v["value"], i + 1, v["derived"]))
            else:
                fail("headline.json: %s %s value %s does not appear in key result %d"
                     % (slug, side, v["value"], i + 1))
    try:
        b, o = float(h["base"]["value"]), float(h["ours"]["value"])
    except (KeyError, ValueError):
        fail("headline.json: %s has a value that is not a number" % slug)
        continue
    if h["scale"] <= 0:
        fail("headline.json: %s has a non-positive scale" % slug)
    for side, val in (("base", b), ("ours", o)):
        if val > h["scale"]:
            fail("headline.json: %s %s value %s is above its own scale of %s"
                 % (slug, side, val, h["scale"]))
    # A panel that shows the paper losing to its own baseline would be a real result,
    # but not a headline, and every one of these was chosen as the headline. If the
    # direction ever inverts it is a typo in lower_is_better, not a discovery.
    better = (b - o) if h.get("lower_is_better") else (o - b)
    if better <= 0:
        fail("headline.json: %s reads as no gain (%s vs %s); check lower_is_better"
             % (slug, h["base"]["value"], h["ours"]["value"]))
    # The panel's own text has to be on the page, or the panel silently vanished.
    for txt in (h["bench"], h["metric"], h["base"]["label"], h["ours"]["label"]):
        if html.escape(txt, quote=True) not in pubs:
            fail("publications: %s panel text %r is not on the page" % (slug, txt))
print("  %d result panels, every number traced back to a key result" % n_head)

home = read("index.html")
ld = jsonlds(home)
types = [x.get("@type") for x in ld]
for t in ("ProfilePage", "Person", "WebSite"):
    if t not in types:
        fail("home: missing %s JSON-LD" % t)
for x in ld:
    if x.get("@type") == "Person":
        for s in x.get("sameAs", []):
            if not s.startswith("http"):
                fail("home: sameAs entry is not a URL: %r" % s)

# ---------------------------------------------------------------- site-wide

print("== site wide ==")
sm = read("sitemap.xml")
locs = re.findall(r"<loc>([^<]+)</loc>", sm)
for loc in locs:
    if not loc.startswith(BASE):
        fail("sitemap: %s is not under %s" % (loc, BASE))
        continue
    p = loc[len(BASE) + 1:]
    f = os.path.join(ROOT, p if p else "index.html")
    if p.endswith("/"):
        f = os.path.join(ROOT, p, "index.html")
    if not os.path.exists(f):
        fail("sitemap: %s does not exist on disk" % loc)
for banned in ("<priority>", "<changefreq>"):
    if banned in sm:
        warn("sitemap: contains %s, which Google ignores" % banned)
print("  sitemap lists %d URLs, all present" % len(locs))

if "Sitemap: %s/sitemap.xml" % BASE not in read("robots.txt"):
    fail("robots.txt does not point at the sitemap")
if not os.path.exists(os.path.join(ROOT, ".nojekyll")):
    fail(".nojekyll missing, GitHub Pages will run Jekyll and may drop files")
if not SITE.get("google_site_verification"):
    warn("site.json google_site_verification is empty, Search Console will not verify")
if not SITE.get("indexnow_key"):
    warn("site.json indexnow_key is empty, no IndexNow submission possible")

# Internal links and asset references across every page.
print("== links and assets ==")
missing = set()
externals = set()
for f in glob.glob(os.path.join(ROOT, "**", "*.html"), recursive=True):
    if "_work" in f or "_build" in f:
        continue
    h = open(f, encoding="utf-8").read()
    here = os.path.dirname(f)
    for attr in ("href", "src", "srcset"):
        for m in re.finditer(r'%s="([^"]+)"' % attr, h):
            for ref in m.group(1).split(","):
                ref = ref.strip().split(" ")[0]
                if not ref or ref.startswith(("#", "mailto:", "data:")):
                    continue
                if ref.startswith(("http://", "https://", "//")):
                    # Only stylesheets, scripts and images are subresources the
                    # browser must fetch to paint. rel=canonical is an absolute
                    # URL by design and is not fetched.
                    before = h[max(0, m.start() - 120):m.start()]
                    is_sub = attr in ("src", "srcset") or (
                        "<link" in before and "stylesheet" in before)
                    if is_sub:
                        externals.add(ref)
                    continue
                t = os.path.join(ROOT, ref.lstrip("/")) if ref.startswith("/") \
                    else os.path.join(here, ref)
                if os.path.isdir(t):
                    t = os.path.join(t, "index.html")
                if not os.path.exists(t):
                    missing.add("%s -> %s" % (os.path.relpath(f, ROOT), ref))
for m in sorted(missing):
    fail("broken reference: %s" % m)
for x in sorted(externals):
    fail("external subresource, breaks offline first paint: %s" % x)
if not missing and not externals:
    print("  every internal reference resolves, no external subresources")

if re.search(r"@import|fonts\.googleapis|<script(?! type=\"application/ld)", home):
    fail("home: has a script tag or web font import")

print()
for w in warns:
    print("WARN  " + w)
for f_ in fails:
    print("FAIL  " + f_)
print("\n%d fail, %d warn" % (len(fails), len(warns)))
sys.exit(1 if fails else 0)
