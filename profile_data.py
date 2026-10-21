"""
Read every row of a data file and summarise each column in a few lines.

The model never sees the raw data. It sees this summary, which is small enough
to fit in its window no matter how many rows the file has.

You can also run it on a file directly:
    python profile_data.py path/to/data.csv
"""

from __future__ import annotations

import csv
import re
import sys
from collections import Counter
from pathlib import Path

csv.field_size_limit(10_000_000)

MISSING = {"", "na", "n/a", "nan", "null", "none", ".", "-", "missing"}
MISSING_CODES = {"-9", "-99", "-999", "-9999", "999", "9999", "-8", "-88", "-888"}
MAX_TRACKED = 1000      # stop counting distinct values past this
MAX_PATTERN_CHECKS = 2000   # values per column checked for identifiers
MAX_COLUMNS_SHOWN = 150

INT_RE = re.compile(r"^[+-]?\d+$")
FLOAT_RE = re.compile(r"^[+-]?(\d+\.\d*|\.\d+|\d+)([eE][+-]?\d+)?$")
DATE_RE = re.compile(r"^(\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{4})([ T].*)?$")

PATTERNS = {
    "Canadian postal codes": re.compile(r"^[A-Za-z]\d[A-Za-z][ -]?\d[A-Za-z]\d$"),
    "partial postal codes (FSA)": re.compile(r"^[A-Za-z]\d[A-Za-z]$"),
    "email addresses": re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$"),
    "phone numbers": re.compile(r"^\+?1?[\s.-]?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}$"),
}
SENSITIVE_NAME_WORDS = {
    "name", "firstname", "lastname", "surname", "fullname", "email", "phone", "tel",
    "address", "street", "postal", "postcode", "zip", "dob", "birth", "birthdate",
    "sin", "ssn", "healthcard", "phn", "ip", "ipaddress", "gender", "sex", "ethnicity",
    "religion", "income", "diagnosis", "participant", "respondent",
}
COORD_WORDS = {"lat", "latitude", "lon", "long", "lng", "longitude"}


def value_type(v: str) -> str:
    if INT_RE.match(v):
        return "integer"
    if FLOAT_RE.match(v):
        return "decimal"
    if DATE_RE.match(v):
        return "date"
    return "text"


class Column:
    def __init__(self, name: str):
        self.name = name
        self.filled = 0
        self.missing = 0
        self.types = Counter()
        self.counts = Counter()
        self.too_many = False
        self.minimum = None
        self.maximum = None
        self.max_decimals = 0
        self.text_lengths = 0
        self.odd_examples = []      # values whose type differs from the column's
        self.missing_codes = Counter()
        self.pattern_hits = Counter()
        self.pattern_checked = 0

    def add(self, raw: str):
        v = raw.strip()
        if v.lower() in MISSING:
            self.missing += 1
            return
        self.filled += 1
        t = value_type(v)
        self.types[t] += 1
        self.text_lengths += len(v)

        if not self.too_many:
            self.counts[v] += 1
            if len(self.counts) > MAX_TRACKED:
                self.too_many = True
                self.counts = Counter(dict(self.counts.most_common(10)))
        elif v in self.counts:
            self.counts[v] += 1

        if t in ("integer", "decimal"):
            n = float(v)
            self.minimum = n if self.minimum is None else min(self.minimum, n)
            self.maximum = n if self.maximum is None else max(self.maximum, n)
            if "." in v:
                self.max_decimals = max(self.max_decimals, len(v.split(".")[1]))
            if v in MISSING_CODES:
                self.missing_codes[v] += 1

        if self.pattern_checked < MAX_PATTERN_CHECKS:
            self.pattern_checked += 1
            for label, rx in PATTERNS.items():
                if rx.match(v):
                    self.pattern_hits[label] += 1

    def main_type(self) -> str:
        if not self.types:
            return "empty"
        numeric = self.types["integer"] + self.types["decimal"]
        if numeric / self.filled >= 0.95:
            return "decimal" if self.types["decimal"] else "integer"
        top, count = self.types.most_common(1)[0]
        return top if count / self.filled >= 0.95 else "mixed"

    def describe(self, rows: int) -> list[str]:
        kind = self.main_type()
        pct = f"{self.missing / rows:.0%}" if rows else "0%"
        unique = f"{MAX_TRACKED}+" if self.too_many else str(len(self.counts))
        line = f"- {self.name}: {kind}, missing {self.missing} ({pct}), distinct values {unique}"
        if kind in ("integer", "decimal") and self.minimum is not None:
            line += f", range {self.minimum:g} to {self.maximum:g}"
        if kind in ("text", "mixed") and not self.too_many and len(self.counts) <= 15:
            line += ", values: " + ", ".join(f"{k} ({c})" for k, c in self.counts.most_common(8))
        elif self.counts:
            examples = [k[:40] for k, _ in self.counts.most_common(3)]
            line += ", e.g. " + " | ".join(examples)
        out = [line]

        # Flags for the curator
        words = {w for w in re.split(r"[^a-z]+", self.name.lower()) if w}
        words.add(re.sub(r"[^a-z]", "", self.name.lower()))
        if kind == "empty":
            out.append("    FLAG: column is entirely empty")
        if kind == "mixed":
            out.append(f"    FLAG: mixed value types {dict(self.types)}")
        for label, hits in self.pattern_hits.items():
            if hits >= max(3, 0.2 * self.pattern_checked):
                out.append(f"    FLAG: values look like {label} ({hits} of {self.pattern_checked} checked)")
        if words & SENSITIVE_NAME_WORDS:
            out.append("    FLAG: column name suggests information about people; check it is not identifying or sensitive")
        if words & COORD_WORDS and self.max_decimals >= 4:
            out.append(f"    FLAG: precise coordinates ({self.max_decimals} decimal places, about 11 m or better)")
        if kind in ("integer", "decimal"):
            # A real missing-value code is usually the column's lowest or highest value, or common.
            suspicious = [
                (k, c) for k, c in self.missing_codes.most_common()
                if float(k) in (self.minimum, self.maximum) or c >= 0.01 * self.filled
            ]
            if suspicious:
                codes = ", ".join(f"{k} ({c})" for k, c in suspicious[:3])
                out.append(f"    FLAG: possible missing-value codes: {codes}; check they are documented")
        if kind == "text" and self.filled and self.text_lengths / self.filled > 60:
            out.append("    FLAG: long free text; may contain identifying details, review manually")
        return out


