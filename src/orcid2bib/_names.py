# Copyright (C) 2026 Clemens Drüe <druee@uni-trier.de>
# SPDX-License-Identifier: EUPL-1.2
# Licensed under the EUPL

"""BibTeX author-field parsing for bibdiff's matching logic."""

import re

from ._textutils import normalize_loose, normalize_ws

_PARTICLES = {
    "van", "von", "der", "den", "de", "la", "le", "di", "da",
    "do", "dos", "du", "al", "el", "bin", "ibn", "st",
}


def split_bibtex_authors(author_field):
    """Splits a BibTeX 'author' field into a list of individual name strings."""
    if not author_field:
        return []
    parts = re.split(r"\s+and\s+", str(author_field).strip(), flags=re.IGNORECASE)
    return [p.strip().strip(",") for p in parts if p.strip()]


def parse_name(name):
    """Returns (family, given) for one BibTeX name, either 'Family, Given' or 'Given Family'."""
    name = normalize_ws(name)
    if not name:
        return "", ""
    if "," in name:
        family, _, given = name.partition(",")
        return family.strip(), given.strip()
    tokens = name.split(" ")
    if len(tokens) == 1:
        return tokens[0], ""
    split_idx = len(tokens) - 1
    while split_idx > 0 and tokens[split_idx - 1].lower().rstrip(".") in _PARTICLES:
        split_idx -= 1
    family = " ".join(tokens[split_idx:])
    given = " ".join(tokens[:split_idx])
    return family, given


def given_initial(given):
    """First letter of a normalized given-name string, or '' if empty."""
    normalized = normalize_loose(given)
    return normalized[0] if normalized else ""
