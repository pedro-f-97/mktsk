# AGENTS.md

Instructions for AI agents (and humans) working in this repository.

## Project

`mktsk` is a Python CLI that creates task folders named `YYMMDD - TaskName` with an
associated Markdown file, opened automatically. `mktsk-gui` (PySide6) offers the same
workflow interactively.

## Structure

- `mktsk/main.py` — CLI entry point
- `mktsk/gui.py` — PySide6 interface
- `mktsk/__main__.py` — module entry point and PyInstaller target; keep the absolute
  import, relative imports fail once frozen
- `mktsk/helpers.py` — name validation, reserved Windows names, opening files
- `mktsk/workers.py` — task logic: standardization, recognition, lookup, creation,
  signing, resuming
- `tests/` — pytest suite

## Commands

```bash
python -m pip install -e ".[dev,gui]"
ruff check .
pyright mktsk/
pytest
```

The `gui` extra is required so pyright resolves Qt imports. CI runs the same checks and
enforces coverage ≥ 95%. GUI tests run headless (`tests/conftest.py` forces
`QT_QPA_PLATFORM=offscreen`). Release tooling lives in the `release` extra.

## Domain rules (do not break)

- Date prefix: `datetime.now().astimezone().strftime("%y%m%d")` + `" - "`
- Standardize titles: NFKD, strip accents, keep only alphanumerics, join words in
  CamelCase with the first letter uppercase
- Folder: `<date> - <StandardizedTitle>`; file: `<StandardizedTitle>.md`
- Sign an empty `.md` with `# <StandardizedTitle>`, a blank line, then `## <dd/mm/YYYY>`
  from `strftime("%d/%m/%Y")`, and a blank line; never touch a non-empty file
- Lookup runs before any creation, in the current directory only, for
  `<yymmdd> - <StandardizedTitle>` on any date; the same title in another directory is a
  different task
- Resuming appends `## <today>` at the end of the `.md` unless that date is already
  there; existing text is never rewritten, only trailing whitespace is dropped; headings
  are matched loosely, so `##  05/08/2026 ` counts as 05/08/2026
- `is_task_folder(name)` is a shape check: a real `%y%m%d` date, ` - `, then an ASCII
  alphanumeric title that does not start with a lowercase letter (`2026` counts)
- `standardize_string` is not idempotent (`BigWord` becomes `Bigword`); never test
  `standardize_string(title) == title`
- Lookup uses `is_task_folder`; a folder that fails the check is never resumed, and the
  new task is created beside it
- Reject reserved Windows names (`CON`, `PRN`, `AUX`, `NUL`, `COM1-9`, `LPT1-9`)
- Open files with the OS default application (`os.startfile` / `xdg-open`)
- Folder and file names are ASCII only
- Reading a title back for display (`readable_title`): every uppercase letter starts a
  word and a digit starts one too, so `FSocietyEverbind` reads as `F Society Everbind`
  and `Task2` as `Task 2`; consecutive digits stay together, so `2026` survives

## GUI

- Entry point `mktsk-gui`; PySide6 comes in the optional `gui` extra; tests in
  `tests/test_gui.py` with pytest-qt
- No Qt imports in the CLI or the business logic
- Two panes in a `QSplitter`: a `QTreeWidget` on the left holding the current directory
  and its immediate subdirectories, so it shows where new tasks are created; a
  `QTabWidget` on the right holding one `QListWidget` per task category
- The tree lists folders only, one level deep, and never task folders or hidden
  directories (`list_subdirectories`); double-clicking a subdirectory navigates to it
  and the root does nothing
- The task list comes from `find_task_groups`: one tab per category, the current
  directory being a category named after itself, plus an `All` tab first; only
  categories that hold tasks get a tab
- `All` lists every task under a heading per category, headings bold and not
  selectable; a category tab lists just its own tasks, with no heading
- The active tab survives a refresh or a new task; when its category is gone, `All`
  takes over again
- Within a category, newest first, alphabetical for tasks of the same date
- A task folder with no `.md` is not listed; a task two levels down is not found
- A task label is `dd/mm/yyyy` + two spaces + `readable_title`, with the full path as
  tooltip
- Browsing is read-only: clicking a task just opens its `.md`, it never creates a file
  and never appends a date; only `create_task` resumes a task, and it still looks in
  the current directory only
- Remember the last path with `QSettings`
- Show `TaskError` in a `QMessageBox`; if opening the file fails, warn but never delete
  what was created
- Keep the window open and clear the title field after creating

## Conventions

- English code, symbols, docs and example data; test data uses placeholders
- `snake_case` functions and variables, `PascalCase` classes, `UPPER_CASE` constants
- Type hints on public functions; docstrings with `Args:` / `Returns:` / `Raises:`
- Small functions; imports sorted by isort (`ruff check . --fix`)
- Comment only when it adds value; never delete existing comments
- Tests in `tests/test_*.py`; never write to real user folders (`tmp_path`)

## Writing style

Short, direct, declarative. No fluff, emojis or exclamations. Bullets are fragments
without trailing punctuation.

Commits: `<type>: <description>`, type in `feat`, `fix`, `docs`, `refactor`, `test`,
`ci`, `chore`; one line, lowercase, no trailing period (`fix: prevent invalid task
descriptions`).

## Git

- Branch `main`; one topic per branch; a topic never lands on `main` directly
- Check `git rev-parse --abbrev-ref HEAD` before pushing
- Never push, open a PR or tag without explicit request
- LF line endings (`.gitattributes`)

## Releases

- Bump `version` in `pyproject.toml` in its own branch and merge before tagging
- Tag only commits already in `main`: annotated, message `Release <version>`, pushed
  with `git push origin <tag>`
- The workflow in `.github/workflows/release.yml` builds and uploads the artifacts
- To republish assets, re-run the workflow with the same `tag` input (`--clobber`
  replaces the asset)
- The Linux executable is named after the build-time glibc, which PyInstaller does not
  bundle
- Never attach an executable without the sdist (GPL-3.0 section 6)
