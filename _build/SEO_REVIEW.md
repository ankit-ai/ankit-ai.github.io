# Research discovery and citation review

Verified and updated 2026-11-13.

The main opportunity was to make each paper easier to find, understand, and cite.
The site already had useful summaries and complete abstracts. The update connects
those strengths to current publisher records, clearer navigation, and practical
citation tools.

## Published improvements

- Added WK-Drift with its final proceedings PDF, official title, authors, DOI,
  publication month, complete PDF abstract, figure, and measured results.
  Homepage features, the publication list, and the agent-memory guide link to it.
- Updated APEX-EM and Routed Graph Handoff to their published Findings of EMNLP
  records, official BibTeX, page ranges, DOIs, and final PDFs. Stable paper-page
  URLs remain the reference points across versions.
- Kept full official titles in headings and scholarly metadata while using
  shorter, descriptive browser/search titles. Updated descriptions and social
  cards, including publisher status and meaningful image descriptions.
- Added publication search and topic filtering. The initial HTML retains all
  papers, abstracts, links, and citations when JavaScript is disabled.
- Added copyable BibTeX, per-paper BibTeX/RIS/CSL JSON, complete collection
  downloads, and an Atom feed.
- Added PDF canonical response headers, citation-file MIME types and indexing
  exclusions, richer article/guide/contact structured data, and large-image
  preview permission. The sitemap contains canonical HTML pages.
- Refreshed citation counts from the complete public Google Scholar profile.
  The snapshot has a visible source date, record links, and a source checksum.
  Separate records are displayed separately because their citations may overlap.
  Public pages show positive counts only; blank and zero counts are omitted.
- Fixed narrow-screen navigation and checked layouts at 360, 390, 768, and
  1440 pixels. Checked exact clipboard citations, filtering, images, downloads,
  scholarly metadata, and internal links.

## Account-level follow-ups

1. Enable Cloudflare **SSL/TLS → Edge Certificates → Always Use HTTPS**. A public
   browser-like HTTP request still returns the page over HTTP. HTTPS canonicals
   and HSTS already exist, and `www` redirects to the apex domain. Cloudflare
   Pages `_redirects` does not support domain-level rules, so this requires the
   Cloudflare zone setting.
2. In Google Search Console, verify the domain property if needed, submit
   `https://ankitrchadha.com/sitemap.xml`, and inspect the WK-Drift page.
   The HTML verification token is unset; DNS verification may already exist.
   IndexNow submission does not verify or submit a Google property.
3. Review the two Google Scholar records for Question-Context Alignment and
   Answer-Context Dependencies. The website preserves their separate counts.
   Only merge them in Scholar after checking that both represent the same paper.
4. Change the Google Scholar profile homepage from the GitHub Pages mirror to
   the canonical custom domain. The website and GitHub profile already use the
   custom-domain paper links.

## Highest-value next content

When public research artifacts are ready, link the benchmark data, code, and
reproduction instructions from their paper pages. WK-Drift currently has no
public repository listed in the verified record. Consistent official titles,
DOIs, author names, and stable URLs across releases help readers associate the
artifacts with the right publication.

Use Search Console indexing, search impressions, and clicks to assess discovery;
use the dated Scholar snapshot for reported citations. Recheck those measures
after crawlers have processed the update. Neither metadata changes nor an
accepted indexing request guarantee ranking or additional citations.
