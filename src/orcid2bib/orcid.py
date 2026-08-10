# Copyright (C) 2026 Clemens Drüe <druee@uni-trier.de>
# SPDX-License-Identifier: EUPL-1.2
# Licensed under the EUPL

import re
import time

import requests

# Map ORCID work "type" values to standard (plain-LaTeX) BibTeX entry types.
# https://info.orcid.org/documentation/integration-guide/orcid-work-types/
_BIBTEX_TYPE_MAP = {
    "journal-article": "article",
    "magazine-article": "article",
    "newspaper-article": "article",
    "newsletter-article": "article",
    "review": "article",
    "book": "book",
    "edited-book": "book",
    "book-chapter": "incollection",
    "dictionary-entry": "incollection",
    "encyclopedia-entry": "incollection",
    "book-review": "incollection",
    "conference-paper": "inproceedings",
    "conference-abstract": "inproceedings",
    "conference-poster": "inproceedings",
    "conference-output": "inproceedings",
    "dissertation-thesis": "phdthesis",
    "report": "techreport",
    "standards-and-policy": "techreport",
    "standard": "techreport",
    "technical-standard": "techreport",
    "working-paper": "unpublished",
    "preprint": "unpublished",
    "manual": "manual",
}

# For entry types that have a natural "venue" field, map which BibTeX field
# the ORCID journal-title (or DOI container-title) should be written into.
_VENUE_FIELD_BY_TYPE = {
    "article": "journal",
    "inproceedings": "booktitle",
    "incollection": "booktitle",
}

# Crossref/CSL "type" values, as returned by DOI content-negotiation
# (https://api.crossref.org/types), mapped to BibTeX entry types. This is
# generally *more* reliable than ORCID's own self-reported work "type",
# which authors set by hand and often get wrong or inconsistent -- e.g.
# tagging a Copernicus discussion-journal article (which Crossref
# registers as a plain "journal-article") as a "preprint", or tagging a
# conference paper as "other"/"journal-article".
_CROSSREF_TYPE_MAP = {
    "journal-article": "article",
    "proceedings-article": "inproceedings",
    "book-chapter": "incollection",
    "book-section": "incollection",
    "book-part": "incollection",
    "book-track": "incollection",
    "reference-entry": "incollection",
    "book": "book",
    "monograph": "book",
    "edited-book": "book",
    "reference-book": "book",
    "report": "techreport",
    "report-series": "techreport",
    "standard": "techreport",
    "dissertation": "phdthesis",
}

# Crossref's "posted-content" type covers preprints, working papers, and
# similar things hosted on a repository rather than formally published.
# It doesn't map cleanly onto a classic BibTeX type -- there's no fixed
# venue, volume, or page range -- so "@misc" (no required fields) is a
# much safer fit than "@unpublished" (which formally requires a "note"
# field) or "@inproceedings" (which implies a real proceedings volume).
_CROSSREF_POSTED_CONTENT_TYPE = "misc"

# Safety net: some preprint/working-paper servers are registered with
# DataCite rather than Crossref, or can otherwise come back from DOI
# content negotiation tagged generically (e.g. "journal-article") even
# though the container is clearly a preprint repository. If the resolved
# container-title or publisher matches one of these, treat it as a
# preprint regardless of what the "type" field says.
_PREPRINT_SERVER_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\barxiv\b",
        r"\bbiorxiv\b",
        r"\bmedrxiv\b",
        r"\bchemrxiv\b",
        r"\begusphere\b",
        r"\bessoar\b",
        r"\bresearch\s*square\b",
        r"\bssrn\b",
        r"\bpreprints\.org\b",
        r"\bauthorea\b",
        r"\bpreprint\b",
    )
]


def _clean(value):
    """Collapse whitespace/newlines so a field renders as a single BibTeX line."""
    if value is None:
        return ""
    return " ".join(str(value).split())


def _vprint(verbose, msg):
    if verbose:
        print(f"    [v] {msg}")


