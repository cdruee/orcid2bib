# Copyright (C) 2026 Clemens Drüe <druee@uni-trier.de>
# SPDX-License-Identifier: EUPL-1.2
# Licensed under the EUPL

import pytest

from orcid2bib import _matching as matching


def entry(**fields):
    fields.setdefault("ENTRYTYPE", "article")
    return fields


def test_citekey_match_wins_outright():
    a = entry(ID="smith2020", title="Totally Different Title")
    b = entry(ID="smith2020", title="Something Else Entirely")
    result = matching.score_pair(a, b)
    assert result.tier == "citekey"
    assert result.total == 1.0


def test_doi_match_beats_conflicting_text_fields():
    a = entry(ID="a1", doi="10.1234/x", title="Foo", author="Smith, Jane")
    b = entry(ID="b2", doi="https://doi.org/10.1234/X", title="Bar", author="Doe, John")
    result = matching.score_pair(a, b)
    assert result.tier == "doi"
    assert result.total >= 0.9


def test_isbn_match():
    a = entry(ID="a1", isbn="978-0-13-468599-1")
    b = entry(ID="b2", isbn="9780134685991")
    result = matching.score_pair(a, b)
    assert result.tier == "isbn"


def test_heuristic_match_tolerates_typos_and_abbreviations():
    a = entry(
        ID="a1", author="Mueller, Hans", year="2018",
        title="A Talk About Robust Estimators",
        booktitle="Proceedings of ExampleConf 2018",
    )
    b = entry(
        ID="b2", author="M\u00fcller, H.", year="2018",
        title="A Talk about Robust Estimators",
        booktitle="Proc. of ExampleConf",
    )
    result = matching.score_pair(a, b)
    assert result.tier == "heuristic"
    assert result.total >= matching.MATCH_THRESHOLD


def test_clearly_different_works_score_low():
    a = entry(ID="a1", author="Smith, Jane", year="2020", title="Deep Learning for Climate")
    b = entry(ID="b2", author="Nguyen, Anh", year="1999", title="A Survey of Medieval Pottery")
    result = matching.score_pair(a, b)
    assert result.total < matching.POSSIBLE_THRESHOLD


def test_no_comparable_fields_gives_zero():
    a = entry(ID="a1")
    b = entry(ID="b2")
    result = matching.score_pair(a, b)
    assert result.tier == "none"
    assert result.total == 0.0


def test_match_entries_greedy_assignment_is_one_to_one():
    entries_a = [
        entry(ID="a1", doi="10.1/x"),
        entry(ID="a2", author="Smith, Jane", year="2020", title="Some Paper"),
    ]
    entries_b = [
        entry(ID="b1", doi="10.1/x"),
        entry(ID="b2", author="Smith, J.", year="2020", title="Some Paper"),
    ]
    matches, possibles, unmatched_a, unmatched_b = matching.match_entries(entries_a, entries_b)
    matched_pairs = {(i, j) for i, j, _ in matches}
    assert (0, 0) in matched_pairs
    assert (1, 1) in matched_pairs
    assert not unmatched_a
    assert not unmatched_b


def test_find_duplicates_groups_similar_entries_within_one_file():
    entries = [
        entry(ID="dup1", doi="10.1/x", title="Paper One"),
        entry(ID="dup2", doi="10.1/x", title="Paper One (copy)"),
        entry(ID="unique", author="Someone, Else", year="1999", title="Completely Different"),
    ]
    groups, _ = matching.find_duplicates(entries)
    assert groups == [[0, 1]]


@pytest.mark.parametrize(
    "name_a, name_b, expect_high",
    [
        ("Smith, Jane", "Smith, J.", True),
        ("Smith, Jane", "Smith, Jane", True),
        ("Smith, Jane", "Doe, John", False),
    ],
)
def test_name_similarity(name_a, name_b, expect_high):
    score = matching.name_similarity(name_a, name_b)
    if expect_high:
        assert score >= 0.8
    else:
        assert score < 0.6
