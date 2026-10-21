"""
Build a review package from a folder on your computer (e.g. a deposit that is
not on Borealis yet) and save it to inbox/.

Usage (from inside the curation-skills folder):
    python prepare_local.py path/to/dataset-folder

Every file in the folder (and its subfolders) is considered.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from package import DEFAULT_BUDGET_TOKENS, build_package

BASE = Path(__file__).resolve().parent
INBOX = BASE / "inbox"


def main():
    parser = argparse.ArgumentParser(description="Build a review package from a local folder.")
    parser.add_argument("folder", help="Path to the dataset folder")
    parser.add_argument("--budget-tokens", type=int, default=DEFAULT_BUDGET_TOKENS,
                        help=f"Target package size (default {DEFAULT_BUDGET_TOKENS}; use about 20000 with --ctx 32768)")
    args = parser.parse_args()
    folder = Path(args.folder).expanduser().resolve()
    if not folder.is_dir():
        raise SystemExit(f"Not a folder: {folder}")

    paths = [p for p in sorted(folder.rglob("*"))
             if p.is_file() and not p.name.startswith((".", "~$"))]
    if not paths:
        raise SystemExit("The folder has no files.")

    header = [f"Dataset folder: {folder.name}", "", f"== FILES ({len(paths)}) =="]
    header += [f"- {p.relative_to(folder)} ({p.stat().st_size / 1024:.1f} KB)" for p in paths]

    slug = re.sub(r"[^A-Za-z0-9]+", "_", folder.name).strip("_")
    package, notes = build_package(header, paths, [p.name for p in paths], [],
                                   budget_tokens=args.budget_tokens,
                                   full_out=BASE / "downloads" / slug / "_full_package.txt")

    INBOX.mkdir(exist_ok=True)
    out = INBOX / f"{slug}.txt"
    out.write_text(package, encoding="utf-8")
    print(f"Saved {out.relative_to(BASE)}")
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
    print("Next: python run_skill.py readme-review")


if __name__ == "__main__":
    main()
