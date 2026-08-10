# Copyright (C) 2026 Clemens Drüe <druee@uni-trier.de>
# SPDX-License-Identifier: EUPL-1.2
# Licensed under the EUPL

"""BibTeX file loading and basic syntax validation for bibdiff."""


class BibSyntaxError(Exception):
    """Raised when a .bib file can't be read or doesn't look syntactically valid."""


def _check_brace_balance(text, path):
    """Cheap sanity check that catches truncated files / stray braces early,
    with a useful line number, before handing off to the full parser."""
    depth = 0
    for lineno, line in enumerate(text.splitlines(), 1):
        for ch in line:
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth < 0:
                    raise BibSyntaxError(f"{path}: unbalanced '}}' at line {lineno}")
    if depth != 0:
        raise BibSyntaxError(f"{path}: {depth} unclosed '{{' brace(s) (check the end of the file)")


def load_bib_file(path):
    """Loads and validates a .bib file, returning its list of entries (as dicts).

    Each entry dict has at least 'ID' (citation key) and 'ENTRYTYPE' (article,
    book, misc, ...), plus whatever BibTeX fields the entry defines.
    """
    try:
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
    except OSError as exc:
        raise BibSyntaxError(f"Could not read {path}: {exc}") from exc

    _check_brace_balance(text, path)

    try:
        import bibtexparser
        from bibtexparser.bparser import BibTexParser
    except ImportError as exc:
        raise BibSyntaxError(
            "The 'bibtexparser' package is required for bibdiff. "
            "Install it with: pip install bibtexparser"
        ) from exc

    bib_parser = BibTexParser(common_strings=True)
    bib_parser.ignore_nonstandard_types = False
    try:
        database = bibtexparser.loads(text, parser=bib_parser)
    except Exception as exc:  # bibtexparser doesn't expose a narrower base exception
        raise BibSyntaxError(f"{path}: failed to parse BibTeX ({exc})") from exc

    entries = database.entries
    if not entries:
        raise BibSyntaxError(f"{path}: no valid BibTeX entries found")
    for entry in entries:
        if not entry.get("ID"):
            raise BibSyntaxError(f"{path}: found an entry with no citation key")

    return entries
