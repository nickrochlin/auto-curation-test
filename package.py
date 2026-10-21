"""
Build the review package that goes into inbox/.

Used by fetch_borealis.py (datasets on Borealis) and prepare_local.py (a folder
on your computer). For a set of dataset files it produces:
  - the full text of the README(s) and other documentation (.txt .md .docx .pdf)
  - a profile of every data file, built by reading every row
  - README CHECKS: facts a program can verify, such as which files and
    variables the README never mentions

The model can only hold a limited amount of text at once (its "window"), so the
package is kept within a size budget. When a dataset is too big, the least
important material is trimmed first, in this order:
  1. data profiles are condensed to the flagged columns
  2. other documentation is shortened
  3. the README itself is shortened (last, because it is what is being judged)
The README CHECKS are always computed on the complete files, so they stay exact.
"""

from __future__ import annotations

import re
from pathlib import Path

from profile_data import column_names, profile
from read_documents import DOC_TYPES, extract_text

DATA_TYPES = (".csv", ".tab", ".tsv")
CHARS_PER_TOKEN = 3          # deliberately cautious
DEFAULT_BUDGET_TOKENS = 6500  # leaves room in a 16,384-token window for the skill (~4,000) and the answer (~4,000)
OTHER_DOC_CHARS = 2500        # each non-README document, when trimming is needed
MIN_README_CHARS = 8000
HEADER_LINE_CHARS = 1000
MAX_HEADER_LINES = 120
SHORT_README_WORDS = 150
MAX_NAMES_SHOWN = 30


def is_readme(name: str) -> bool:
    return "readme" in name.lower() or "read_me" in name.lower() or "read-me" in name.lower()


def mentioned(term: str, text: str) -> bool:
    """Case-insensitive whole-word search."""
    return re.search(rf"(?<![A-Za-z0-9_]){re.escape(term)}(?![A-Za-z0-9_])", text, re.IGNORECASE) is not None


def short_list(names: list[str]) -> str:
    shown = ", ".join(names[:MAX_NAMES_SHOWN])
    return shown + (f", ... and {len(names) - MAX_NAMES_SHOWN} more" if len(names) > MAX_NAMES_SHOWN else "")


def cut(text: str, limit: int) -> str:
    """Shorten text at a line break near the limit."""
    if len(text) <= limit:
        return text
    head = text[:limit]
    newline = head.rfind("\n")
    return head[:newline] if newline > limit * 0.7 else head