def get_orcid_works(orcid_id):
    """Fetches the list of all public works summaries from an ORCID profile."""
    url = f"https://pub.orcid.org/v3.0/{orcid_id}/works"
    headers = {"Accept": "application/json"}

    print(f"[*] Fetching works list for ORCID: {orcid_id}...")
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        print(
            f"[-] Error fetching profile (Status Code: {response.status_code}). Check the ORCID iD.")
        return []

    data = response.json()
    put_codes = []

    # Extract unique put-codes for each work entry
    if "group" in data:
        for group in data["group"]:
            if "work-summary" in group and group["work-summary"]:
                # Grab the put-code from the first item in the group summary
                put_code = group["work-summary"][0].get("put-code")
                if put_code:
                    put_codes.append(put_code)

    print(f"[+] Found {len(put_codes)} public works.")
    return put_codes


def get_doi_metadata(doi_string, verbose=False):
    """Fetches CSL-JSON metadata for a DOI (via doi.org content negotiation).

    Used to enrich/override author, journal, year, volume, number, pages,
    and keywords beyond what ORCID itself stores.
    """
    doi = (
        doi_string.replace("https://doi.org/", "")
        .replace("http://doi.org/", "")
        .replace("https://doi.org", "")
        .replace("http://doi.org", "")
        .lstrip("/")
    )
    url = f"https://doi.org/{doi}"
    headers = {"Accept": "application/vnd.citationstyles.csl+json"}

    _vprint(verbose, f"Resolving DOI {doi} via {url}")
    try:
        response = requests.get(url, headers=headers, timeout=5)
    except Exception as exc:
        _vprint(verbose, f"DOI lookup failed: {exc!r}")
        return None

    _vprint(verbose, f"DOI lookup response: {response.status_code} {response.headers.get('Content-Type', '')}")
    if response.status_code != 200:
        _vprint(verbose, f"DOI lookup body (truncated): {response.text[:300]!r}")
        return None

    try:
        return response.json()
    except ValueError as exc:
        _vprint(verbose, f"DOI response was not valid JSON ({exc!r}); got: {response.text[:300]!r}")
        return None


def _extract_doi(work_data):
    external_ids = (work_data.get("external-ids") or {}).get("external-id") or []
    for ext_id in external_ids:
        if ext_id.get("external-id-type") == "doi":
            doi_val = ext_id.get("external-id-value")
            if doi_val:
                return doi_val
    return None


_NAME_SUFFIXES = {"jr", "jr.", "sr", "sr.", "ii", "iii", "iv", "v"}
_NAME_PARTICLES = {
    "van", "von", "der", "den", "de", "la", "le", "di", "da",
    "do", "dos", "du", "al", "el", "bin", "ibn", "st", "st.",
}


def _normalize_name(name):
    """Normalizes a single-string full name into BibTeX's 'Family, Given' form.

    Handles names already given as "Family, Given" (just tidies spacing),
    trailing generational suffixes (Jr., III, ...), and lowercase name
    particles (van, von, de, ...) that belong with the family name.
    This is a heuristic -- name splitting is inherently ambiguous -- so it
    won't be perfect for every name, but covers the common cases.
    """
    name = _clean(name)
    if not name:
        return ""

    if "," in name:
        # Already looks like "Family, Given" (or "Family, Suffix, Given") -- just tidy it.
        parts = [p.strip() for p in name.split(",")]
        return ", ".join(p for p in parts if p)

    tokens = name.split(" ")
    if len(tokens) == 1:
        return tokens[0]

    suffix = None
    if tokens[-1].lower().rstrip(".") in {s.rstrip(".") for s in _NAME_SUFFIXES}:
        if len(tokens) > 2:
            suffix = tokens.pop()

    # Merge trailing lowercase particle words ("van der Berg") into the family name.
    split_idx = len(tokens) - 1
    while split_idx > 0 and tokens[split_idx - 1].lower() in _NAME_PARTICLES:
        split_idx -= 1

    given = " ".join(tokens[:split_idx])
    family = " ".join(tokens[split_idx:])

    if suffix:
        return f"{family}, {suffix}, {given}"
    return f"{family}, {given}"


