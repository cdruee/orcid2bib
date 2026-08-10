# Copyright (C) 2026 Clemens Drüe <druee@uni-trier.de>
# SPDX-License-Identifier: EUPL-1.2
# Licensed under the EUPL

"""orcid2bib: fetch public works from an ORCID profile and compile them to BibTeX.

This package also ships a `bibdiff` tool for comparing BibTeX files.
"""

from .orcid import (
    build_bibtex_entry,
    fetch_work_details,
    get_doi_metadata,
    get_orcid_works,
    run,
)

try:
    # Generated at build/install time by setuptools_scm from the latest git tag.
    from ._version import version as __version__
except ImportError:
    try:
        from importlib.metadata import version as _pkg_version
        __version__ = _pkg_version("orcid2bib")
    except Exception:
        __version__ = "0.0.0+unknown"

__all__ = [
    "get_orcid_works",
    "get_doi_metadata",
    "build_bibtex_entry",
    "fetch_work_details",
    "run",
]
