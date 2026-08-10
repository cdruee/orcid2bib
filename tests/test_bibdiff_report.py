# Copyright (C) 2026 Clemens Drüe <druee@uni-trier.de>
# SPDX-License-Identifier: EUPL-1.2
# Licensed under the EUPL

import pytest

from orcid2bib._compare import diff_entry_fields
from orcid2bib._parser import BibSyntaxError, load_bib_file
from orcid2bib._report import render_diff


def entry(**fields):
    fields.setdefault("ENTRYTYPE", "article")
    return fields


def test_diff_entry_fields_flags_changed_added_removed():
    a = entry(ID="a", title="Same Title", year="2020", pages="1-2")
    b = entry(ID="b", title="Same Title", year="2021", keywords="x, y")
    rows = {row[0]: row for row in diff_entry_fields(a, b)}
    assert rows["title"][3] == "same"
    assert rows["year"][3] == "changed"
    assert rows["pages"][3] == "removed"
    assert rows["keywords"][3] == "added"


def test_diff_entry_fields_flags_type_mismatch():
    a = entry(ID="a", ENTRYTYPE="article")
    b = entry(ID="b", ENTRYTYPE="misc")
    rows = {row[0]: row for row in diff_entry_fields(a, b)}
    assert rows["@type"][3] == "changed"


def test_render_diff_unified_style_shows_changes():
    a = entry(ID="a", title="Old Title", year="2020")
    b = entry(ID="b", title="New Title", year="2020")
    text = render_diff("first: a", a, "second: b", b, style="diff")
    assert "-  title = {Old Title}," in text
    assert "+  title = {New Title}," in text


def test_render_diff_side_by_side_marks_differences():
    a = entry(ID="a", title="Old Title")
    b = entry(ID="b", title="New Title")
    text = render_diff("first: a", a, "second: b", b, style="side-by-side")
    assert "*title" in text
    assert "Old Title" in text
    assert "New Title" in text


def test_render_diff_rejects_unknown_style():
    a, b = entry(ID="a"), entry(ID="b")
    with pytest.raises(ValueError):
        render_diff("a", a, "b", b, style="not-a-style")


def test_load_bib_file_parses_valid_file(tmp_path):
    bib_path = tmp_path / "valid.bib"
    bib_path.write_text(
        "@article{key2020,\n"
        "  author = {Smith, Jane},\n"
        "  title = {A Paper},\n"
        "  year = {2020}\n"
        "}\n",
        encoding="utf-8",
    )
    entries = load_bib_file(str(bib_path))
    assert len(entries) == 1
    assert entries[0]["ID"] == "key2020"
    assert entries[0]["title"] == "A Paper"


def test_load_bib_file_detects_unbalanced_braces(tmp_path):
    bib_path = tmp_path / "broken.bib"
    bib_path.write_text(
        "@article{key2020,\n"
        "  title = {Missing Closing Brace,\n"
        "  year = {2020}\n"
        "}\n",
        encoding="utf-8",
    )
    with pytest.raises(BibSyntaxError):
        load_bib_file(str(bib_path))


def test_load_bib_file_missing_file_raises(tmp_path):
    with pytest.raises(BibSyntaxError):
        load_bib_file(str(tmp_path / "does_not_exist.bib"))
