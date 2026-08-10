# Copyright (C) 2026 Clemens Drüe <druee@uni-trier.de>
# SPDX-License-Identifier: EUPL-1.2
# Licensed under the EUPL

import pytest

from orcid2bib import orcid as core
from conftest import make_response


# --------------------------------------------------------------------------
# Entry-type guessing
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "work_type, expected",
    [
        ("journal-article", "article"),
        ("conference-paper", "inproceedings"),
        ("book-chapter", "incollection"),
        ("dissertation-thesis", "phdthesis"),
        ("preprint", "unpublished"),
        ("working-paper", "unpublished"),
        ("report", "techreport"),
        ("website", "misc"),  # unrecognized -> misc fallback
        ("", "misc"),
    ],
)
def test_guess_entry_type(work_type, expected):
    assert core._guess_entry_type({"type": work_type}) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("100-110", "100--110"),
        ("100--110", "100--110"),  # already correct, left alone
        ("100\u2013110", "100--110"),  # en dash, e.g. from Crossref
        ("100\u2014110", "100--110"),  # em dash
        ("100 - 110", "100--110"),  # spaced hyphen
        ("e12345", "e12345"),  # article number, not a range -> untouched
        ("", ""),
        (None, ""),
    ],
)
def test_format_page_range(raw, expected):
    assert core._format_page_range(raw) == expected


# --------------------------------------------------------------------------
# build_bibtex_entry
# --------------------------------------------------------------------------

def test_build_bibtex_entry_journal_article_no_doi_lookup():
    work = {
        "type": "journal-article",
        "title": {"title": {"value": "Deep Learning for X"}},
        "journal-title": {"value": "ORCID Journal Name"},
        "publication-date": {"year": {"value": "2019"}},
        "external-ids": {"external-id": [
            {"external-id-type": "doi", "external-id-value": "10.1234/example.doi"}
        ]},
        "contributors": {"contributor": [
            {"credit-name": {"value": "Jane Q. Orcid"},
             "contributor-attributes": {"contributor-role": "author"}},
            {"credit-name": {"value": "Some Editor"},
             "contributor-attributes": {"contributor-role": "editor"}},
        ]},
    }
    entry = core.build_bibtex_entry("0000-0000-0000-0001", 111, work, use_doi_lookup=False)

    assert entry.startswith("@article{orcid_0000-0000-0000-0001_111,")
    assert "author = {Orcid, Jane Q.}" in entry  # editor excluded, name normalized
    assert "title = {Deep Learning for X}" in entry
    assert "journal = {ORCID Journal Name}" in entry
    assert "year = {2019}" in entry
    assert "doi = {10.1234/example.doi}" in entry
    assert "comment = {Retrieved via ORCID API put-code 111}" in entry


def test_build_bibtex_entry_doi_lookup_overrides_fields(monkeypatch):
    work = {
        "type": "journal-article",
        "title": {"title": {"value": "Deep Learning for X"}},
        "journal-title": {"value": "ORCID Journal Name"},
        "publication-date": {"year": {"value": "2019"}},
        "external-ids": {"external-id": [
            {"external-id-type": "doi", "external-id-value": "10.1234/example.doi"}
        ]},
        "contributors": {"contributor": []},
    }
    csl_meta = {
        "author": [{"family": "Smith", "given": "Jane"}, {"family": "Doe", "given": "John"}],
        "container-title": "Journal of Real Metadata",
        "issued": {"date-parts": [[2020, 3]]},
        "volume": "12",
        "issue": "4",
        "page": "100-110",
        "subject": ["machine learning", "nlp"],
    }
    monkeypatch.setattr(core, "get_doi_metadata", lambda doi, verbose=False: csl_meta)

    entry = core.build_bibtex_entry("0000-0000-0000-0001", 111, work, use_doi_lookup=True)

    assert "author = {Smith, Jane and Doe, John}" in entry
    assert "journal = {Journal of Real Metadata}" in entry
    assert "year = {2020}" in entry
    assert "volume = {12}" in entry
    assert "number = {4}" in entry
    assert "pages = {100--110}" in entry
    assert "keywords = {machine learning, nlp}" in entry


def test_build_bibtex_entry_conference_paper_uses_booktitle():
    work = {
        "type": "conference-paper",
        "title": {"title": {"value": "A Talk About Things"}},
        "journal-title": {"value": "Proceedings of ExampleConf"},
        "publication-date": {"year": {"value": "2021"}},
        "external-ids": {"external-id": None},
        "contributors": {"contributor": [
            {"credit-name": {"value": "Solo Author"}},
        ]},
    }
    entry = core.build_bibtex_entry("0000-0000-0000-0001", 222, work, use_doi_lookup=True)

    assert entry.startswith("@inproceedings{")
    assert "booktitle = {Proceedings of ExampleConf}" in entry
    assert "author = {Author, Solo}" in entry
    assert "doi" not in entry


