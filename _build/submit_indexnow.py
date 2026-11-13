#!/usr/bin/env python3
"""Notify IndexNow of published site URLs after verifying the live ownership file.

Pass canonical URLs or site-relative paths. With no arguments, submit the sitemap.
An accepted submission requests discovery; it does not guarantee indexing.
"""
import argparse
import json
from pathlib import Path
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SITE = json.loads((ROOT / "_build" / "site.json").read_text())
BASE = SITE["base_url"].rstrip("/")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("urls", nargs="*")
    args = parser.parse_args()
    key = SITE.get("indexnow_key")
    if not key:
        parser.error("Set indexnow_key in _build/site.json, rebuild, and publish first.")
    if args.urls:
        urls = [urllib.parse.urljoin(BASE + "/", u) for u in args.urls]
    else:
        sitemap = ET.parse(ROOT / "sitemap.xml")
        urls = [n.text for n in sitemap.findall(
            ".//{http://www.sitemaps.org/schemas/sitemap/0.9}loc"
        )]
    host = urllib.parse.urlparse(BASE).netloc
    if any(urllib.parse.urlparse(u).netloc != host for u in urls):
        parser.error("Every URL must belong to the configured site.")
    key_url = BASE + "/" + key + ".txt"
    headers = {"User-Agent": "Mozilla/5.0"}
    request = urllib.request.Request(key_url, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        if response.read().decode("utf-8").strip() != key:
            parser.error("The live ownership file does not match. Publish the build first.")
    payload = {
        "host": host,
        "key": key,
        "keyLocation": key_url,
        "urlList": list(dict.fromkeys(urls)),
    }
    request = urllib.request.Request(
        "https://api.indexnow.org/indexnow",
        data=json.dumps(payload).encode("utf-8"),
        headers={**headers, "Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        print("IndexNow: HTTP %d, %d URLs submitted for %s."
              % (response.status, len(payload["urlList"]), host))
        if response.status == 202:
            print("Ownership validation is pending.")


if __name__ == "__main__":
    main()