def _split_combined_credit_name(name, verbose=False):
    """Detects a known ORCID data-quality issue: a single contributor's
    'credit-name' field actually contains an entire citation-style author
    list crammed together, e.g.:

        "Kahlenborn, W., Porst, L., Voss, M., ..., and Schauser, I."

    instead of just that one contributor's name. If the string looks like
    an even number of alternating "Family, Given" pairs joined by commas
    (with "and" before the last one or two), split it into individual
    normalized names. Returns a list of names, or None if this doesn't look
    like a combined multi-author string (i.e. it's a normal single name).
    """
    if " and " not in f" {name.lower()} ":
        return None

    tokens = [t.strip() for t in name.split(",")]
    tokens = [t for t in tokens if t]

    # A single name with a suffix ("Smith, Jr., John") also has 3 comma
    # tokens but no "and" -- already excluded above. Anything with "and"
    # AND an even token count >= 4 is very likely a concatenated list
    # of "Family, Given" pairs rather than one person's name.
    if len(tokens) < 4 or len(tokens) % 2 != 0:
        return None

    pairs = []
    for i in range(0, len(tokens), 2):
        family = re.sub(r"^and\s+", "", tokens[i], flags=re.IGNORECASE).strip()
        given = re.sub(r"^and\s+", "", tokens[i + 1], flags=re.IGNORECASE).strip()
        if not family or not given:
            return None
        # Real "Family, Given" citation-list entries are short (a surname, an
        # initial or short first name). If any piece runs long, this is more
        # likely a single name with an "and" caught up in it by coincidence
        # than a genuine concatenated author list -- bail out to be safe.
        if len(family.split()) > 3 or len(given.split()) > 3:
            return None
        pairs.append(f"{family}, {given}")

    _vprint(verbose, f"credit-name looks like {len(pairs)} concatenated authors, not one -- splitting it")
    return pairs


def _extract_orcid_authors(work_data, verbose=False):
    """Builds a BibTeX 'and'-joined author string from ORCID contributor info."""
    contributors = (work_data.get("contributors") or {}).get("contributor") or []
    names = []
    for contributor in contributors:
        attrs = contributor.get("contributor-attributes") or {}
        role = (attrs.get("contributor-role") or "").lower()
        # Only pull in authors; skip explicitly-tagged non-author roles (e.g. editor).
        if role and role != "author":
            continue
        credit_name = (contributor.get("credit-name") or {}).get("value")
        if not credit_name:
            continue

        combined = _split_combined_credit_name(credit_name, verbose=verbose)
        if combined:
            names.extend(_normalize_name(n) for n in combined)
        else:
            names.append(_normalize_name(credit_name))
    return " and ".join(names)


def _format_csl_authors(csl_authors):
    """Formats a CSL-JSON author list as 'Family, Given and Family2, Given2'."""
    if not csl_authors:
        return ""
    names = []
    for author in csl_authors:
        family = _clean(author.get("family"))
        given = _clean(author.get("given"))
        if family and given:
            names.append(f"{family}, {given}")
        elif family:
            names.append(family)
        elif given:
            names.append(given)
        elif author.get("literal"):
            names.append(_normalize_name(author["literal"]))
    return " and ".join(names)


def _extract_csl_year(meta):
    for key in ("issued", "published-print", "published-online", "published"):
        date_info = meta.get(key)
        if date_info and date_info.get("date-parts"):
            parts = date_info["date-parts"]
            if parts and parts[0]:
                return str(parts[0][0])
    return ""


def _extract_orcid_year(work_data):
    pub_date = work_data.get("publication-date") or {}
    year_block = pub_date.get("year")
    if year_block:
        return _clean(year_block.get("value")) or ""
    return ""


def _format_page_range(pages):
    """Normalizes a page range to BibTeX's 'first--last' (double-dash) form.

    Sphinx's 'sphinxcontrib-bibtex' (and other strict BibTeX consumers) only
    recognize a page *range* when it's separated by a double dash; a single
    hyphen, en dash, or em dash (as DOI/Crossref metadata often uses) isn't
    picked up. A single page number (no range) is left untouched.
    """
    pages = _clean(pages)
    if not pages:
        return pages
    match = re.match(r"^(\S+?)\s*[-\u2010-\u2015]+\s*(\S+)$", pages)
    if match:
        first, last = match.group(1), match.group(2)
        return f"{first}--{last}"
    return pages


