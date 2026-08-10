# Copyright (C) 2026 Clemens Drüe <druee@uni-trier.de>
# SPDX-License-Identifier: EUPL-1.2
# Licensed under the EUPL

import pytest

from orcid2bib import orcid2bib as cli


def test_build_parser_requires_orcid_id():
    parser = cli.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])


def test_build_parser_defaults():
    parser = cli.build_parser()
    args = parser.parse_args(["0000-0002-0103-4275"])
    assert args.orcid_id == "0000-0002-0103-4275"
    assert args.output is None
    assert args.delay == 0.2
    assert args.no_doi_lookup is False
    assert args.verbose is False


def test_build_parser_all_options():
    parser = cli.build_parser()
    args = parser.parse_args([
        "0000-0002-0103-4275",
        "-o", "out.bib",
        "--delay", "1.5",
        "-n",
        "-v",
    ])
    assert args.output == "out.bib"
    assert args.delay == 1.5
    assert args.no_doi_lookup is True
    assert args.verbose is True


def test_main_calls_run_with_parsed_args(monkeypatch):
    captured = {}

    def fake_run(orcid_id, output_filename=None, delay=0.2, doi_lookup=True, verbose=False):
        captured.update(
            orcid_id=orcid_id, output_filename=output_filename,
            delay=delay, doi_lookup=doi_lookup, verbose=verbose,
        )
        return "some_output.bib"

    monkeypatch.setattr(cli, "run", fake_run)
    cli.main(["0000-0002-0103-4275", "-n", "-v", "--delay", "0"])

    assert captured == {
        "orcid_id": "0000-0002-0103-4275",
        "output_filename": None,
        "delay": 0.0,
        "doi_lookup": False,  # -n negates the default True
        "verbose": True,
    }


def test_main_exits_nonzero_when_run_returns_none(monkeypatch):
    monkeypatch.setattr(cli, "run", lambda *a, **k: None)
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["0000-0002-0103-4275"])
    assert exc_info.value.code == 1
