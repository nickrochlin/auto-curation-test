# Curation skills for local models

A small toolkit for **testing whether AI data curation can run on an ordinary laptop**. It uses
small, open AI models running locally through [Ollama](https://ollama.com), so nothing a curator
reviews is sent to an online AI service. It was built to explore how AI-assisted curation could
help build research data management capacity ahead of the Tri-Agency data deposit policy.

Each "skill" is a folder of plain-text instructions (Markdown) that tells the model how to do one
kind of curation check. A short Python script feeds a dataset and a skill to the model and turns
the answer into a readable report.

> ### New here, or not technical?
> **Start with [GETTING_STARTED.md](GETTING_STARTED.md).** It is a plain-language, step-by-step
> guide for Mac and Windows: installing Ollama and the Qwen model, running a review, reading
> the report, and fixing common problems. No technical background needed.

**Status: early prototype.** Reports are a first pass for a curator to check, not a verdict.
Small models make mistakes, and the checks have not yet been validated against curators' judgements.

## What it can do

| Skill | Question it answers |
|---|---|
| `readme-review` | Is the README thorough enough for someone else to understand and reuse the data? Checks 31 elements, based on the [Cornell README guide](https://data.research.cornell.edu/data-management/sharing/readme), plus two Canadian additions (human participants, Indigenous data governance). |
| `deposit-readiness` | Is the dataset ready for deposit in Borealis? Also drafts citation metadata. |

What it reads: `.txt`, `.md`, `.docx` and text-based `.pdf` documentation, and every row of
`.csv` / `.tab` / `.tsv` data files. Not read: scanned PDFs (they need OCR), old `.doc` files,
images, zips. Anything skipped is listed in the package, so nothing is skipped silently.

## Quick start (if you are comfortable with a terminal)

Requirements: [Ollama](https://ollama.com/download) (macOS 14+, or Windows 10 22H2+), Python 3.9+,
about 10 GB of disk space, and 16 GB of RAM recommended.

```
pip install -r requirements.txt
ollama pull qwen3:8b

python fetch_borealis.py https://doi.org/10.5683/SP4/XXXXXX   # copy a public Borealis dataset into inbox/
python run_skill.py readme-review                              # review it
```

Then open the `.html` report in `outputs/`. (On a Mac, use `python3` and `pip3` if `python` and
`pip` are not found.)

With 8 GB of RAM, use `ollama pull qwen3:4b` and add `--model qwen3:4b` to `run_skill.py`.

## Folder layout

```
curation-skills/
├── GETTING_STARTED.md        plain-language setup and usage guide
├── run_skill.py              runs a skill on every file in inbox/
├── fetch_borealis.py         copies a Borealis dataset into inbox/ for review
├── prepare_local.py          does the same for a dataset folder on your computer
├── package.py                builds the review package (used by the two scripts above)
├── profile_data.py           reads every row of a data file and summarises each column
├── read_documents.py         turns .txt .md .docx .pdf into plain text
├── render_report.py          turns a result (.json) into a readable web page (.html)
├── requirements.txt          the Python libraries needed
├── inbox/                    review packages go here; starts empty, never shared
├── outputs/                  results: a readable .html report plus the raw .json; never shared
├── downloads/                files fetched from Borealis; never shared
├── samples/                  a made-up example package, for practice only
└── skills/
    ├── deposit-readiness/    Borealis deposit check and draft citation metadata
    └── readme-review/        element-by-element README thoroughness check
        ├── SKILL.md          name, description, and step-by-step instructions
        ├── references/       checklists and vocabularies the skill relies on
        └── examples/         one sample input and the ideal output
```

`inbox/`, `outputs/` and `downloads/` can hold real deposits, so `.gitignore` keeps their
contents out of the repository.

## Run it

```
python run_skill.py                                    # list skills
python run_skill.py readme-review                      # run on everything in inbox/
python run_skill.py readme-review --file NAME.txt      # run on one inbox file only
python run_skill.py readme-review --model gemma3:12b   # try another model
python run_skill.py readme-review --ctx 32768          # bigger window for large packages
python run_skill.py readme-review --open               # open the report when done
python run_skill.py auto                               # model chooses the skill
```

The tool reviews **every** file in `inbox/`, so clear out old packages between datasets, or use `--file`.

## Review a dataset

From Borealis (reads only; never changes anything there):
```
python fetch_borealis.py doi:10.5683/SP3/XXXXXX
python run_skill.py readme-review
```
Public datasets need no API token. For a draft or restricted dataset you have access to, set the
environment variable `BOREALIS_API_TOKEN` first. Never put a token in a file.

From a folder on your computer:
```
python prepare_local.py ~/Documents/my-dataset
python run_skill.py readme-review
```

Either way, the inbox file contains:
- the full text of the README and other documentation (`.txt` `.md` `.docx` `.pdf`)
- README CHECKS: exact counts of which files and variables the README never mentions
- a profile of every data file, built by reading every row, with flags for things a curator
  would care about (postal codes, precise coordinates, missing-value codes, free text)
- a list of files that could not be read, and why

## If a dataset is too big for the model

The model can only hold so much text at once (its "window", 16,384 tokens by default).
The skill's instructions and the model's answer use about half of it, so the package
for a dataset is kept to a budget (6,500 tokens by default). When a dataset is bigger,
the scripts shorten the least important material first, tell you exactly what was cut,
and save the complete version in `downloads/<name>/_full_package.txt`:

1. data profiles are condensed to the flagged columns
2. other documentation is shortened
3. the README itself is shortened last

The README CHECKS (missing files, undocumented variables) always use the complete files.

For a long README, give the model a bigger window (needs about 2.5 GB more memory):
```
python fetch_borealis.py doi:10.5683/SP3/XXXXXX --budget-tokens 20000
python run_skill.py readme-review --ctx 32768
```

## Reading the results

Each run saves two files in `outputs/`: the raw `.json` and a readable `.html` report
with the same name. Double-click the `.html` to open it in your browser. It works offline
and sends nothing anywhere.

The report shows the overall rating, the most important fixes, and a colour-coded table.
Wherever the model quotes the README as evidence, the quote is checked against the source,
and quotes that cannot be found are flagged. The model's overall rating is also checked
against its own table.

To make reports for results you already have, without running the model again:
```
python render_report.py
```

## Add a new skill

1. Copy a skill folder and rename it (lowercase, hyphens).
2. Edit the `name` and `description` lines at the top of `SKILL.md`.
3. Rewrite the steps, replace the references, and update the example input and output.
4. Run `python run_skill.py` to confirm it is listed.

Skills are plain Markdown, so curators can write and improve them without any coding.
The Python scripts rarely need to change.

## Sources

- Cornell University, [Guide to writing "readme" style metadata](https://data.research.cornell.edu/data-management/sharing/readme), the basis of the `readme-review` checklist.
- [Borealis](https://borealisdata.ca) API documentation from [Scholars Portal](https://docs.scholarsportal.info/Main/SP/Borealis/Borealis_Admin/Dataverse_API/).