def _guess_entry_type(work_data):
    work_type = work_data.get("type") or ""
    return _BIBTEX_TYPE_MAP.get(work_type, "misc")


def _guess_entry_type_from_doi_meta(meta, verbose=False):
    """Guesses a BibTeX entry type from DOI-resolved CSL-JSON metadata.

    Uses the Crossref/CSL 'type' (and, for posted content, 'subtype')
    field, which reflects how the work was actually registered, rather
    than ORCID's self-reported work type. Returns None if the metadata
    doesn't give a confident answer, so the caller can fall back to the
    ORCID-based guess instead.
    """
    if not meta:
        return None

    csl_type = (meta.get("type") or "").lower()

    if csl_type == "posted-content":
        subtype = (meta.get("subtype") or "").lower()
        _vprint(
            verbose,
            f"DOI type 'posted-content' (subtype '{subtype or '?'}') "
            f"-> preprint -> '@{_CROSSREF_POSTED_CONTENT_TYPE}'",
        )
        return _CROSSREF_POSTED_CONTENT_TYPE

    mapped = _CROSSREF_TYPE_MAP.get(csl_type)
    if mapped:
        _vprint(verbose, f"DOI type '{csl_type}' -> '@{mapped}'")
        return mapped

    # Safety net: container/publisher looks like a known preprint server,
    # even though the 'type' field itself didn't say 'posted-content'.
    container_title = meta.get("container-title")
    if isinstance(container_title, list):
        container_title = container_title[0] if container_title else None
    publisher = meta.get("publisher")
    haystack = " ".join(str(x) for x in (container_title, publisher) if x)
    if haystack and any(p.search(haystack) for p in _PREPRINT_SERVER_PATTERNS):
        _vprint(
            verbose,
            f"DOI type '{csl_type or '?'}' but container/publisher "
            f"'{haystack}' looks like a preprint server -> "
            f"'@{_CROSSREF_POSTED_CONTENT_TYPE}'",
        )
        return _CROSSREF_POSTED_CONTENT_TYPE

    if csl_type:
        _vprint(
            verbose,
            f"DOI type '{csl_type}' has no confident BibTeX mapping -- "
            f"keeping ORCID-based guess",
        )
    return None


