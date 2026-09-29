# AGENTS.md

Instructions for AI agents (and humans) working in this repository.

## Project

`mktsk` is a small Python CLI that creates task folders with a `YYMMDD - TaskName`
naming convention and an associated Markdown file, opened automatically. An optional
PySide6 desktop GUI (`mktsk-gui`) offers the same workflow interactively.

## Structure

- `mktsk/main.py` — CLI entry point (`argparse`), orchestrates the flow.
- `mktsk/gui.py` — PySide6 desktop interface over the same logic.
- `mktsk/helpers.py` — OS helpers: name validation, reserved Windows names, opening files.
- `mktsk/workers.py` — task logic: title standardization, folder/file creation, signing.
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

## Domain rules (do not break)

- Date prefix: `datetime.now().astimezone().strftime("%y%m%d")` + `" - "`.
- Standardize titles: NFKD + strip accents, keep only alphanumerics, join words in
  CamelCase with the first letter uppercase.
- Folder: `<date> - <StandardizedTitle>`; file: `<StandardizedTitle>.md`.
- Sign the `.md` with the raw title exactly as typed (`# It's Alive!`).
- Reserved Windows names (`CON`, `PRN`, `AUX`, `NUL`, `COM1-9`, `LPT1-9`) are rejected.
- Collision: never duplicate or overwrite — open the existing `.md`.
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

## GUI (`mktsk.gui`)

Optional desktop interface (PySide6) over the same `helpers`/`workers` logic. The CLI
(`mktsk`) and the business logic stay free of Qt imports.

Requirements:

- Pick the base path with a native dialog (`QFileDialog`) or navigate inside the window.
- Navigation: list the folder contents, an up button, a refresh button and
  double-click to enter subfolders or open `.md` files.
- Create the task with the same domain rules as the CLI (folder/file creation, reserved
  name errors, collision opening the existing `.md`).
- Open the created `.md` with the OS default application.
- Keep the window open and clear the title field after creating.
- Remember the last used path with `QSettings`.
- Show business errors (`TaskError`) in a `QMessageBox`; if opening the file fails, warn
  but never delete what was created.
- UI text, code and symbols in English.
- Entry point: `mktsk-gui`; PySide6 declared as an optional `gui` extra.
- Tests in `tests/test_gui.py` with pytest-qt; `tests/conftest.py` forces
  `QT_QPA_PLATFORM=offscreen` so the suite runs headless.