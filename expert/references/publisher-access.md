# Publisher access: what fetches, and what to do when it does not

Facts established by fetching (2026-09, from a plain `curl` in a sandbox), not guessed.
Hosts change: re-test cheaply (one request, short timeout) before relying on one, and
put what is particular to your institution or network in the librarian's project memory
of the library home, not here. The fetch budget stays the librarian's: at most two
attempts per source.

## Reliable

- **arXiv** (`/abs/`, `/pdf/`, `/e-print/`). The e-print is a tarball, sometimes a bare
  gzipped `.tex` (then `gunzip` instead of `tar`); some submissions ship only a PDF.
- **Crossref** (`api.crossref.org/works/<doi>`): a good record, but often only the first
  page; take the page range from the journal's own landing page.
- **Clay Mathematics Institute proceedings** are hosted in full by CMI
  (`https://www.claymath.org/library/proceedings/cmip0NN<letter>.pdf`, e.g. `cmip010c.pdf`
  for volume 10), with a reproduction-for-research notice in the front matter. Check them
  first for a classical fact restated by a summer-school chapter before reaching for a
  paywalled textbook.
- **Authors' own pages** usually serve preprints and sometimes scanned chapters (an OCR
  layer may be garbled: read such pages as images and quote from those).

## Not fetchable by script

- **JSTOR** (`www.jstor.org/stable/pdf/<id>.pdf`) answers `200` with a ~3 kB HTML
  "Client Challenge": a JavaScript bot check that runs *before* entitlement is looked
  at. No user agent and no institutional address gets `curl` past it. A JSTOR-only paper
  is saved from a real browser by the human into the library, then cached as usual.
- **Project Euclid** (old Acta and similar) returns an Incapsula bot-challenge shell
  (`NOINDEX, NOFOLLOW`), the same failure mode: a browser save by hand.
- **Annals of Mathematics before ~2000**: the journal site serves a landing page only
  (authors, page range, DOI), which is a good bibliographic record; the text is JSTOR's.
- **link.springer.com** answers `303` to `curl`, and redirects a PDF request to a cookie
  error. Don't burn calls retrying.

## Needs care

- **Math-Net.Ru** (Russian originals: Mat. Zametki, Mat. Sbornik, …): the HTML answers
  `403` to `curl` but reads with a web fetch; the PDF endpoint
  `https://www.mathnet.ru/php/getFT.phtml?jrnid=<jrn>&paperid=<id>&what=fullt&option_lang=rus`
  works with `curl` only with a browser `User-Agent`. The scans' text layer drops every
  Cyrillic character: read the pages as images and quote from those.
- **An unreachable origin host** (a connection-level timeout on every address): try the
  origin once with a short timeout (and with and without `www.`), then a Wayback Machine
  snapshot, `https://web.archive.org/web/<date>/<original-url>`, by `curl`. Check the
  snapshot's title page against the known title before trusting it.
- **A VPN is not an entitlement.** An institutional VPN may egress from a guest address
  block the library never registered with publishers. Before concluding that a paywall
  is "just blocked" or "now open", check the egress (`curl -s https://api.ipify.org`
  and an RDAP lookup of the address).

## A paywalled textbook with no open primary text

Do not fetch a scan of an in-print book, even when a mirror turns up in search: it is a
pirated copy. **Corroborate the pinpoint second-hand** instead: find open-access arXiv
papers that cite the book by bracketed pinpoint (`grep` their extraction for
`"[KEY, Theorem II.4.1]"`), and read enough context to confirm the quoted statement is
the one the draft needs, not just that the number exists. Two independent sources
agreeing is fair confidence; one is weaker and the card says so. A search engine's
summary is not evidence: download and grep the citing paper. Record the result on the
card as second-hand corroboration, not a primary read, and the book in `index.md` as
`not cached — paywalled`.
