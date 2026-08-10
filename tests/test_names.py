# Copyright (C) 2026 Clemens Drüe <druee@uni-trier.de>
# SPDX-License-Identifier: EUPL-1.2
# Licensed under the EUPL

import pytest

from orcid2bib import orcid as core


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Jane Q. Orcid", "Orcid, Jane Q."),
        ("John Smith", "Smith, John"),
        ("Ludwig van Beethoven", "van Beethoven, Ludwig"),
        ("Vincent van Gogh", "van Gogh, Vincent"),
        ("Martin Luther King Jr.", "King, Jr., Martin Luther"),
        ("Charles Emerson Winchester III", "Winchester, III, Charles Emerson"),
        ("Madonna", "Madonna"),
        ("Ursula K. Le Guin", "Le Guin, Ursula K."),
        ("Wernher von Braun", "von Braun, Wernher"),
        ("Smith, Jane", "Smith, Jane"),
        ("Smith, Jr., John", "Smith, Jr., John"),
        ("  Extra   Spaces   Here  ", "Here, Extra Spaces"),
        ("", ""),
    ],
)
def test_normalize_name(raw, expected):
    assert core._normalize_name(raw) == expected


def test_split_combined_credit_name_detects_concatenated_authors():
    combined = (
        "Kahlenborn, W., Porst, L., Voß, M., Hölscher, L., Undorf, S., Wolf, M., "
        "and Schönthaler, K., Crespi, A., Renner, K., Zebisch, M., Fritsch, U., "
        "and Schauser, I."
    )
    result = core._split_combined_credit_name(combined)
    assert result == [
        "Kahlenborn, W.",
        "Porst, L.",
        "Voß, M.",
        "Hölscher, L.",
        "Undorf, S.",
        "Wolf, M.",
        "Schönthaler, K.",
        "Crespi, A.",
        "Renner, K.",
        "Zebisch, M.",
        "Fritsch, U.",
        "Schauser, I.",
    ]


@pytest.mark.parametrize(
    "name",
    [
        "Smith, Jr., John",  # single name w/ suffix, no "and" -> not combined
        "Smith, Jane",  # plain single name
        "Sabine Undorf",  # no comma at all
        "Kahlenborn, W., Porst, L.",  # no "and" present
    ],
)
def test_split_combined_credit_name_leaves_single_names_alone(name):
    assert core._split_combined_credit_name(name) is None


def test_split_combined_credit_name_bails_on_pathological_and():
    # A legitimate single name that happens to contain " and " combined with
    # another name in the same field should not be garbled.
    name = "King, Jr., Martin Luther and Someone, Else"
    assert core._split_combined_credit_name(name) is None
