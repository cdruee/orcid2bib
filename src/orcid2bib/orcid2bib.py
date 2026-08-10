# Copyright (C) 2026 Clemens Drüe <druee@uni-trier.de>
# SPDX-License-Identifier: EUPL-1.2
# Licensed under the EUPL

import argparse
import sys

from .orcid import run


def build_parser():
    parser = argparse.ArgumentParser(
        prog="orcid2bib",
        description="Fetch all public works from an ORCID profile and compile them into a BibTeX file.",
    )
    parser.add_argument(
        "orcid_id",
        help="ORCID iD of the profile to fetch, e.g. 0000-0002-0103-4275",
    )
    parser.add_argument(
        "-o",
        "--output",
        metavar="FILE",
        help="Output .bib file path (default: <orcid_id>_publications.bib)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.2,
        metavar="SECONDS",
        help="Delay between ORCID API requests, in seconds (default: 0.2)",
    )
    parser.add_argument(
        "-n",
        "--no-doi-lookup",
        action="store_true",
        help=(
            "Disable resolving each work's DOI for extra metadata "
            "(author, journal, year, volume, number, pages, keywords). "
            "By default, DOI-resolved data overrides ORCID's own fields where available."
        ),
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print diagnostic details per work: detected entry type, DOI found, "
             "DOI-lookup requests/responses, and why fields were or weren't overridden.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.2.0",
    )
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    result = run(
        args.orcid_id,
        output_filename=args.output,
        delay=args.delay,
        doi_lookup=not args.no_doi_lookup,
        verbose=args.verbose,
    )
    if result is None:
        sys.exit(1)


if __name__ == "__main__":
    main()
