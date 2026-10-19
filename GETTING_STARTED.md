# Getting started: a plain-language guide

**No technical background needed.** This guide walks you through everything, one small step at a time, for both Mac and Windows. The first-time setup takes about 30 to 45 minutes, most of it waiting for downloads. After that, reviewing a dataset takes a few minutes.

---

## What this tool does

When a researcher deposits a dataset in a repository like Borealis, someone has to check that it is well described: Is there a README? Does it explain every variable? Does it say what the license is? Is anything sensitive hiding in the data?

This tool does a **first-pass check** of that. You point it at a dataset, and it produces a one-page report that shows:

- what is missing or unclear in the README,
- which variables in the data are never explained,
- possible privacy problems (such as postal codes or exact coordinates), and
- a short list of the most important things to fix.

It uses a small **AI model that runs on your own computer**. Nothing you review is sent to an online AI service.

> **Important:** the report is a first pass to help a curator, not a verdict. Small AI models make mistakes. Always have a person check anything that matters.

## Is my data safe?

Reviews run **on your computer**. Your dataset files are not uploaded to an AI company.

Your computer does use the internet for three things: downloading the software and the AI model during setup, downloading a public dataset from Borealis when you ask it to, and the software's own update checks.

## What you need

| | |
|---|---|
| **A computer** | Mac (macOS 14 "Sonoma" or newer) or Windows (Windows 10 version 22H2 or newer, or Windows 11) |
| **Memory (RAM)** | **16 GB recommended.** See below for how to check. |
| **Free disk space** | About **10 GB** |
| **Internet** | Needed for setup, and when you fetch a dataset from Borealis |
| **A Borealis DOI** | Or a folder of dataset files on your computer |

**How to check your memory:**
- *Mac:* click the Apple menu (top-left), then **About This Mac**. Look for **Memory**.
- *Windows:* click Start, type **About your PC**, press Enter. Look for **Installed RAM**.

If you have **8 GB**, it can still work. In Step 6 use the smaller model, `qwen3:4b`, instead, and see the note there. Results will be rougher.

Older Intel Macs can run this but will be slow.

---

# Part 1: One-time setup

You only do this once.

## Step 1: Install Ollama

Ollama is the free program that runs AI models on your computer. Think of it as the engine.

1. Go to **https://ollama.com/download**
2. Download the version for your computer.
3. **Mac:** open the downloaded file, drag **Ollama** into your **Applications** folder, then open it. If it asks permission to install its command-line tool, say yes.
   **Windows:** double-click **OllamaSetup.exe** and follow the prompts. It does not need administrator rights.
4. Ollama then runs quietly in the background. You may see a small llama icon near the clock (Windows) or at the top of the screen (Mac). You don't need to do anything with it.

## Step 2: Install Python

Python is the programming language this tool is written in. You won't write any Python, but your computer needs it to run the tool.

1. Go to **https://www.python.org/downloads/** and click the big yellow **Download Python** button.
2. Open the downloaded file and follow the installer.
3. **Windows only, and this matters:** on the very first screen of the installer, tick the box at the bottom that says **"Add python.exe to PATH"** *before* you click **Install Now**. If you miss this, nothing later will work.

If you already have Python 3.9 or newer, you can skip this step.

## Step 3: Download this project

