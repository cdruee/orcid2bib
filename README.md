# orcid2bib

[![License: EUPL-1.2](https://img.shields.io/badge/License-EUPL--1.2-blue.svg)](LICENSE)
[![GitHub](https://img.shields.io/badge/GitHub-cdruee%2Forcid2bib-181717?logo=github)](https://github.com/cdruee/orcid2bib)

Fetch all public works from an ORCID profile and compile them into a single BibTeX (`.bib`) file.

Repository: [github.com/cdruee/orcid2bib](https://github.com/cdruee/orcid2bib)

For each work, `orcid2bib` builds a BibTeX entry from the ORCID record:

- **Entry type** is guessed from the ORCID work type (e.g. `journal-article` → `@article`,
  `conference-paper` → `@inproceedings`, `book-chapter` → `@incollection`, `dissertation-thesis` →
  `@phdthesis`, `preprint`/`working-paper` → `@unpublished`, etc.), falling back to `@misc` for
  anything unrecognized. Only standard (plain-LaTeX) BibTeX entry types are used.
- **Author** is taken from the work's ORCID contributors (author-role entries).
- **Journal / booktitle**, **year**, **title**, and **DOI** are filled from ORCID where present.
- If a DOI is found, it's resolved (via `doi.org` content negotiation for CSL-JSON metadata) to
  fetch **author, journal, year, volume, number, pages,** and **keywords** — overriding the ORCID
  values with the DOI-sourced ones where available, since publisher metadata is usually more
  complete and accurate. Use `-n`/`--no-doi-lookup` to skip this and rely on ORCID data only.

## Install

Clone the repository and install it (editable install is recommended during development):

```bash
git clone https://github.com/cdruee/orcid2bib.git
cd orcid2bib
pip install -e .
```

(or `pip install -e ".[dev]"` to include test dependencies)

You can also install directly from GitHub without cloning first:

```bash
pip install "git+https://github.com/cdruee/orcid2bib.git"
```

## Usage

```bash
orcid2bib 0000-0002-0103-4275
```

Options:

```
usage: orcid2bib [-h] [-o FILE] [--delay SECONDS] [-n] [-v] [--version] orcid_id

positional arguments:
  orcid_id              ORCID iD of the profile to fetch, e.g. 0000-0002-0103-4275

options:
  -h, --help             show this help message and exit
  -o FILE, --output FILE
                          Output .bib file path (default: <orcid_id>_publications.bib)
  --delay SECONDS        Delay between ORCID API requests, in seconds (default: 0.2)
  -n, --no-doi-lookup    Disable resolving each work's DOI for extra metadata (author,
                          journal, year, volume, number, pages, keywords). By default,
                          DOI-resolved data overrides ORCID's own fields where available.
  -v, --verbose          Print diagnostic details per work: detected entry type, DOI
                          found, DOI-lookup requests/responses, and why fields were or
                          weren't overridden.
  --version              show program's version number and exit
```

Example with a custom output path:

```bash
orcid2bib 0000-0002-0103-4275 -o my_publications.bib
```

Example skipping DOI lookups (ORCID data only, faster, no extra network calls):

```bash
orcid2bib 0000-0002-0103-4275 -n
```

Example diagnosing why DOI enrichment isn't showing up:

```bash
orcid2bib 0000-0002-0103-4275 -v
```

## As a library

```python
from orcid2bib import run

run("0000-0002-0103-4275", output_filename="my_publications.bib")
```

## bibdiff

`bibdiff` compares two BibTeX files: it validates their syntax, flags likely duplicate entries
within each file, matches corresponding entries across the two files, and shows a field-by-field
diff for each matched pair.

```bash
bibdiff mylibrary.bib exported_from_zotero.bib
```

**How matching works**, in order of confidence:

1. Identical citation key.
2. Identical DOI (or, failing that, ISBN), normalized (case, `https://doi.org/` prefix, hyphens).
3. A weighted, typo- and abbreviation-tolerant score combining whichever of first author, year,
   title, and journal/booktitle/pages are available. This also tolerates first-name initials
   (`J. Smith` vs `John Smith`) and abbreviated venue names (`J. Am. Chem. Soc.` vs `Journal of
   the American Chemical Society`).

The same scoring is used to detect probable duplicates *within* a single file.

Options:

```
usage: bibdiff [-h] [--style {diff,context,side-by-side}]
               [--match-threshold SCORE] [--possible-threshold SCORE]
               [-o FILE] [-v] [-d] [--version]
               first second

positional arguments:
  first                 First .bib file
  second                Second .bib file

options:
  -h, --help            show this help message and exit
  --style {diff,context,side-by-side}
                        Output style for field-level differences (default: diff)
  --match-threshold SCORE
                        Minimum score (0-1) to treat two entries as a confirmed match
                        (default: 0.75)
  --possible-threshold SCORE
                        Minimum score (0-1) to flag two entries as a possible match
                        needing review (default: 0.55)
  -o FILE, --output FILE
                        Write the report to a file instead of stdout
  -v, --verbose         Print progress details (files parsed, entry counts, matching
                        progress)
  -d, --debug           Also print the score breakdown (per-component scores and
                        weights) for every match, possible match, and duplicate pair
                        found
  --version             show program's version number and exit
```

Example with a side-by-side field comparison:

```bash
bibdiff mylibrary.bib exported_from_zotero.bib --style side-by-side
```

Example seeing exactly how each score was computed:

```bash
bibdiff mylibrary.bib exported_from_zotero.bib -d
```

## Contributing

Bug reports and pull requests are welcome at
[github.com/cdruee/orcid2bib/issues](https://github.com/cdruee/orcid2bib/issues).

## License

Copyright (C) 2026 Clemens Drüe <druee@uni-trier.de>

Licensed under the **EUPL-1.2** (European Union Public Licence, version 1.2). See [LICENSE](LICENSE)
for the full text.

## Author

Clemens Drüe (druee@uni-trier.de)

## Acknowledgments

Developed with the assistance of Claude Sonnet 5 (Anthropic).
