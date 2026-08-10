# Copyright (C) 2026 Clemens Drüe <druee@uni-trier.de>
# SPDX-License-Identifier: EUPL-1.2
# Licensed under the EUPL

"""Scoring, matching, and duplicate-detection logic for bibdiff.

Matching procedure (per entry pair), highest-confidence signal first:
  1. Identical citation key -> certain match.
  2. Identical (normalized) DOI, then ISBN -> certain match.
  3. A weighted, typo-tolerant composite of first author / year / title
     and journal (or booktitle) / pages -- whichever fields are available.
"""

import difflib
import re
from dataclasses import dataclass, field
from typing import Dict, Tuple

from ._names import given_initial, parse_name, split_bibtex_authors
from ._textutils import normalize_loose, significant_words

MATCH_THRESHOLD = 0.75
POSSIBLE_THRESHOLD = 0.55


@dataclass
class ScoreResult:
    total: float
    tier: str  # "citekey" | "doi" | "isbn" | "heuristic" | "none"
    breakdown: Dict[str, Tuple[float, float]] = field(default_factory=dict)  # name -> (score, weight)


def normalize_doi(doi):
    if not doi:
        return ""
    text = str(doi).strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if text.startswith(prefix):
            text = text[len(prefix):]
    return text.strip()


def normalize_isbn(isbn):
    if not isbn:
        return ""
    return re.sub(r"[\s-]", "", str(isbn)).lower()


def seq_ratio(a, b):
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def name_similarity(name_a, name_b):
    """Typo-/abbreviation-tolerant similarity between two BibTeX author names."""
    fam_a, giv_a = parse_name(name_a)
    fam_b, giv_b = parse_name(name_b)
    fam_score = seq_ratio(normalize_loose(fam_a), normalize_loose(fam_b))
    if fam_score < 0.6:
        return fam_score  # surnames clearly differ -> don't let given-name save it

    ia, ib = given_initial(giv_a), given_initial(giv_b)
    if not giv_a or not giv_b:
        given_score = 0.5  # one side has no given name on record -- stay neutral
    elif ia != ib:
        given_score = 0.0
    elif len(normalize_loose(giv_a)) <= 2 or len(normalize_loose(giv_b)) <= 2:
        given_score = 1.0  # one side is just an initial ("J.") and initials match
    else:
        given_score = seq_ratio(normalize_loose(giv_a), normalize_loose(giv_b))

    return 0.75 * fam_score + 0.25 * given_score


def first_author(entry):
    authors = split_bibtex_authors(entry.get("author", ""))
    return authors[0] if authors else ""


def title_similarity(title_a, title_b):
    norm_a, norm_b = normalize_loose(title_a), normalize_loose(title_b)
    if not norm_a or not norm_b:
        return 0.0
    full = seq_ratio(norm_a, norm_b)
    first_words_a = " ".join(norm_a.split()[:8])
    first_words_b = " ".join(norm_b.split()[:8])
    first_words = seq_ratio(first_words_a, first_words_b)
    return max(full, first_words)


