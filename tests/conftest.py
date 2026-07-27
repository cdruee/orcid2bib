# Copyright (C) 2026 Clemens Drüe <druee@uni-trier.de>
# SPDX-License-Identifier: EUPL-1.2
# Licensed under the EUPL

"""Shared test fixtures for orcid2bib's test suite."""

from unittest.mock import MagicMock


def make_response(status_code=200, json_data=None, text="", headers=None):
    """Builds a MagicMock standing in for a requests.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    resp.headers = headers or {}
    if json_data is not None:
        resp.json.return_value = json_data
    else:
        resp.json.side_effect = ValueError("no JSON body")
    return resp