def build_bibtex_entry(orcid_id, put_code, work_data, use_doi_lookup=True, verbose=False):
    """Builds a BibTeX entry from an ORCID work record, optionally enriched via DOI lookup."""
    title_block = work_data.get("title") or {}
    inner_title = title_block.get("title") or {}
    title = _clean(inner_title.get("value")) or "Unknown Title"

    doi = _extract_doi(work_data)
    entry_type = _guess_entry_type(work_data)
    _vprint(verbose, f"Work type '{work_data.get('type')}' -> entry type '@{entry_type}'")
    _vprint(verbose, f"DOI found on record: {doi!r}")

    authors = _extract_orcid_authors(work_data, verbose=verbose)
    journal = _clean((work_data.get("journal-title") or {}).get("value"))
    year = _extract_orcid_year(work_data)
    volume = number = pages = keywords = ""

    if not doi:
        _vprint(verbose, "No DOI on this work -- skipping DOI lookup, using ORCID data only.")
    elif not use_doi_lookup:
        _vprint(verbose, "DOI lookup disabled (--no-doi-lookup) -- using ORCID data only.")

    if doi and use_doi_lookup:
        meta = get_doi_metadata(doi, verbose=verbose)
        if not meta:
            _vprint(verbose, "DOI lookup returned no usable metadata -- keeping ORCID-sourced fields.")
        if meta:
            _vprint(verbose, "DOI metadata retrieved -- overriding fields where present.")

            # The DOI's own registered type is generally a more reliable
            # signal for the BibTeX entry type than ORCID's self-reported
            # work type (see _guess_entry_type_from_doi_meta docstring).
            doi_entry_type = _guess_entry_type_from_doi_meta(meta, verbose=verbose)
            if doi_entry_type and doi_entry_type != entry_type:
                _vprint(
                    verbose,
                    f"Overriding entry type '@{entry_type}' (from ORCID) "
                    f"with '@{doi_entry_type}' (from DOI)",
                )
                entry_type = doi_entry_type
            elif doi_entry_type:
                _vprint(verbose, f"DOI-derived entry type '@{doi_entry_type}' agrees with ORCID-based guess")

            # DOI-resolved metadata overrides ORCID's own info where available.
            csl_authors = _format_csl_authors(meta.get("author"))
            if csl_authors:
                authors = csl_authors

            container_title = meta.get("container-title")
            if isinstance(container_title, list):
                container_title = container_title[0] if container_title else None
            if container_title:
                journal = _clean(container_title)

            csl_year = _extract_csl_year(meta)
            if csl_year:
                year = csl_year

            if meta.get("volume"):
                volume = _clean(meta["volume"])
            if meta.get("issue"):
                number = _clean(meta["issue"])
            if meta.get("page"):
                pages = _format_page_range(_clean(meta["page"]))

            subject = meta.get("subject")
            if subject:
                keywords = ", ".join(_clean(s) for s in subject) if isinstance(subject, list) else _clean(subject)

    venue_field = _VENUE_FIELD_BY_TYPE.get(entry_type)

    fields = []
    if authors:
        fields.append(("author", authors))
    fields.append(("title", title))
    if venue_field and journal:
        fields.append((venue_field, journal))
    elif entry_type == "misc" and journal:
        # @misc has no natural venue field, but the container/journal
        # title (e.g. "EGUsphere", "arXiv") is still useful context.
        fields.append(("note", journal))
    if year:
        fields.append(("year", year))
    if volume:
        fields.append(("volume", volume))
    if number:
        fields.append(("number", number))
    if pages:
        fields.append(("pages", pages))
    if doi:
        fields.append(("doi", doi))
    if keywords:
        fields.append(("keywords", keywords))
    fields.append(("comment", f"Retrieved via ORCID API put-code {put_code}"))

    key = f"orcid_{orcid_id}_{put_code}"
    body = ",\n".join(f"  {name} = {{{value}}}" for name, value in fields)
    return f"@{entry_type}{{{key},\n{body}\n}}"


def fetch_work_details(orcid_id, put_code, use_doi_lookup=True, verbose=False):
    """Fetches full details for a single work and builds a BibTeX entry for it."""
    url = f"https://pub.orcid.org/v3.0/{orcid_id}/work/{put_code}"
    headers = {"Accept": "application/json"}

    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        _vprint(verbose, f"Failed to fetch work {put_code} (status {response.status_code})")
        return None

    work_data = response.json()
    return build_bibtex_entry(
        orcid_id, put_code, work_data, use_doi_lookup=use_doi_lookup, verbose=verbose
    )


def run(orcid_id, output_filename=None, delay=0.2, doi_lookup=True, verbose=False):
    """Fetches all public works for an ORCID iD and writes a compiled BibTeX file.

    Returns the output filename on success, or None if there was nothing to write.
    """
    if output_filename is None:
        output_filename = f"{orcid_id}_publications.bib"

    put_codes = get_orcid_works(orcid_id)
    if not put_codes:
        print("[-] No works to process. Exiting.")
        return None

    compiled_bibtex = []

    for idx, code in enumerate(put_codes, 1):
        print(
            f"[*] Processing item {idx}/{len(put_codes)} (Put-code: {code})...")
        bib_entry = fetch_work_details(orcid_id, code, use_doi_lookup=doi_lookup, verbose=verbose)
        if bib_entry:
            compiled_bibtex.append(bib_entry)
        # Polite API delay to respect rate limits
        if delay > 0:
            time.sleep(delay)

    with open(output_filename, "w", encoding="utf-8") as f:
        f.write("\n\n".join(compiled_bibtex))

    print(f"\n[+] Success! Your BibTeX file is saved to: '{output_filename}'")
    return output_filename