def build_package(header_lines: list[str], paths: list[Path], all_file_names: list[str],
                  not_read: list[str], budget_tokens: int = DEFAULT_BUDGET_TOKENS,
                  full_out: Path | None = None) -> tuple[str, list[str]]:
    """
    header_lines:   metadata lines to put at the top
    paths:          files on disk to read
    all_file_names: every file in the dataset (including ones not downloaded)
    not_read:       files already skipped, with the reason
    budget_tokens:  target size of the package, in (estimated) tokens
    full_out:       if given and trimming was needed, the untrimmed package is saved here

    Returns (package text, list of notes about anything trimmed).
    """
    budget = budget_tokens * CHARS_PER_TOKEN
    not_read = list(not_read)
    docs = {}                                   # name -> text
    data_paths = {}                             # name -> path
    data_columns = {}

    for path in sorted(paths, key=lambda p: (not is_readme(p.name), p.name.lower())):
        lower = path.name.lower()
        if lower.endswith(DATA_TYPES):
            print(f"  profiling every row of {path.name} ...", flush=True)
            data_paths[path.name] = path
            data_columns[path.name] = column_names(path)
        elif lower.endswith(DOC_TYPES):
            print(f"  reading {path.name} ...", flush=True)
            text, note = extract_text(path)
            if not text:
                not_read.append(f"{path.name} ({note or 'no text found'})")
                continue
            docs[path.name] = text
            if note:
                docs[path.name] = f"NOTE: {note}\n{text}"
        else:
            not_read.append(f"{path.name} (file type not readable)")

    full_profiles = {n: profile(p, n) for n, p in data_paths.items()}
    compact_profiles = {n: profile(p, n, compact=True) for n, p in data_paths.items()}

    # ---- README checks: things a program can verify exactly (always on complete files) ----
    readme_texts = {n: t for n, t in docs.items() if is_readme(n)}
    other_texts = {n: t for n, t in docs.items() if not is_readme(n)}
    readme_all = "\n".join(readme_texts.values())
    docs_all = readme_all + "\n" + "\n".join(other_texts.values())

    checks = ["== README CHECKS (automated; these counts are exact and use the complete files) =="]
    readme_names = [n for n in all_file_names if is_readme(n)]
    if not readme_names:
        checks.append("FLAG: no README file in this dataset")
    elif not readme_texts:
        checks.append(f"FLAG: README file(s) present but could not be read: {', '.join(readme_names)}")
    else:
        words = len(readme_all.split())
        checks.append(f"README file(s): {', '.join(readme_texts)} | length: {words:,} words")
        if words < SHORT_README_WORDS:
            checks.append(f"FLAG: README is very short (under {SHORT_README_WORDS} words)")
        others = [n for n in all_file_names if not is_readme(n)]
        missing_files = [n for n in others
                         if not (mentioned(n, readme_all) or mentioned(Path(n).stem, readme_all))]
        checks.append(f"Files described in README: {len(others) - len(missing_files)} of {len(others)}")
        if missing_files:
            checks.append(f"FLAG: files the README never mentions: {short_list(missing_files)}")
    for file_name, cols in data_columns.items():
        if not cols:
            continue
        not_in_readme = [c for c in cols if not mentioned(c, readme_all)]
        nowhere = [c for c in cols if not mentioned(c, docs_all)]
        checks.append(f"{file_name}: {len(cols)} variables | named in README: {len(cols) - len(not_in_readme)} "
                      f"| named in any documentation: {len(cols) - len(nowhere)}")
        if nowhere:
            checks.append(f"FLAG: variables in {file_name} not named in ANY documentation: {short_list(nowhere)}")
    checks_text = "\n".join(checks)

    # ---- header: metadata and file list, kept to a sensible size ----
    header = [ln if len(ln) <= HEADER_LINE_CHARS else ln[:HEADER_LINE_CHARS] + " ..." for ln in header_lines]
    notes = []
    if len(header) > MAX_HEADER_LINES:
        notes.append(f"the metadata and file list were shortened ({len(header) - MAX_HEADER_LINES} lines left out)")
        header = header[:MAX_HEADER_LINES] + [f"... {len(header_lines) - MAX_HEADER_LINES} more lines not shown"]
    header_text = "\n".join(header)
    not_read_text = ("== FILES NOT READ ==\n" + "\n".join(f"- {n}" for n in not_read)) if not_read else ""

    def doc_section(name: str, text: str, limit: int) -> str:
        kind = "README" if is_readme(name) else "DOCUMENT"
        shown = cut(text, limit)
        label = f" (first {len(shown):,} of {len(text):,} characters)" if len(shown) < len(text) else ""
        return f"== {kind}: {name}{label} ==\n{shown}"

    def assemble(readme_limit, other_limit, profiles, note_lines):
        parts = [header_text, checks_text]
        if note_lines:
            parts.append("== NOTE: SHORTENED TO FIT THE MODEL'S WINDOW ==\n"
                         + "\n".join(f"- {n}" for n in note_lines)
                         + "\nIf the README was cut, do not mark an element missing just because it may be in "
                           "the part you cannot see; say so in the note field.")
        for name, text in docs.items():
            if is_readme(name):
                parts.append(doc_section(name, text, readme_limit))
        for name, text in docs.items():
            if not is_readme(name):
                parts.append(doc_section(name, text, other_limit))
        parts += list(profiles.values())
        if not_read_text:
            parts.append(not_read_text)
        return "\n\n".join(p for p in parts if p)

    BIG = 10 ** 9
    full_package = assemble(BIG, BIG, full_profiles, [])

    def breakdown(pkg_parts):
        return ", ".join(f"{k} ~{v // CHARS_PER_TOKEN:,}" for k, v in pkg_parts.items() if v)
    print("  size before trimming (approx. tokens): " + breakdown({
        "metadata+files": len(header_text), "README": sum(len(t) for t in readme_texts.values()),
        "other documents": sum(len(t) for t in other_texts.values()),
        "data profiles": sum(len(t) for t in full_profiles.values())}))

    package = full_package
    if len(package) > budget:
        # Step 1: condense the data profiles to the flagged columns
        profiles = full_profiles
        if any(full_profiles[n] != compact_profiles[n] for n in full_profiles):
            profiles = compact_profiles
            notes.append("data profiles were condensed: columns with FLAGS are shown in full, the rest by name only")
        package = assemble(BIG, BIG, profiles, notes)

        # Step 2: shorten other documentation
        other_limit = BIG
        if len(package) > budget and other_texts:
            other_limit = OTHER_DOC_CHARS
            cut_names = [n for n, t in other_texts.items() if len(t) > other_limit]
            if cut_names:
                notes.append(f"other documents were cut to their first {other_limit:,} characters: "
                             + ", ".join(cut_names))
            package = assemble(BIG, other_limit, profiles, notes)

        # Step 3: shorten the README last, to whatever room is left
        readme_limit = BIG
        if len(package) > budget and readme_texts:
            room = budget - len(assemble(0, other_limit, profiles, notes + ["x" * 150]))
            readme_limit = max(MIN_README_CHARS, room)
            for n, t in readme_texts.items():
                if len(t) > readme_limit:
                    notes.append(f"the README ({n}) was cut to its first {readme_limit:,} of {len(t):,} characters")
            package = assemble(readme_limit, other_limit, profiles, notes)

        # Step 4: if the data profiles alone are still too big, cap them
        if len(package) > budget * 1.15 and profiles:
            cap = max(1500, int(budget * 0.15) // max(1, len(profiles)))
            profiles = {n: cut(t, cap) for n, t in profiles.items()}
            notes.append(f"each data profile was cut to {cap:,} characters")
            package = assemble(readme_limit, other_limit, profiles, notes)

        if full_out is not None:
            full_out.parent.mkdir(parents=True, exist_ok=True)
            full_out.write_text(full_package, encoding="utf-8")

    return package, notes
