"""orcid2bib: fetch public works from an ORCID profile and compile them to BibTeX."""

from .core import (
    build_bibtex_entry,
    fetch_work_details,
    get_doi_metadata,
    get_orcid_works,
    run,
)

__version__ = "0.2.0"

__all__ = [
    "get_orcid_works",
    "get_doi_metadata",
    "build_bibtex_entry",
    "fetch_work_details",
    "run",
]
