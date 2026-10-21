"""
Run a curation skill with a local Ollama model.

Usage (from inside the curation-skills folder):
    python run_skill.py                         # list available skills
    python run_skill.py deposit-readiness       # run a skill on every file in inbox/
    python run_skill.py auto                    # let the model pick a skill for each file
    python run_skill.py deposit-readiness --model gemma3:12b
    python run_skill.py readme-review --file 10_5683_SP4_VIC1LT.txt   # just one inbox file

Results are saved in outputs/ as <file>__<skill>__<model>.json
"""

from __future__ import annotations

import argparse
import json
import sys
import webbrowser
from pathlib import Path

import ollama

from read_documents import DOC_TYPES, extract_text
from render_report import render_file

BASE = Path(__file__).resolve().parent
SKILLS_DIR = BASE / "skills"
INBOX = BASE / "inbox"
OUTPUTS = BASE / "outputs"

DEFAULT_MODEL = "qwen3:8b"
# Ollama's default context window is small; skills plus a document need more room.
OPTIONS = {"temperature": 0.2, "num_ctx": 16384, "num_predict": 4096}


def read_frontmatter(skill_md: Path) -> dict:
    """Read the name and description lines between the --- markers."""
    text = skill_md.read_text(encoding="utf-8")
    info = {}
    if text.startswith("---"):
        header = text.split("---", 2)[1]
        for line in header.strip().splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                info[key.strip()] = value.strip()
    return info


def list_skills() -> dict:
    skills = {}
    for skill_md in sorted(SKILLS_DIR.glob("*/SKILL.md")):
        info = read_frontmatter(skill_md)
        name = info.get("name", skill_md.parent.name)
        skills[name] = {"folder": skill_md.parent, "description": info.get("description", "")}
    return skills


def build_instructions(folder: Path) -> str:
    """Combine SKILL.md with everything in references/ and examples/."""
    parts = [(folder / "SKILL.md").read_text(encoding="utf-8")]
    for sub in ("references", "examples"):
        for f in sorted((folder / sub).glob("*")):
            if f.is_file():
                parts.append(f"\n\n=== {sub}/{f.name} ===\n{f.read_text(encoding='utf-8')}")
    return "".join(parts)


def pick_skill(skills: dict, document: str, model: str) -> str:
    """Show the model only the skill descriptions and ask it to choose one."""
    menu = "\n".join(f"- {name}: {s['description']}" for name, s in skills.items())
    response = ollama.chat(
        model=model,
        messages=[{
            "role": "user",
            "content": f"Which skill best fits this document? Reply as JSON: {{\"skill\": \"<name>\"}}\n\n"
                       f"Skills:\n{menu}\n\nDocument (first 2000 characters):\n{document[:2000]}",
        }],
        format="json",
        think=False,
        options=OPTIONS,
    )
    choice = json.loads(response["message"]["content"]).get("skill", "")
    if choice not in skills:
        raise ValueError(f"Model picked an unknown skill: {choice!r}")
    return choice


def run(skill_name: str, folder: Path, document: str, model: str) -> dict:
    instructions = build_instructions(folder)
    approx_tokens = (len(instructions) + len(document)) // 3 + OPTIONS["num_predict"]
    if approx_tokens > OPTIONS["num_ctx"] * 0.95:
        print(f"  Warning: instructions + document + room for the answer come to roughly {approx_tokens:,} tokens, "
              f"but the window is {OPTIONS['num_ctx']:,}. Part of it will be lost.\n"
              f"  Fix: fetch again with a smaller package (--budget-tokens), or raise the window (--ctx 32768).")
    response = ollama.chat(
        model=model,
        messages=[
            {"role": "system", "content": instructions},
            {"role": "user", "content": f"Here is the material to review:\n\n{document}"},
        ],
        format="json",
        think=False,
        options=OPTIONS,
    )
    return json.loads(response["message"]["content"])


def main():
    parser = argparse.ArgumentParser(description="Run a curation skill with a local model.")
    parser.add_argument("skill", nargs="?", help="Skill name, or 'auto' to let the model choose")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Ollama model (default {DEFAULT_MODEL})")
    parser.add_argument("--file", help="Only review this file from inbox/ (name, e.g. 10_5683_SP4_VIC1LT.txt)")
    parser.add_argument("--open", action="store_true", help="Open each readable report in your browser when done")
    parser.add_argument("--ctx", type=int, default=OPTIONS["num_ctx"],
                        help="Model window size in tokens (default 16384; 32768 uses about 2.5 GB more memory)")
    args = parser.parse_args()
    OPTIONS["num_ctx"] = args.ctx

    skills = list_skills()
    if not args.skill:
        print("Available skills:")
        for name, s in skills.items():
            print(f"  {name}: {s['description']}")
        return
    if args.skill != "auto" and args.skill not in skills:
        sys.exit(f"No skill called {args.skill!r}. Run without arguments to list skills.")

    readable = DOC_TYPES + (".csv",)
    files = [f for f in sorted(INBOX.glob("*")) if f.is_file() and f.suffix.lower() in readable]
    if args.file:
        files = [f for f in files if f.name == Path(args.file).name]
        if not files:
            sys.exit(f"{args.file!r} is not in inbox/. Files there: "
                     + ", ".join(f.name for f in sorted(INBOX.glob('*')) if f.is_file()))
    if not files:
        sys.exit("No readable files in inbox/ (.txt .md .docx .pdf .csv .json).")
    print(f"Reviewing {len(files)} file(s) from inbox/: " + ", ".join(f.name for f in files))

    OUTPUTS.mkdir(exist_ok=True)
    for f in files:
        document, note = extract_text(f)
        if not document.strip():
            print(f"{f.name}: skipped ({note or 'no text found'})")
            continue
        if note:
            print(f"{f.name}: note: {note}")
        skill_name = pick_skill(skills, document, args.model) if args.skill == "auto" else args.skill
        print(f"{f.name} -> {skill_name} ({args.model}) ...", flush=True)
        try:
            result = run(skill_name, skills[skill_name]["folder"], document, args.model)
        except json.JSONDecodeError:
            print("  The model did not return valid JSON; skipping.")
            continue
        out = OUTPUTS / f"{f.stem}__{skill_name}__{args.model.replace(':', '-')}.json"
        out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  saved {out.relative_to(BASE)}")
        report = render_file(out)
        if report:
            print(f"  readable report: {report.relative_to(BASE)}  (double-click to open)")
            if args.open:
                webbrowser.open(report.resolve().as_uri())


if __name__ == "__main__":
    main()
