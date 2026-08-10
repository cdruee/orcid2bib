# Copyright (C) 2026 Clemens Drüe <druee@uni-trier.de>
# SPDX-License-Identifier: EUPL-1.2
# Licensed under the EUPL

"""bibdiff CLI: compare two BibTeX files.

Procedure:
  a) parse and validate both files,
  b) find likely duplicate entries within each file,
  c) match corresponding entries across the two files,
  d) for each matched pair, diff every field and report the result.

Modeled on the classic `diff` tool's conventions: normal output is just the
differences (no section headers/counts -- those are verbose-only), -q/--brief
mirrors `diff -q`, -s/--report-identical-files mirrors GNU diff's flag of the
same name, and -N/--new-file mirrors `diff -N` (treat a missing counterpart
as blank instead of listing it separately).
"""

import argparse
import sys

from ._color import paint
from ._compare import diff_entry_fields
from ._matching import (
    MATCH_THRESHOLD,
    POSSIBLE_THRESHOLD,
    find_duplicates,
    match_entries,
)
from ._parser import BibSyntaxError, load_bib_file
from ._report import render_diff

_EMPTY_ENTRY = {"ID": "", "ENTRYTYPE": ""}


def build_parser():
    parser = argparse.ArgumentParser(
        prog="bibdiff",
        description=(
            "Compare two BibTeX files: validate syntax, find duplicates within each "
            "file, match corresponding entries across files, and diff their fields. "
            "Normal output is just the differences, as with diff(1)."
        ),
    )
    parser.add_argument("first", help="First .bib file")
    parser.add_argument("second", help="Second .bib file")

    style_group = parser.add_mutually_exclusive_group()
    style_group.add_argument(
        "-c", "--context",
        action="store_true",
        help="Show field differences in context-diff style (default: unified diff)",
    )
    style_group.add_argument(
        "-y", "--side-by-side",
        action="store_true",
        help="Show field differences side by side (default: unified diff)",
    )

    parser.add_argument(
        "-q", "--brief",
        action="store_true",
        help='Report only whether entries differ, one line per pair: '
             '"KEY1 KEY2 differ", or "KEY1 KEY2 renamed" if only the citation '
             'key differs. With -s, also reports "KEY1 KEY2 are identical".',
    )
    parser.add_argument(
        "-s", "--report-identical-files",
        action="store_true",
        dest="report_identical",
        help="Also report matched pairs with no differences at all "
             "(same citation key, all fields identical). Omitted by default.",
    )
    parser.add_argument(
        "-N", "--new-file",
        action="store_true",
        dest="new_file",
        help="Treat an entry missing on one side as blank there and diff it "
             "against the blank, instead of listing it under 'Only in ...'.",
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
        help="Also print progress details, possible-duplicate listings, section "
             "headers/counts, and a final summary. Normal output has none of these.",
    )
    parser.add_argument(
        "-d", "--debug",
        action="store_true",
        help="Also print the score breakdown (per-component scores and weights) "
             "for every match, possible match, and duplicate pair found",
    )
    parser.add_argument(
        "--color",
        action="store_true",
        help="Colorize output (green=added, red=removed) when writing to a "
             "terminal, as diff(1)'s --color=auto does.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.2.0",
    )
    return parser


def _resolve_style(args):
    if args.side_by_side:
        return "side-by-side"
    if args.context:
        return "context"
    return "diff"


def _resolve_color(args, stream):
    """--color behaves like diff's --color=auto: on only when writing to a terminal."""
    if not args.color:
        return False
    return hasattr(stream, "isatty") and stream.isatty()


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
    return f"{filename}: {entry.get('ID') or '?'}"


def _classify_pair(key_a, key_b, rows):
    """Returns 'differ', 'renamed' (only the citekey differs), or 'identical'."""
    if any(row[3] != "same" for row in rows):
        return "differ"
    if key_a != key_b:
        return "renamed"
    return "identical"