def sniff_delimiter(path: Path) -> str:
    if path.suffix.lower() in (".tab", ".tsv"):
        return "\t"
    with path.open(encoding="utf-8", errors="replace", newline="") as f:
        sample = f.read(20000)
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        return ","


def column_names(path: Path) -> list[str]:
    """Just the header row of a data file."""
    with path.open(encoding="utf-8-sig", errors="replace", newline="") as f:
        try:
            return [h.strip() for h in next(csv.reader(f, delimiter=sniff_delimiter(path))) if h.strip()]
        except StopIteration:
            return []


def profile(path: Path, label: str | None = None, compact: bool = False, max_flagged: int = 20) -> str:
    """
    Return a plain-text profile of a delimited data file.
    compact=True keeps full detail only for columns that have a FLAG; the rest are listed by name.
    """
    label = label or path.name
    delimiter = sniff_delimiter(path)
    with path.open(encoding="utf-8-sig", errors="replace", newline="") as f:
        reader = csv.reader(f, delimiter=delimiter)
        try:
            header = next(reader)
        except StopIteration:
            return f"== DATA FILE PROFILE: {label} ==\nThe file is empty."
        columns = [Column(h.strip() or f"(unnamed column {i + 1})") for i, h in enumerate(header)]
        rows = 0
        bad_rows = 0
        blank_rows = 0
        for row in reader:
            if not any(cell.strip() for cell in row):
                blank_rows += 1
                continue
            rows += 1
            if len(row) != len(columns):
                bad_rows += 1
            for col, cell in zip(columns, row):
                col.add(cell)

    lines = [
        f"== DATA FILE PROFILE: {label} ==",
        f"Every row was read. Rows: {rows} | Columns: {len(columns)} | "
        f"Rows with the wrong number of fields: {bad_rows} | Blank rows: {blank_rows}",
    ]
    names = [c.name for c in columns]
    dupes = sorted({n for n in names if names.count(n) > 1})
    if dupes:
        lines.append(f"FLAG: duplicate column names: {', '.join(dupes)}")
    if header and all(value_type(h.strip()) in ("integer", "decimal") for h in header if h.strip()):
        lines.append("FLAG: the first row looks like data, not column names")
    if any(" " in n for n in names):
        lines.append("Note: some column names contain spaces")
    lines.append("Columns:")
    if compact:
        flagged, plain = [], []
        for col in columns:
            desc = col.describe(rows)
            (flagged if len(desc) > 1 else plain).append((col, desc))
        for col, desc in flagged[:max_flagged]:
            lines += desc
        if len(flagged) > max_flagged:
            lines.append(f"... {len(flagged) - max_flagged} more flagged columns not shown: "
                         + ", ".join(c.name for c, _ in flagged[max_flagged:max_flagged + 40]))
        if plain:
            lines.append(f"Columns with no flags ({len(plain)}): "
                         + ", ".join(f"{c.name} ({c.main_type()})" for c, _ in plain[:60])
                         + (f", ... and {len(plain) - 60} more" if len(plain) > 60 else ""))
        return "\n".join(lines)
    for col in columns[:MAX_COLUMNS_SHOWN]:
        lines += col.describe(rows)
    if len(columns) > MAX_COLUMNS_SHOWN:
        flagged = [c for c in columns[MAX_COLUMNS_SHOWN:] if len(c.describe(rows)) > 1]
        lines.append(f"... {len(columns) - MAX_COLUMNS_SHOWN} more columns not listed; flagged ones follow")
        for col in flagged:
            lines += col.describe(rows)
    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("Usage: python profile_data.py <file.csv|file.tab>")
    for p in sys.argv[1:]:
        print(profile(Path(p)))
        print()
