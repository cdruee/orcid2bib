# Copyright (C) 2026 Clemens Drüe <druee@uni-trier.de>
# SPDX-License-Identifier: EUPL-1.2
# Licensed under the EUPL

"""bibdiff CLI: compare two BibTeX files.

Procedure:
  a) parse and validate both files,
  b) find likely duplicate entries within each file,
  c) match corresponding entries across the two files,
  d) for each matched pair, diff every field and report the result.
"""

import argparse
import sys

from ._compare import diff_entry_fields
from ._matching import (
    MATCH_THRESHOLD,
    POSSIBLE_THRESHOLD,
    find_duplicates,
    match_entries,
)
from ._parser import BibSyntaxError, load_bib_file
from ._report import STYLES, render_diff


def build_parser():
    parser = argparse.ArgumentParser(
        prog="bibdiff",
        description=(
            "Compare two BibTeX files: validate syntax, find duplicates within each "
            "file, match corresponding entries across files, and diff their fields."
        ),
    )
    parser.add_argument("first", help="First .bib file")
    parser.add_argument("second", help="Second .bib file")
    parser.add_argument(
        "--style",
        choices=STYLES,
        default="diff",
        help="Output style for field-level differences (default: diff)",
    )
    parser.add_argument(
        "--match-threshold",
        type=float,
        default=MATCH_THRESHOLD,
        metavar="SCORE",
        help=f"Minimum score (0-1) to treat two entries as a confirmed match (default: {MATCH_THRESHOLD})",
    )
    parser.add_argument(
        "--possible-threshold",
        type=float,
        default=POSSIBLE_THRESHOLD,
        metavar="SCORE",
        help=f"Minimum score (0-1) to flag two entries as a possible match needing review (default: {POSSIBLE_THRESHOLD})",
    )
    parser.add_argument(
        "-o", "--output",
        metavar="FILE",
        help="Write the report to a file instead of stdout",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Print progress details (files parsed, entry counts, matching progress)",
    )
    parser.add_argument(
        "-d", "--debug",
        action="store_true",
        help="Also print the score breakdown (per-component scores and weights) "
             "for every match, possible match, and duplicate pair found",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.1.0",
    )
    return parser


def _vprint(verbose, msg, stream):
    if verbose:
        print(f"[*] {msg}", file=stream)


def _make_debug_sink(label, args, stream):
    if not args.debug:
        return None

    def sink(i, j, result):
        is_interesting = result.tier in ("citekey", "doi", "isbn") or result.total >= args.possible_threshold
        if not is_interesting:
            return
        parts = ", ".join(f"{name}={score:.2f}(w={weight:.2f})" for name, (score, weight) in result.breakdown.items())
        print(f"    [d] {label} #{i} vs #{j}: total={result.total:.3f} tier={result.tier}  {parts}", file=stream)

    return sink


def _entry_label(filename, entry):
    return f"{filename}: {entry.get('ID', '?')}"


def _report_duplicates(filename, entries, groups, stream):
    print(f"=== Possible duplicates within {filename} ===", file=stream)
    if not groups:
        print("  None found.", file=stream)
        return
    for group in groups:
        keys = [entries[i].get("ID", "?") for i in group]
        print(f"  {', '.join(keys)}", file=stream)


def _report_matched(title, pairs, entries_a, entries_b, args, first, second, stream):
    print(f"\n=== {title} ({len(pairs)}) ===", file=stream)
    for i, j, result in pairs:
        entry_a, entry_b = entries_a[i], entries_b[j]
        label_a = _entry_label(first, entry_a)
        label_b = _entry_label(second, entry_b)
        print(f"\n--- {label_a}  <->  {label_b}  (score={result.total:.2f}, via {result.tier}) ---", file=stream)
        if args.debug:
            parts = ", ".join(f"{name}={score:.2f}(w={weight:.2f})" for name, (score, weight) in result.breakdown.items())
            print(f"    [d] breakdown: {parts or '(identifier match, no component breakdown)'}", file=stream)
        if args.style == "side-by-side":
            rows = diff_entry_fields(entry_a, entry_b)
            changed = sum(1 for row in rows if row[3] != "same")
            if changed == 0:
                print("  (all fields identical)", file=stream)
                continue
        print(render_diff(label_a, entry_a, label_b, entry_b, style=args.style), file=stream)


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    stream = open(args.output, "w", encoding="utf-8") if args.output else sys.stdout
    try:
        try:
            entries_a = load_bib_file(args.first)
            entries_b = load_bib_file(args.second)
        except BibSyntaxError as exc:
            print(f"[-] {exc}", file=sys.stderr)
            sys.exit(2)

        _vprint(args.verbose, f"Parsed {len(entries_a)} entries from {args.first}", stream)
        _vprint(args.verbose, f"Parsed {len(entries_b)} entries from {args.second}", stream)

        dups_a, _ = find_duplicates(
            entries_a, threshold=args.match_threshold,
            debug_sink=_make_debug_sink("dup-A", args, stream),
        )
        dups_b, _ = find_duplicates(
            entries_b, threshold=args.match_threshold,
            debug_sink=_make_debug_sink("dup-B", args, stream),
        )
        _report_duplicates(args.first, entries_a, dups_a, stream)
        print(file=stream)
        _report_duplicates(args.second, entries_b, dups_b, stream)

        _vprint(args.verbose, "Matching entries across files...", stream)
        matches, possibles, unmatched_a, unmatched_b = match_entries(
            entries_a, entries_b,
            match_threshold=args.match_threshold,
            possible_threshold=args.possible_threshold,
            debug_sink=_make_debug_sink("match", args, stream),
        )

        _report_matched("Matched entries", matches, entries_a, entries_b, args, args.first, args.second, stream)
        if possibles:
            _report_matched(
                "Possible matches needing review", possibles,
                entries_a, entries_b, args, args.first, args.second, stream,
            )

        print(f"\n=== Only in {args.first} ({len(unmatched_a)}) ===", file=stream)
        for i in unmatched_a:
            entry = entries_a[i]
            print(f"  {entry.get('ID', '?')}: {entry.get('title', '')}", file=stream)

        print(f"\n=== Only in {args.second} ({len(unmatched_b)}) ===", file=stream)
        for j in unmatched_b:
            entry = entries_b[j]
            print(f"  {entry.get('ID', '?')}: {entry.get('title', '')}", file=stream)

        dup_count_a = sum(len(g) for g in dups_a)
        dup_count_b = sum(len(g) for g in dups_b)
        print("\n=== Summary ===", file=stream)
        print(f"  {args.first}: {len(entries_a)} entries, {dup_count_a} in {len(dups_a)} duplicate group(s)", file=stream)
        print(f"  {args.second}: {len(entries_b)} entries, {dup_count_b} in {len(dups_b)} duplicate group(s)", file=stream)
        print(
            f"  Matched: {len(matches)}  Possible: {len(possibles)}  "
            f"Only in {args.first}: {len(unmatched_a)}  Only in {args.second}: {len(unmatched_b)}",
            file=stream,
        )
    finally:
        if args.output:
            stream.close()


if __name__ == "__main__":
    main()
