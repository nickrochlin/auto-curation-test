"""
Fetch a published dataset from Borealis and save a review package to inbox/.

This script only READS from Borealis. It never changes anything there.

What ends up in inbox/:
  - the dataset's existing metadata and file list
  - the full text of READMEs and documentation (.txt .md .docx .pdf)
  - a profile of EVERY data file, built by reading every row
  - README checks: which files and variables the README never mentions

Downloaded files are kept in downloads/ so you can open them yourself.

Usage (from inside the curation-skills folder):
    python fetch_borealis.py doi:10.5683/SP3/XXXXXX
    python fetch_borealis.py https://doi.org/10.5683/SP3/XXXXXX
    python fetch_borealis.py doi:10.5683/SP3/XXXXXX --max-mb 1000
    python fetch_borealis.py doi:10.5683/SP3/XXXXXX --server https://demo.borealisdata.ca

Public datasets need no API token. For a draft or restricted dataset you have
access to, set an environment variable called BOREALIS_API_TOKEN first.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path

from package import DATA_TYPES, DEFAULT_BUDGET_TOKENS, build_package
from read_documents import DOC_TYPES

BASE = Path(__file__).resolve().parent
INBOX = BASE / "inbox"
DOWNLOADS = BASE / "downloads"


def clean_doi(value: str) -> str:
    value = value.strip()
    value = re.sub(r"^https?://(dx\.)?doi\.org/", "", value)
    value = value.replace("persistentId=", "")
    if not value.startswith("doi:"):
        value = "doi:" + value
    return value


def open_url(url: str, token: str | None):
    request = urllib.request.Request(url, headers={"User-Agent": "curation-skills"})
    if token:
        request.add_header("X-Dataverse-key", token)
    return urllib.request.urlopen(request, timeout=120)


def download(url: str, token: str | None, dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open_url(url, token) as response, dest.open("wb") as out:
        shutil.copyfileobj(response, out)


def field_value(field):
    """Turn a Dataverse metadata field into plain text."""
    value = field.get("value")
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, dict):
                parts.append("; ".join(str(sub.get("value")) for sub in item.values() if isinstance(sub, dict)))
            else:
                parts.append(str(item))
        return " | ".join(parts)
    if isinstance(value, dict):
        return "; ".join(str(sub.get("value")) for sub in value.values() if isinstance(sub, dict))
    return str(value)


def main():
    parser = argparse.ArgumentParser(description="Fetch a Borealis dataset into inbox/.")
    parser.add_argument("doi", help="The dataset DOI, e.g. doi:10.5683/SP3/ABC123")
    parser.add_argument("--server", default="https://borealisdata.ca", help="Borealis server address")
    parser.add_argument("--max-mb", type=float, default=500, help="Skip files larger than this (default 500 MB)")
    parser.add_argument("--budget-tokens", type=int, default=DEFAULT_BUDGET_TOKENS,
                        help=f"Target package size (default {DEFAULT_BUDGET_TOKENS}, which suits the default "
                             "16,384 window; use about 20000 with --ctx 32768)")
    args = parser.parse_args()

    server = args.server.rstrip("/")
    doi = clean_doi(args.doi)
    slug = re.sub(r"[^A-Za-z0-9]+", "_", doi.replace("doi:", "")).strip("_")
    token = os.environ.get("BOREALIS_API_TOKEN")

    print(f"Fetching {doi} from {server} ...")
    try:
        with open_url(f"{server}/api/datasets/:persistentId/?persistentId={doi}", token) as r:
            version = json.loads(r.read())["data"]["latestVersion"]
    except urllib.error.HTTPError as e:
        sys.exit(f"Borealis said {e.code}. Check the DOI, and that the dataset is public "
                 f"(or that your API token has access).")
    except urllib.error.URLError as e:
        sys.exit(f"Could not reach {server}: {e.reason}")

    header = [f"Dataset DOI: {doi}", f"Source: {server}", "", "== EXISTING METADATA =="]
    for block in version.get("metadataBlocks", {}).values():
        for field in block.get("fields", []):
            header.append(f"{field['typeName']}: {field_value(field)}")

    files = version.get("files", [])
    header += ["", f"== FILES ({len(files)}) =="]
    for f in files:
        df = f.get("dataFile", {})
        size_kb = round(df.get("filesize", 0) / 1024, 1)
        restricted = " [restricted]" if f.get("restricted") else ""
        desc = f" - {f['description']}" if f.get("description") else ""
        folder = f"{f['directoryLabel']}/" if f.get("directoryLabel") else ""
        header.append(f"- {folder}{df.get('filename')} ({df.get('contentType')}, {size_kb} KB){restricted}{desc}")

    all_names, downloaded, not_read = [], [], []
    for f in files:
        df = f.get("dataFile", {})
        name = df.get("filename", "")
        all_names.append(name)
        lower = name.lower()
        size_mb = df.get("filesize", 0) / 1_048_576
        readable = (lower.endswith(DATA_TYPES + DOC_TYPES)
                    or df.get("contentType", "").startswith("text/tab-separated-values"))

        if not readable:
            not_read.append(f"{name} (file type not readable)")
            continue
        if f.get("restricted") and not token:
            not_read.append(f"{name} (restricted)")
            continue
        if size_mb > args.max_mb:
            not_read.append(f"{name} ({size_mb:.0f} MB, over the --max-mb limit)")
            continue

        dest = DOWNLOADS / slug / name
        print(f"  downloading {name} ({size_mb:.1f} MB) ...", flush=True)
        try:
            download(f"{server}/api/access/datafile/{df['id']}", token, dest)
            downloaded.append(dest)
        except (urllib.error.HTTPError, urllib.error.URLError) as e:
            not_read.append(f"{name} (download failed: {e})")

    package, notes = build_package(header, downloaded, all_names, not_read,
                                   budget_tokens=args.budget_tokens,
                                   full_out=DOWNLOADS / slug / "_full_package.txt")

    INBOX.mkdir(exist_ok=True)
    out = INBOX / f"{slug}.txt"
    out.write_text(package, encoding="utf-8")

    print(f"Saved {out.relative_to(BASE)}. Downloads are in downloads/{slug}/")
    print(f"Package size: roughly {len(package) // 3:,} tokens (budget {args.budget_tokens:,}).")
    if notes:
        print("To fit the model's window, this was shortened:")
        for n in notes:
            print(f"  - {n}")
        if any("README" in n and "cut" in n for n in notes):
            print("The README itself was cut. For a fuller review, use a bigger window:")
            print("  re-run this script with --budget-tokens 20000, then:")
            print("  python run_skill.py readme-review --ctx 32768")
        print(f"The complete, unshortened version is in downloads/{slug}/_full_package.txt")
    print("Next: python run_skill.py readme-review   (or deposit-readiness)")


if __name__ == "__main__":
    main()
