# Copyright (C) 2026 Clemens Drüe <druee@uni-trier.de>
# SPDX-License-Identifier: EUPL-1.2
# Licensed under the EUPL

"""Rendering matched-entry differences as unified diff, context diff, or side-by-side."""

import difflib
import textwrap

from ._compare import diff_entry_fields

STYLES = ("diff", "context", "side-by-side")


def entry_to_lines(entry):
    """Serializes a BibTeX entry to a stable, sorted-field text form for diffing."""
    key = entry.get("ID") or "(none)"
    entry_type = entry.get("ENTRYTYPE") or "(none)"
    lines = [f"@{entry_type}{{{key},"]
    for name in sorted(k for k in entry if k not in ("ID", "ENTRYTYPE")):
        lines.append(f"  {name} = {{{entry[name]}}},")
    lines.append("}")
    return lines


def render_side_by_side(label_a, label_b, rows, width=36):
    def wrap(value):
        text = "-" if value is None else str(value)
        return textwrap.wrap(text, width) or [""]

    field_w = 12
    lines = []
    header = f"{'FIELD':<{field_w}}| {label_a[:width]:<{width}} | {label_b[:width]:<{width}}"
    lines.append(header)
    lines.append("-" * len(header))
    for name, value_a, value_b, status in rows:
        marker = " " if status == "same" else "*"
        wrapped_a, wrapped_b = wrap(value_a), wrap(value_b)
        row_count = max(len(wrapped_a), len(wrapped_b))
        for idx in range(row_count):
            col_a = wrapped_a[idx] if idx < len(wrapped_a) else ""
            col_b = wrapped_b[idx] if idx < len(wrapped_b) else ""
            field_label = f"{marker}{name}" if idx == 0 else ""
            lines.append(f"{field_label:<{field_w}}| {col_a:<{width}} | {col_b:<{width}}")
    return "\n".join(lines)


def render_diff(label_a, entry_a, label_b, entry_b, style="diff"):
    if style not in STYLES:
        raise ValueError(f"Unknown style {style!r}; expected one of {STYLES}")

    if style == "side-by-side":
        rows = diff_entry_fields(entry_a, entry_b)
        return render_side_by_side(label_a, label_b, rows)

    lines_a = entry_to_lines(entry_a)
    lines_b = entry_to_lines(entry_b)
    if style == "diff":
        diff = difflib.unified_diff(lines_a, lines_b, fromfile=label_a, tofile=label_b, lineterm="")
    else:  # context
        diff = difflib.context_diff(lines_a, lines_b, fromfile=label_a, tofile=label_b, lineterm="")
    return "\n".join(diff)
