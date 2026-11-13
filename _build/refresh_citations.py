#!/usr/bin/env python3
"""Import a manually fetched, complete Google Scholar profile into a dated snapshot.

Usage:
  python3 _build/refresh_citations.py --html saved-profile.html --as-of YYYY-MM-DD

No fuzzy matches, merged citation counts, scheduled scraping, or invented zeros.
The saved HTML remains in ignored _work/; the public snapshot records its checksum.
"""

import argparse
import hashlib
import json
import re
import unicodedata
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

BUILD = Path(__file__).resolve().parent
PROFILE_ID = "hcslcm0AAAAJ"
PROFILE_URL = "https://scholar.google.com/citations?user=" + PROFILE_ID
ALIASES = {
    "Design, Modeling and Implementation of 8-bit Processor for Intelligent Automatic Chocolate Vending Machine":
        "Design, Modeling and Implementation of 8-bit Processor for Intelligent Automatic Chocolate Vending Machine (AVM)",
}


def normalize(title):
    title = unicodedata.normalize("NFKD", title).replace("&", "and")
    return re.sub(r"[^a-z0-9]", "", title.lower())


class Scholar(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows, self.metrics = [], []
        self.row, self.capture = None, None
        self.name, self.complete = "", False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = attrs.get("class", "").split()
        if attrs.get("id") == "gsc_prf_in":
            self.capture = ("name", tag, "")
        if attrs.get("id") == "gsc_bpf_more" and "disabled" in attrs:
            self.complete = True
        if tag == "tr" and "gsc_a_tr" in classes:
            self.row = {}
        if self.row is not None:
            for field, css in (("title", "gsc_a_at"), ("citations", "gsc_a_ac")):
                if tag == "a" and css in classes:
                    self.capture = (field, tag, "")
                    self.row[field + "_url"] = attrs.get("href", "")
            if tag == "span" and "gsc_a_h" in classes:
                self.capture = ("year", tag, "")
        if tag == "td" and "gsc_rsb_std" in classes:
            self.capture = ("metric", tag, "")

    def handle_data(self, text):
        if self.capture:
            field, tag, old = self.capture
            self.capture = (field, tag, old + text)

    def handle_endtag(self, tag):
        if self.capture and self.capture[1] == tag:
            field, _, text = self.capture
            if field == "name":
                self.name = text.strip()
            elif field == "metric":
                self.metrics.append(int(text.replace(",", "").strip()))
            elif self.row is not None:
                self.row[field] = text.strip()
            self.capture = None
        if tag == "tr" and self.row is not None:
            self.rows.append(self.row)
            self.row = None


def record(row):
    record_url = urljoin(PROFILE_URL, row["title_url"])
    query = parse_qs(urlparse(record_url).query)
    if query.get("user") != [PROFILE_ID]:
        raise ValueError("Scholar record belongs to a different profile")
    raw = row["citations"]
    if raw and not raw.replace(",", "").isdigit():
        raise ValueError("Unrecognized citation count: " + raw)
    return {
        "title": row["title"],
        "record_url": record_url,
        "cited_by_url": row["citations_url"] or "",
        "count": int(raw.replace(",", "")) if raw else None,
        "status": "counted" if raw else "no_citations_listed",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--html", type=Path, required=True)
    parser.add_argument("--as-of", type=date.fromisoformat, required=True)
    args = parser.parse_args()
    if args.as_of > datetime.now(timezone.utc).date():
        parser.error("The snapshot date cannot be in the future")
    raw = args.html.read_bytes()
    profile = Scholar()
    profile.feed(raw.decode("utf-8"))
    if profile.name != "Ankit Chadha" or not profile.complete or len(profile.metrics) != 6:
        parser.error("Expected Ankit Chadha's complete Scholar profile and all six metrics")
    data = json.loads((BUILD / "papers.json").read_text())
    by_title = {}
    for row in profile.rows:
        by_title.setdefault(normalize(row["title"]), []).append(row)

    def match(paper):
        title = paper["title"]
        rows = by_title.get(normalize(ALIASES.get(title, title)), [])
        if not rows:
            raise ValueError("No exact Scholar title match: " + title)
        return [record(row) for row in rows]

    # Resolve every paper before writing anything. Split Scholar records are kept
    # separate because their citing articles may overlap.
    snapshot = {
        "source": "Google Scholar",
        "profile_url": PROFILE_URL,
        "as_of": args.as_of.isoformat(),
        "source_html_sha256": hashlib.sha256(raw).hexdigest(),
        "profile": {
            "citations": profile.metrics[0],
            "h_index": profile.metrics[2],
            "i10_index": profile.metrics[4],
        },
        "papers": {p["slug"]: match(p) for p in data["papers"]},
        "earlier_work": {p["title"]: match(p) for p in data["earlier_work"]},
    }
    (BUILD / "citations.json").write_text(
        json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n"
    )
    print("Verified %d papers; profile reports %d citations as of %s."
          % (len(snapshot["papers"]) + len(snapshot["earlier_work"]),
             snapshot["profile"]["citations"], snapshot["as_of"]))


if __name__ == "__main__":
    main()
