# Copyright (C) 2026 Clemens Drüe <druee@uni-trier.de>
# SPDX-License-Identifier: EUPL-1.2
# Licensed under the EUPL

"""Field-by-field comparison of two matched BibTeX entries."""

from ._textutils import normalize_ws

_IGNORE_FIELDS = ("ID",)


def diff_entry_fields(entry_a, entry_b):
    """Returns a list of (field, value_a, value_b, status) rows.

    status is one of 'same', 'changed', 'added' (only in b), 'removed' (only in a).
    The BibTeX entry type (@article, @misc, ...) is included as a synthetic
    '@type' row so type mismatches aren't silently missed.
    """
    rows = []

    type_a = entry_a.get("ENTRYTYPE", "")
    type_b = entry_b.get("ENTRYTYPE", "")
    rows.append(("@type", type_a, type_b, "same" if type_a == type_b else "changed"))

    fields = sorted(
        (set(entry_a.keys()) | set(entry_b.keys()))
        - set(_IGNORE_FIELDS) - {"ENTRYTYPE"}
    )
    for name in fields:
        value_a = entry_a.get(name)
        value_b = entry_b.get(name)
        if value_a is not None and value_b is None:
            rows.append((name, value_a, None, "removed"))
        elif value_a is None and value_b is not None:
            rows.append((name, None, value_b, "added"))
        elif normalize_ws(value_a) == normalize_ws(value_b):
            rows.append((name, value_a, value_b, "same"))
        else:
            rows.append((name, value_a, value_b, "changed"))
    return rows
