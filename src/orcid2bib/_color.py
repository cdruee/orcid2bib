# Copyright (C) 2026 Clemens Drüe <druee@uni-trier.de>
# SPDX-License-Identifier: EUPL-1.2
# Licensed under the EUPL

"""Minimal ANSI color helpers shared by bibdiff's CLI and report rendering."""

_CODES = {
    "red": "31",
    "green": "32",
    "yellow": "33",
    "cyan": "36",
    "bold": "1",
}


def paint(text, color, enabled):
    """Wraps `text` in an ANSI color code if `enabled` and `text` is non-empty."""
    if not enabled or not text:
        return text
    return f"\033[{_CODES[color]}m{text}\033[0m"
