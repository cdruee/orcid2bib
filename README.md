# orcid2bib

Fetch all public works from an ORCID profile and compile them into a single BibTeX (`.bib`) file.

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

```bash
pip install -e .
```

(or `pip install -e ".[dev]"` to include test dependencies)

## Usage

```bash
orcid2bib 0000-0002-0103-4275
```

Options:

```
usage: orcid2bib [-h] [-o FILE] [--delay SECONDS] [-n] [--version] orcid_id

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

## As a library

```python
from orcid2bib import run

run("0000-0002-0103-4275", output_filename="my_publications.bib")
```
