# AGENTS.md

Instructions for AI agents (and humans) working in this repository.

## Project

`mktsk` is a small Python CLI that creates task folders with a `YYMMDD - TaskName`
naming convention and an associated Markdown file, opened automatically. An optional
PySide6 desktop GUI (`mktsk-gui`) offers the same workflow interactively.

## Structure

- `mktsk/main.py` — CLI entry point (`argparse`), orchestrates the flow.
- `mktsk/gui.py` — PySide6 desktop interface over the same logic.
- `mktsk/__main__.py` — module entry point (`python -m mktsk`); delegates to the GUI and
  is the script PyInstaller freezes. Uses an absolute import on purpose, since relative
  imports do not resolve once the package is frozen.
- `mktsk/helpers.py` — OS helpers: name validation, reserved Windows names, opening files.
- `mktsk/workers.py` — task logic: title standardization, lookup, folder/file creation,
  signing and resuming an existing task.
- `tests/` — pytest test suite.
- `pyproject.toml` — packaging, dependencies and tooling configuration.

## Commands

```bash
python -m pip install -e ".[dev,gui]"
ruff check .
pyright mktsk/
pytest
```

The `gui` extra (PySide6) is required so `pyright mktsk/` resolves the Qt imports. GUI
tests run headless: `tests/conftest.py` forces `QT_QPA_PLATFORM=offscreen`.

CI installs `.[dev,gui]` and runs `ruff check .`, `pyright mktsk/` and `pytest`
(coverage ≥ 95% enforced).

Release tooling lives in the `release` extra (`build`, `twine`, `pyinstaller`); the
`dev` extra deliberately stays light because CI installs it on every run:

```bash
python -m pip install -e ".[release,gui]"
python -m build
python -m twine check dist/*
```

## Domain rules (do not break)

- Date prefix: `datetime.now().astimezone().strftime("%y%m%d")` + `" - "`.
- Standardize titles: NFKD + strip accents, keep only alphanumerics, join words in
  CamelCase with the first letter uppercase.
- Folder: `<date> - <StandardizedTitle>`; file: `<StandardizedTitle>.md`.
- Sign the `.md` with the standardized title, a blank line, then the creation date as a
  second level heading: `# ItsAlive\n\n## 23/09/2026\n\n` (date via
  `strftime("%d/%m/%Y")`).
- `sign_md_file` only writes into an empty file, so files created by older versions keep
  their original heading.
- Lookup happens before any creation: search the current directory only, for
  `<yymmdd> - <StandardizedTitle>` on **any** date. Subdirectories are not searched, so
  the same title in another directory is a different task and never blocks a new one.
- Resuming a task appends `## <today>` as a new section at the end of the `.md`, unless
  that date is already there. Existing text is never rewritten — only trailing
  whitespace is dropped — and a heading is matched loosely, so `##  05/08/2026 ` counts
  as 05/08/2026.
- Reserved Windows names (`CON`, `PRN`, `AUX`, `NUL`, `COM1-9`, `LPT1-9`) are rejected.
- Open the file with the OS default application (`os.startfile` / `xdg-open`).
- Keep folder/file names ASCII only.

## Conventions

- English code, symbols and documentation.
- `snake_case` functions/variables, `PascalCase` classes, `UPPER_CASE` constants.
- Type hints on public functions; docstrings with `Args:` / `Returns:` / `Raises:`.
- One blank line between top-level definitions; small functions.
- Imports sorted by isort (`ruff check . --fix`).
- Add comments only when they add real value — and **never delete existing comments**
  when editing code.
- Tests in `tests/test_*.py` with pytest; never write to real user folders (`tmp_path`).

## Writing style and tone

Short, direct, declarative prose. No fluff, emojis or exclamations; plain statements.
Bullets are fragments without trailing punctuation.

Commit messages: `<type>: <description>` — lowercase type from
`feat`, `fix`, `docs`, `refactor`, `test`, `ci`, `chore`; one concise line, no trailing
period:
- `docs: update readme`
- `fix: prevent invalid task descriptions`

## Git

- Branch `main`; one topic per branch.
- Commit in the `<type>: <description>` style above.
- Never push without explicit request.
- Line endings normalized to LF (`* text=auto eol=lf` in `.gitattributes`).

## Releases

- Bump `version` in `pyproject.toml` in its own branch, then merge before tagging.
- Tag only commits already in `main`, annotated, message `Release <version>`
  (e.g. `Release v0.2.0`), and push the tag explicitly with `git push origin <tag>`.
- `.github/workflows/release.yml` builds on a `v*` tag push and attaches the
  artifacts to the release. For a tag that predates the workflow, run it manually
  from the Actions tab and fill in the `tag` input.
- Three jobs: `package` builds the sdist and wheel once, `bundle` builds the
  onefile executable per OS, and `release` uploads everything in a single pass, so
  no two jobs touch the same release.
- To fix or republish assets on an existing release, re-run the workflow with the
  same `tag` input. The `release` job uses `--clobber`, so an asset of the same
  name is replaced instead of duplicated.
- The Linux executable is named with the glibc detected at build time, because
  PyInstaller does not bundle it and the binary will not run on older systems.
- GPL-3.0 section 6 requires the corresponding source to travel with a bundled
  executable. The sdist is that source, so never attach an executable without it.

## GUI (`mktsk.gui`)

Optional desktop interface (PySide6) over the same `helpers`/`workers` logic. The CLI
(`mktsk`) and the business logic stay free of Qt imports.

Requirements:

- Pick the base path with a native dialog (`QFileDialog`) or navigate inside the window.
- Navigation: list the folder contents, an up button, a refresh button and
  double-click to enter subfolders or open `.md` files.
- Create the task with the same domain rules as the CLI (lookup on any date, folder/file
  creation, reserved name errors, resuming an existing task).
- Open the created or resumed `.md` with the OS default application.
- Keep the window open and clear the title field after creating.
- Remember the last used path with `QSettings`.
- Show business errors (`TaskError`) in a `QMessageBox`; if opening the file fails, warn
  but never delete what was created.
- UI text, code and symbols in English.
- Entry point: `mktsk-gui`; PySide6 declared as an optional `gui` extra.
- Tests in `tests/test_gui.py` with pytest-qt; `tests/conftest.py` forces
  `QT_QPA_PLATFORM=offscreen` so the suite runs headless.