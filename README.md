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