def venue_similarity(venue_a, venue_b):
    """Tolerant of journal-name abbreviations (e.g. 'J. Am. Chem. Soc.' vs full name)."""
    norm_a, norm_b = normalize_loose(venue_a), normalize_loose(venue_b)
    if not norm_a or not norm_b:
        return 0.0
    full = seq_ratio(norm_a, norm_b)
    words_a, words_b = significant_words(venue_a), significant_words(venue_b)
    if not words_a or not words_b:
        return full
    shorter, longer = (words_a, words_b) if len(words_a) <= len(words_b) else (words_b, words_a)
    if len(shorter) <= max(1, len(longer) // 2):
        acronym = "".join(w[0] for w in longer)
        candidate = "".join(shorter)
        return max(full, seq_ratio(acronym, candidate))
    return full


def year_similarity(year_a, year_b):
    try:
        ya, yb = int(str(year_a)[:4]), int(str(year_b)[:4])
    except ValueError:
        return seq_ratio(str(year_a), str(year_b))
    diff = abs(ya - yb)
    if diff == 0:
        return 1.0
    if diff == 1:
        return 0.5  # tolerate off-by-one (online-first vs print year, etc.)
    return 0.0


def pages_similarity(pages_a, pages_b):
    start_a = re.sub(r"[^0-9]", "", str(pages_a).split("-")[0])
    start_b = re.sub(r"[^0-9]", "", str(pages_b).split("-")[0])
    if start_a and start_a == start_b:
        return 1.0
    return seq_ratio(normalize_loose(pages_a), normalize_loose(pages_b))


def score_pair(entry_a, entry_b):
    """Scores how likely two BibTeX entries are the same work. See module docstring."""
    id_a, id_b = (entry_a.get("ID") or "").strip(), (entry_b.get("ID") or "").strip()
    if id_a and id_b and id_a.lower() == id_b.lower():
        return ScoreResult(total=1.0, tier="citekey", breakdown={"citekey": (1.0, 1.0)})

    doi_a, doi_b = normalize_doi(entry_a.get("doi")), normalize_doi(entry_b.get("doi"))
    if doi_a and doi_b and doi_a == doi_b:
        return ScoreResult(total=0.98, tier="doi", breakdown={"doi": (1.0, 1.0)})

    isbn_a, isbn_b = normalize_isbn(entry_a.get("isbn")), normalize_isbn(entry_b.get("isbn"))
    if isbn_a and isbn_b and isbn_a == isbn_b:
        return ScoreResult(total=0.95, tier="isbn", breakdown={"isbn": (1.0, 1.0)})

    components, weights = {}, {}

    auth_a, auth_b = first_author(entry_a), first_author(entry_b)
    if auth_a and auth_b:
        components["author"] = name_similarity(auth_a, auth_b)
        weights["author"] = 0.30

    year_a, year_b = (entry_a.get("year") or "").strip(), (entry_b.get("year") or "").strip()
    if year_a and year_b:
        components["year"] = year_similarity(year_a, year_b)
        weights["year"] = 0.15

    title_a, title_b = entry_a.get("title") or "", entry_b.get("title") or ""
    if title_a and title_b:
        components["title"] = title_similarity(title_a, title_b)
        weights["title"] = 0.30

    venue_a = entry_a.get("journal") or entry_a.get("booktitle") or ""
    venue_b = entry_b.get("journal") or entry_b.get("booktitle") or ""
    if venue_a and venue_b:
        components["venue"] = venue_similarity(venue_a, venue_b)
        weights["venue"] = 0.15

    pages_a, pages_b = (entry_a.get("pages") or "").strip(), (entry_b.get("pages") or "").strip()
    if pages_a and pages_b:
        components["pages"] = pages_similarity(pages_a, pages_b)
        weights["pages"] = 0.10

    if not weights:
        return ScoreResult(total=0.0, tier="none", breakdown={})

    total_weight = sum(weights.values())
    total = sum(components[k] * weights[k] for k in components) / total_weight
    breakdown = {k: (components[k], weights[k]) for k in components}
    return ScoreResult(total=total, tier="heuristic", breakdown=breakdown)


def classify(score_result, match_threshold=MATCH_THRESHOLD, possible_threshold=POSSIBLE_THRESHOLD):
    if score_result.tier in ("citekey", "doi", "isbn"):
        return "match"
    if score_result.total >= match_threshold:
        return "match"
    if score_result.total >= possible_threshold:
        return "possible"
    return "none"


def match_entries(entries_a, entries_b, match_threshold=MATCH_THRESHOLD,
                   possible_threshold=POSSIBLE_THRESHOLD, debug_sink=None):
    """Greedy best-score-first 1:1 matching between two entry lists.

    Returns (matches, possibles, unmatched_a, unmatched_b); matches/possibles
    are lists of (index_a, index_b, ScoreResult).
    """
    candidates = []
    for i, entry_a in enumerate(entries_a):
        for j, entry_b in enumerate(entries_b):
            result = score_pair(entry_a, entry_b)
            if debug_sink is not None:
                debug_sink(i, j, result)
            if result.tier in ("citekey", "doi", "isbn") or result.total >= possible_threshold:
                candidates.append((result.total, i, j, result))

    candidates.sort(key=lambda c: c[0], reverse=True)

    used_a, used_b = set(), set()
    matches, possibles = [], []
    for _, i, j, result in candidates:
        if i in used_a or j in used_b:
            continue
        used_a.add(i)
        used_b.add(j)
        cls = classify(result, match_threshold, possible_threshold)
        if cls == "match":
            matches.append((i, j, result))
        elif cls == "possible":
            possibles.append((i, j, result))

    unmatched_a = [i for i in range(len(entries_a)) if i not in used_a]
    unmatched_b = [j for j in range(len(entries_b)) if j not in used_b]
    return matches, possibles, unmatched_a, unmatched_b


def find_duplicates(entries, threshold=MATCH_THRESHOLD, debug_sink=None):
    """Finds clusters of likely-duplicate entries within a single list (union-find)."""
    n = len(entries)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[ry] = rx

    pair_scores = {}
    for i in range(n):
        for j in range(i + 1, n):
            result = score_pair(entries[i], entries[j])
            if debug_sink is not None:
                debug_sink(i, j, result)
            if result.tier in ("citekey", "doi", "isbn") or result.total >= threshold:
                union(i, j)
                pair_scores[(i, j)] = result

    clusters = {}
    for i in range(n):
        clusters.setdefault(find(i), []).append(i)
    groups = [sorted(members) for members in clusters.values() if len(members) > 1]
    return groups, pair_scores