def test_build_bibtex_entry_handles_null_fields_gracefully():
    # Reproduces the original crash: ORCID returning explicit nulls instead
    # of omitting keys.
    work = {
        "citation": None,
        "external-ids": {"external-id": None},
        "title": None,
        "publication-date": None,
        "contributors": None,
        "type": None,
    }
    entry = core.build_bibtex_entry("0000-0001-7026-080X", 154711005, work, use_doi_lookup=False)
    assert entry.startswith("@misc{")
    assert "title = {Unknown Title}" in entry


def test_build_bibtex_entry_splits_concatenated_credit_name():
    work = {
        "type": "report",
        "title": {"title": {"value": "Klimawirkungsund Risikoanalyse 2021"}},
        "publication-date": {"year": {"value": "2021"}},
        "external-ids": {"external-id": []},
        "contributors": {"contributor": [
            {"credit-name": {"value": "Sabine Undorf"},
             "contributor-attributes": {"contributor-role": "author"}},
            {"credit-name": {
                "value": "Kahlenborn, W., Porst, L., and Schauser, I."},
             "contributor-attributes": {"contributor-role": "author"}},
        ]},
    }
    entry = core.build_bibtex_entry("0000-0001-7026-080X", 154967113, work, use_doi_lookup=False)
    assert (
        "author = {Undorf, Sabine and Kahlenborn, W. and Porst, L. and Schauser, I.}"
        in entry
    )


# --------------------------------------------------------------------------
# get_orcid_works
# --------------------------------------------------------------------------

def test_get_orcid_works_success(monkeypatch):
    data = {
        "group": [
            {"work-summary": [{"put-code": 111}]},
            {"work-summary": [{"put-code": 222}]},
        ]
    }
    monkeypatch.setattr(core.requests, "get", lambda *a, **k: make_response(200, data))
    assert core.get_orcid_works("0000-0000-0000-0001") == [111, 222]


def test_get_orcid_works_error_status(monkeypatch):
    monkeypatch.setattr(core.requests, "get", lambda *a, **k: make_response(403))
    assert core.get_orcid_works("bad-id") == []


# --------------------------------------------------------------------------
# fetch_work_details
# --------------------------------------------------------------------------

def test_fetch_work_details_non_200_returns_none(monkeypatch):
    monkeypatch.setattr(core.requests, "get", lambda *a, **k: make_response(404))
    assert core.fetch_work_details("0000-0000-0000-0001", 999) is None


# --------------------------------------------------------------------------
# get_doi_metadata
# --------------------------------------------------------------------------

def test_get_doi_metadata_success(monkeypatch):
    csl = {"container-title": "Some Journal"}
    monkeypatch.setattr(core.requests, "get", lambda *a, **k: make_response(200, csl))
    assert core.get_doi_metadata("10.1234/x") == csl


def test_get_doi_metadata_non_200_returns_none(monkeypatch):
    monkeypatch.setattr(core.requests, "get", lambda *a, **k: make_response(404, text="Not Found"))
    assert core.get_doi_metadata("10.1234/x") is None


def test_get_doi_metadata_network_error_returns_none(monkeypatch):
    def raise_error(*a, **k):
        raise ConnectionError("simulated network failure")

    monkeypatch.setattr(core.requests, "get", raise_error)
    assert core.get_doi_metadata("10.1234/x") is None


# --------------------------------------------------------------------------
# run() end-to-end
# --------------------------------------------------------------------------

def test_run_writes_bibtex_file(monkeypatch, tmp_path):
    works_data = {"group": [{"work-summary": [{"put-code": 111}]}]}
    work_detail = {
        "type": "journal-article",
        "title": {"title": {"value": "A Paper"}},
        "publication-date": {"year": {"value": "2020"}},
        "external-ids": {"external-id": []},
        "contributors": {"contributor": []},
    }

    def fake_get(url, headers=None, timeout=None):
        if url.endswith("/works"):
            return make_response(200, works_data)
        return make_response(200, work_detail)

    monkeypatch.setattr(core.requests, "get", fake_get)

    out_file = tmp_path / "out.bib"
    result = core.run("0000-0000-0000-0001", output_filename=str(out_file), delay=0)

    assert result == str(out_file)
    content = out_file.read_text(encoding="utf-8")
    assert "@article{orcid_0000-0000-0000-0001_111," in content
    assert "title = {A Paper}" in content


def test_run_returns_none_when_no_works(monkeypatch):
    monkeypatch.setattr(core.requests, "get", lambda *a, **k: make_response(200, {"group": []}))
    assert core.run("0000-0000-0000-0001", delay=0) is None
