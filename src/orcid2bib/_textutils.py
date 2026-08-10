# Copyright (C) 2026 Clemens Drüe <druee@uni-trier.de>
# SPDX-License-Identifier: EUPL-1.2
# Licensed under the EUPL

"""Text normalization helpers shared by bibdiff's matching and reporting code."""

import re
import unicodedata

_STOPWORDS = {
    "a", "an", "the", "of", "and", "or", "in", "on", "for", "to",
    "with", "from", "at", "by", "als", "die", "der", "das", "und",
}


def strip_accents(text):
    """Removes diacritics so e.g. 'Voß'/'Voss' or 'Muller'/'Müller' compare equal-ish."""
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(c for c in normalized if not unicodedata.combining(c))


def normalize_ws(value):
    """Collapses whitespace/newlines; treats None as empty string."""
    if value is None:
        return ""
    return " ".join(str(value).split())


def normalize_loose(value):
    """Lowercase, accent- and punctuation-stripped, whitespace-collapsed form.

    Used for fuzzy/typo-tolerant comparisons -- deliberately lossy.
    """
    if not value:
        return ""
    text = strip_accents(str(value))
    text = text.lower()
    text = re.sub(r"[{}\\]", "", text)  # stray BibTeX braces/backslashes
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return " ".join(text.split())


def significant_words(value):
    """Words from `value`, normalized and with common stopwords removed."""
    return [w for w in normalize_loose(value).split() if w not in _STOPWORDS]
