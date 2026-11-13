# ankit-ai.github.io

Personal site for Ankit Chadha. Static HTML, no build framework, no JavaScript, no
external requests. Every page is one file and one round trip.

The point of the site is citations. Every paper gets its own URL, its own complete
abstract as plain visible text, and its own Google Scholar meta block, because that
is what Scholar requires in order to index a paper at all.

## Layout

```
index.html                    about page
publications/index.html       full list, peer reviewed then preprints then earlier work
papers/<slug>/index.html      one page per paper
papers/<slug>/<paper>.pdf     the PDF, as a SIBLING of the HTML, not in /assets
papers/<slug>/<slug>.bib      downloadable citation, matching the visible BibTeX
404.html  robots.txt  sitemap.xml  .nojekyll
assets/img/headshot-*.{jpg,webp}
assets/img/papers/            4:3 index cards cropped from each paper
assets/img/figs/              natural-aspect body figures cropped from each paper
assets/img/cards/             1200x630 social share cards
assets/pdf/                   the master PDF copies the build reads from
_build/                       the generator and its data, NOT published content
_work/                        research, crops, previews, scratch. not published
```

## Rebuild

```
python3 _build/make_content.py    # only needed if the extraction is rerun
python3 _build/make_cards.py      # only needed if a headline number changes
python3 _build/build.py           # emits every HTML file, copies PDFs into place
python3 _build/check.py           # must print "0 fail" before publishing
```

`_build/build.py` is the only place HTML and CSS live. `_build/site.json` holds the
prose and config, `_build/papers.json` the bibliographic metadata, and
`_build/content.json` the per-paper page content. Edit those, never the generated
HTML, which is overwritten on every build.

WK-Drift uses the final IJCNLP-AACL 2026 proceedings PDF and the publisher's
BibTeX, including its verified November publication month. To recreate its
figure and share card (requires PyMuPDF and Pillow):

```
python3 _build/make_wk_drift_assets.py
python3 _build/make_cards.py --slug wk-drift-procedural-memory-maintenance
```

After a build is published, `python3 _build/submit_indexnow.py` verifies the live
ownership file and submits the sitemap URLs to IndexNow. Pass specific canonical
URLs or site-relative paths to submit just those pages. This requests discovery
by participating search engines; Google and Google Scholar use their own crawlers.

## Local preview

```
python3 -m http.server 8899
open http://localhost:8899/
```

## The rules that are not stylistic

These come from Google Scholar's inclusion guidelines and from Google's
structured-data policy. `_build/check.py` enforces all of them.

1. **One paper, one URL.** Scholar will not index two abstracts on the same page.
2. **`citation_pdf_url` must point at a file in the same directory as the HTML.**
   This is why every PDF is duplicated into its paper directory instead of being
   linked from `/assets/pdf/`.
3. **The complete abstract must be plain visible text.** No `<details>`, no
   accordion, no clamping, no JavaScript reveal. Pages that hide the abstract get
   dropped.
4. **`citation_title`, `citation_author`, `citation_publication_date` are all
   mandatory.** Missing one makes Scholar treat the page as having no metadata at
   all. One `citation_author` tag per author, name only, no affiliations.
5. **Never both `citation_conference_title` and `citation_journal_title`.**
   Preprints get neither.
6. **No `citation_*` tags on the homepage or `/publications/`.**
7. **The site header must render visually smaller than the paper `<h1>`.** Scholar
   uses relative font size to work out which line is the paper title.
8. Section headings stay in sentence case. Title Case can be mistaken for an author
   line.
9. Corrections to Scholar take **6 to 9 months** to propagate. Get the metadata
   right before publishing, not after.

## Honesty rules the content follows

Every number on a paper page appears in that paper and was checked against the PDF
text by a second pass. Results that were null or went the wrong way are included and
marked. Each page names the baseline and gives the from and to values. No citation
counts, download counts, or star counts are mirrored anywhere, because they go stale
and cannot be verified by a reader; the site links to Google Scholar instead. Nothing
claims a venue it has not been accepted to. Preprints are labelled as preprints in
the page body, in the listing, and on the social card.

## Publishing

The site is published at `https://ankitrchadha.com/`. Its source is
`ankit-ai/ankit-ai.github.io`, branch `main`; the GitHub Pages copy uses the same
custom-domain canonical URLs.

1. Edit the source data and generator, recreate changed image assets, then run
   `python3 _build/build.py` and `python3 _build/check.py`.
2. Check desktop and mobile layouts, then commit and push `main`. `_work/` is
   gitignored. `_build/` stays committed so the site is reproducible, and
   `robots.txt` disallows it to avoid indexing duplicate abstracts.
3. Verify the changed pages, sibling PDFs, citation downloads, `robots.txt`, and
   `https://ankitrchadha.com/sitemap.xml` on the live custom domain.
4. Run `python3 _build/submit_indexnow.py` after the ownership file is live.
5. For Google Search Console, verify the custom-domain property and submit
   `https://ankitrchadha.com/sitemap.xml`. The HTML verification token can be added
   to `google_site_verification` in `_build/site.json`; it is currently unset.
   Search Console also supports other verification methods.

Keep canonical paper URLs stable, and use `https://ankitrchadha.com/` as the
homepage on research profiles. A crawl request or sitemap submission does not
guarantee when Google or Google Scholar will index a paper.
