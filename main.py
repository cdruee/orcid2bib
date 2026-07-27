import time
import requests


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


def get_bibtex_from_doi(doi_string):
    """Attempts to fetch a clean BibTeX entry directly from the DOI foundation API."""
    # Clean up common DOI prefix formats if present
    doi = doi_string.replace("https://doi.org", "").replace(
        "http://doi.org", "")
    url = f"https://doi.org{doi}"
    headers = {"Accept": "text/bibliography; style=bibtex"}

    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            return response.text.strip()
    except Exception:
        pass
    return None


def fetch_work_details(orcid_id, put_code):
    """Fetches full details for a single work and extracts or resolves the BibTeX citation."""
    url = f"https://pub.orcid.org/v3.0/{orcid_id}/work/{put_code}"
    headers = {"Accept": "application/json"}

    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return None

    work_data = response.json()

    # Strategy 1: Check if ORCID already stores a native BibTeX citation for this work
    citation = work_data.get("citation")
    if citation and citation.get("citation-type", "").upper() == "BIBTEX":
        return citation.get("citation-value")

    # Strategy 2: If no native BibTeX exists, look for a DOI to resolve externally
    external_ids = work_data.get("external-ids", {}).get("external-id", [])
    for ext_id in external_ids:
        if ext_id.get("external-id-type") == "doi":
            doi_val = ext_id.get("external-id-value")
            if doi_val:
                bibtex = get_bibtex_from_doi(doi_val)
                if bibtex:
                    return bibtex

    # Strategy 3: Dynamic fallback if neither BibTeX nor DOI exists
    title = work_data.get("title", {}).get("title", {}).get("value",
                                                            "Unknown Title")
    year = work_data.get("publication-date", {})
    pub_year = "XXXX"
    if year and year.get("year"):
        pub_year = year["year"].get("value", "XXXX")

    fallback_key = f"orcid_{orcid_id}_{put_code}"
    fallback_bibtex = (
        f"@misc{{{fallback_key},\n"
        f"  title = {{{title}}},\n"
        f"  year = {{{pub_year}}},\n"
        f"  note = {{Retrieved via ORCID API put-code {put_code}}}\n"
        f"}}"
    )
    return fallback_bibtex


def main():
    # Replace with any valid public 16-digit ORCID iD
    target_orcid = "0000-0002-0103-4275"
    output_filename = f"{target_orcid}_publications.bib"

    put_codes = get_orcid_works(target_orcid)
    if not put_codes:
        print("[-] No works to process. Exiting.")
        return

    compiled_bibtex = []

    for idx, code in enumerate(put_codes, 1):
        print(
            f"[*] Processing item {idx}/{len(put_codes)} (Put-code: {code})...")
        bib_entry = fetch_work_details(target_orcid, code)
        if bib_entry:
            compiled_bibtex.append(bib_entry)
        # Polite API delay to respect rate limits
        time.sleep(0.2)

    # Save compilation to a local file
    with open(output_filename, "w", encoding="utf-8") as f:
        f.write("\n\n".join(compiled_bibtex))

    print(
        f"\n[+] Success! Your BibTeX file is saved to: '{output_filename}'")


if __name__ == "__main__":
    main()