1. Open this project's page on GitHub (ask the person who shared it for the link).
2. Click the green **Code** button, then **Download ZIP**.
3. **Unzip it.** On a Mac, double-click the file. On Windows, right-click it and choose **Extract All** (don't just open it from inside the zip).
4. Move the unzipped folder somewhere easy to find, such as **Documents**.

## Step 4: Open a "terminal" in the project folder

A **terminal** is a window where you type short instructions to your computer instead of clicking. It looks old-fashioned, but you only need to copy and paste a few lines.

**On a Mac:**
1. Press **Cmd + Space**, type **Terminal**, and press **Enter**.
2. Type `cd` followed by **one space**. Don't press Enter yet.
3. Drag the project folder from Finder into the Terminal window. Its location appears after `cd `.
4. Press **Enter**.

**On Windows:**
1. Open the project folder in File Explorer.
2. Click once in the **address bar** at the top (the box showing the folder's location).
3. Type `powershell` and press **Enter**. A blue window opens, already in the right folder.

**Check you're in the right place.** Type this and press Enter:

- Mac: `ls`
- Windows: `dir`

You should see a list that includes **run_skill.py**. If you don't, you're one folder too high or too low. Some downloads have a folder inside a folder, so open the inner one and try again.

> **From now on, every command in this guide is typed into this window, followed by Enter.** Mac commands start with `python3`. Windows commands start with `python`. Where they differ, both are shown.

## Step 5: Install the helper libraries

Libraries are small add-ons the tool needs. Copy this line, paste it into the terminal, and press Enter:

- Mac: `python3 -m pip install -r requirements.txt`
- Windows: `python -m pip install -r requirements.txt`

Lines of text will scroll past. When the cursor returns, it's done.

## Step 6: Download the AI model

The model is the "brain" Ollama runs. We use one called **Qwen3 (8 billion parameters)**. It's a good balance: small enough for an ordinary laptop, capable enough for this task.

Paste this and press Enter (same on Mac and Windows):

```
ollama pull qwen3:8b
```

It's a **5.2 GB** download, so it takes anywhere from a few minutes to an hour depending on your internet. A progress bar shows how far along it is. You only do this once.

> **Only 8 GB of memory?** Use the smaller model instead (a 2.5 GB download):
> ```
> ollama pull qwen3:4b
> ```
> Then, every time this guide tells you to run `run_skill.py`, add `--model qwen3:4b` to the end of the line.

## Step 7: Check that everything works

- Mac: `python3 run_skill.py`
- Windows: `python run_skill.py`

You should see a list of two "skills" (readme-review and deposit-readiness). If you do, **setup is finished.** If you see an error, see "If something goes wrong" near the bottom.

---

# Part 2: Reviewing a dataset

Do this every time. There are two ways to start, depending on where the dataset is.

## Option A: The dataset is already on Borealis

1. On the dataset's Borealis page, find its **DOI**. It looks like `https://doi.org/10.5683/SP4/ABC123`.
2. In your terminal, type the following, pasting your own DOI at the end:

   - Mac: `python3 fetch_borealis.py https://doi.org/10.5683/SP4/ABC123`
   - Windows: `python fetch_borealis.py https://doi.org/10.5683/SP4/ABC123`

3. Wait. It downloads the files and reads them. When it prints **"Saved inbox/..."**, it's ready.

This only reads from Borealis. It never changes anything there. It works for **public, published** datasets.

## Option B: The files are on your computer

Put all the dataset's files together in one folder. Then:

- Mac: type `python3 prepare_local.py ` (with a space at the end), then **drag the folder into the Terminal window** and press Enter.
- Windows: type `python prepare_local.py ` (with a space at the end), then **drag the folder into the PowerShell window** and press Enter. If dragging doesn't work, hold **Shift**, right-click the folder, choose **Copy as path**, and paste it after the space.

## Then: run the review

- Mac: `python3 run_skill.py readme-review`
- Windows: `python run_skill.py readme-review`

This can take a few minutes. **The first time is slowest**, because the model has to load into your computer's memory. Your computer may run its fan and feel busy. That's normal.

Two checks are available. Use the name after `run_skill.py` to choose:

| Name | Question it answers |
|---|---|
| `readme-review` | Is the README thorough enough for someone else to understand and reuse the data? |
| `deposit-readiness` | Is the dataset ready to deposit in Borealis? It also drafts the citation information. |

## Open your report

1. Open the project folder and go into the **outputs** folder.
2. Double-click the file ending in **.html**. It opens in your web browser.

(The file ending in `.json` is the same information in a form meant for programs. You can ignore it.)

## Before the next dataset

The tool reviews **everything in the `inbox` folder**. So before you start a new dataset, open the `inbox` folder and delete the files from the last one. Otherwise the old dataset gets reviewed again alongside the new one.

---

# Part 3: Reading the report

**At the top** is an overall rating and the most important fixes, in order. If you read nothing else, read those.

**The table below** goes through a standard checklist, one row at a time, based on a widely used guide for writing README files. Each row has a status:

| Status | Meaning |
|---|---|
| **Present** | The README covers this. |
| **Partial** | It's there, but incomplete (for example, units for some variables but not all). |
| **Missing** | It isn't there. |
| **Not applicable** | It doesn't apply to this dataset. |

A ★ marks the items considered the **minimum** needed for someone to reuse the data.

**Check the evidence.** For things marked Present or Partial, the report shows a short quote from the README as proof, and checks that the quote really exists:

- a green **"quote found in the source"** means it checks out;
- a red **"quote was not found"** means the AI may have misread or made something up. Look it up yourself before trusting that row.

The report also warns you if the AI's overall rating doesn't match its own table. When they disagree, trust the table.

---

# If something goes wrong

Find the message you saw, then try the fix beside it.

| What you see | What to do |
|---|---|
| `python is not recognized` or "Python was not found" (Windows, sometimes opening the Microsoft Store), or `command not found: python` (Mac) | **Mac:** use `python3`, not `python`. **Windows:** Python wasn't added to PATH. Run the Python installer again, choose **Modify**, and tick **Add python.exe to PATH**. Then close and reopen the terminal. |
| `pip` is not found | Use the longer form from Step 5: `python3 -m pip ...` (Mac) or `python -m pip ...` (Windows). |
| `No module named 'ollama'` | Step 5 didn't finish. Run it again. |
| `externally-managed-environment` (Mac) | Run `python3 -m pip install --user --break-system-packages -r requirements.txt` instead. |
| `Failed to connect to Ollama`, or `connection refused` | Ollama isn't running. Open the **Ollama** app (from Applications on a Mac, from the Start menu on Windows), wait a few seconds, and try again. |
| `model 'qwen3:8b' not found` | Run `ollama pull qwen3:8b` (Step 6). |
| `unexpected keyword argument 'think'` | Your software is out of date. Download the latest Ollama from ollama.com, then run `python3 -m pip install --upgrade ollama` (Windows: `python -m pip ...`). |
| `Borealis said 404` | The DOI wasn't found. Check it for typos or extra characters at the end, and check that the dataset is published. |
| `Borealis said 401` or `403` | The dataset is a draft or restricted. Public datasets work directly. For others, ask the person who shared this tool about using an API token. |
| `No readable files in inbox` | You need to do Option A or B first, so there's something to review. |
| The report is about the wrong dataset | Old files are still in the `inbox` folder. Delete them and run the review again. |
| A warning about the input being larger than the window | The dataset is bigger than the model can read in one go. The technical README has a section, "If a dataset is too big for the model". Your report will say what was left out. |
| Everything is very slow, or the computer struggles | Close other programs (especially web browsers with many tabs). If it's still too slow, use the smaller model (see the 8 GB note in Step 6). |

**Still stuck?** Copy the full error message from the terminal and send it to whoever shared this tool with you.

---

# Words used in this guide

- **AI model:** a program trained on lots of text that can read and write. Here it reads a README and judges it.
- **Ollama:** the free program that runs AI models on your own computer.
- **Qwen3:** the specific AI model this project uses.
- **Python:** the programming language this tool is written in.
- **Library:** a small add-on that a program needs in order to work.
- **Terminal / PowerShell:** the window where you type commands.
- **Command:** a line you type into the terminal and run by pressing Enter.
- **DOI:** a permanent web address for a dataset, like `https://doi.org/10.5683/...`.
- **README:** a document that explains what a dataset is and how to use it.
- **Borealis:** the Canadian research data repository where datasets are deposited and shared.
- **Skill:** a set of written instructions that tells the model how to do one kind of check.
- **Local:** happening on your own computer, not on the internet.

---

*This tool is an early prototype. Please tell the project team what works and what doesn't.*