def _print_pair(entry_a, entry_b, result, label_a, label_b, args, stream):
    """Prints one compared pair per the chosen style/brief/report-identical settings.

    Returns (printed, differs): whether anything was printed, and whether the
    pair counts as a difference (used for the process exit code).
    """
    rows = diff_entry_fields(entry_a, entry_b)
    key_a = entry_a.get("ID") or "(none)"
    key_b = entry_b.get("ID") or "(none)"
    status = _classify_pair(key_a, key_b, rows)
    differs = status != "identical"

    if status == "identical" and not args.report_identical:
        return False, differs

    color = args.color_enabled

    if args.brief:
        if status == "differ":
            print(paint(f"{key_a} {key_b} differ", "red", color), file=stream)
        elif status == "renamed":
            print(paint(f"{key_a} {key_b} renamed", "yellow", color), file=stream)
        else:
            print(paint(f"{key_a} {key_b} are identical", "green", color), file=stream)
        return True, differs

    score_note = f"(score={result.total:.2f}, via {result.tier})" if result is not None else "(no entry on the other side)"
    print(paint(f"\n--- {label_a}  <->  {label_b}  {score_note} ---", "bold", color), file=stream)
    if args.debug and result is not None:
        parts = ", ".join(f"{name}={score:.2f}(w={weight:.2f})" for name, (score, weight) in result.breakdown.items())
        print(f"    [d] breakdown: {parts or '(identifier match, no component breakdown)'}", file=stream)

    if status != "differ":
        note = "entries are identical" if status == "identical" else "citation key differs; all fields identical"
        note_color = "green" if status == "identical" else "yellow"
        print(paint(f"  ({note})", note_color, color), file=stream)
        return True, differs

    print(render_diff(label_a, entry_a, label_b, entry_b, style=args.style, color=color), file=stream)
    return True, differs


def _report_duplicates(filename, entries, groups, stream):
    print(f"=== Possible duplicates within {filename} ===", file=stream)
    if not groups:
        print("  None found.", file=stream)
        return
    for group in groups:
        keys = [entries[i].get("ID", "?") for i in group]
        print(f"  {', '.join(keys)}", file=stream)


def _report_unmatched(filename, entries, indices, args, stream, side, color=False):
    line_color = "red" if side == "a" else "green"
    for i in indices:
        entry = entries[i]
        key = entry.get("ID", "?")
        if args.brief:
            print(paint(f"Only in {filename}: {key}", line_color, color), file=stream)
        else:
            line = f"only in {filename}: {key} ({entry.get('title', '')})"
            print(paint(line, line_color, color), file=stream)


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    args.style = _resolve_style(args)

    stream = open(args.output, "w", encoding="utf-8") if args.output else sys.stdout
    args.color_enabled = _resolve_color(args, stream)
    any_diff = False
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
        if args.verbose:
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

        if args.verbose:
            print(f"\n=== Matched entries ({len(matches)}) ===", file=stream)
        for i, j, result in matches:
            entry_a, entry_b = entries_a[i], entries_b[j]
            label_a, label_b = _entry_label(args.first, entry_a), _entry_label(args.second, entry_b)
            _, differs = _print_pair(entry_a, entry_b, result, label_a, label_b, args, stream)
            any_diff = any_diff or differs

        if possibles:
            if args.verbose:
                print(f"\n=== Possible matches needing review ({len(possibles)}) ===", file=stream)
            for i, j, result in possibles:
                entry_a, entry_b = entries_a[i], entries_b[j]
                label_a, label_b = _entry_label(args.first, entry_a), _entry_label(args.second, entry_b)
                _print_pair(entry_a, entry_b, result, label_a, label_b, args, stream)
            any_diff = True

        if unmatched_a or unmatched_b:
            any_diff = True

        if args.new_file:
            for i in unmatched_a:
                entry_a = entries_a[i]
                label_a = _entry_label(args.first, entry_a)
                label_b = f"{args.second}: (no entry)"
                _print_pair(entry_a, _EMPTY_ENTRY, None, label_a, label_b, args, stream)
            for j in unmatched_b:
                entry_b = entries_b[j]
                label_a = f"{args.first}: (no entry)"
                label_b = _entry_label(args.second, entry_b)
                _print_pair(_EMPTY_ENTRY, entry_b, None, label_a, label_b, args, stream)
        else:
            if args.verbose:
                print(f"\n=== Only in {args.first} ({len(unmatched_a)}) ===", file=stream)
            _report_unmatched(args.first, entries_a, unmatched_a, args, stream, side="a", color=args.color_enabled)
            if args.verbose:
                print(f"\n=== Only in {args.second} ({len(unmatched_b)}) ===", file=stream)
            _report_unmatched(args.second, entries_b, unmatched_b, args, stream, side="b", color=args.color_enabled)

        if args.verbose:
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

    sys.exit(1 if any_diff else 0)


if __name__ == "__main__":
    main()
