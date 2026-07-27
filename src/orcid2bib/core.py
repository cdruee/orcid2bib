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


def _clean(value):
    """Collapse whitespace/newlines so a field renders as a single BibTeX line."""
    if value is None:
        return ""
    return " ".join(str(value).split())


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


def get_doi_metadata(doi_string):
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

    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
    return None


def _extract_doi(work_data):
    external_ids = (work_data.get("external-ids") or {}).get("external-id") or []
    for ext_id in external_ids:
        if ext_id.get("external-id-type") == "doi":
            doi_val = ext_id.get("external-id-value")
            if doi_val:
                return doi_val
    return None


def _extract_orcid_authors(work_data):
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
        if credit_name:
            names.append(_clean(credit_name))
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
            names.append(_clean(author["literal"]))
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


def _guess_entry_type(work_data):
    work_type = work_data.get("type") or ""
    return _BIBTEX_TYPE_MAP.get(work_type, "misc")


def build_bibtex_entry(orcid_id, put_code, work_data, use_doi_lookup=True):
    """Builds a BibTeX entry from an ORCID work record, optionally enriched via DOI lookup."""
    title_block = work_data.get("title") or {}
    inner_title = title_block.get("title") or {}
    title = _clean(inner_title.get("value")) or "Unknown Title"

    doi = _extract_doi(work_data)
    entry_type = _guess_entry_type(work_data)

    authors = _extract_orcid_authors(work_data)
    journal = _clean((work_data.get("journal-title") or {}).get("value"))
    year = _extract_orcid_year(work_data)
    volume = number = pages = keywords = ""

    if doi and use_doi_lookup:
        meta = get_doi_metadata(doi)
        if meta:
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
                pages = _clean(meta["page"])

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
    fields.append(("note", f"Retrieved via ORCID API put-code {put_code}"))

    key = f"orcid_{orcid_id}_{put_code}"
    body = ",\n".join(f"  {name} = {{{value}}}" for name, value in fields)
    return f"@{entry_type}{{{key},\n{body}\n}}"


def fetch_work_details(orcid_id, put_code, use_doi_lookup=True):
    """Fetches full details for a single work and builds a BibTeX entry for it."""
    url = f"https://pub.orcid.org/v3.0/{orcid_id}/work/{put_code}"
    headers = {"Accept": "application/json"}

    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return None

    work_data = response.json()
    return build_bibtex_entry(orcid_id, put_code, work_data, use_doi_lookup=use_doi_lookup)


def run(orcid_id, output_filename=None, delay=0.2, doi_lookup=True):
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
        bib_entry = fetch_work_details(orcid_id, code, use_doi_lookup=doi_lookup)
        if bib_entry:
            compiled_bibtex.append(bib_entry)
        # Polite API delay to respect rate limits
        if delay > 0:
            time.sleep(delay)

    with open(output_filename, "w", encoding="utf-8") as f:
        f.write("\n\n".join(compiled_bibtex))

    print(f"\n[+] Success! Your BibTeX file is saved to: '{output_filename}'")
    return output_filename
