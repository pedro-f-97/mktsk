# AGENTS.md

Instructions for AI agents (and humans) working in this repository.

## Project

`mktsk` is a Python CLI that creates task folders named `YYMMDD - TaskName` with an
associated Markdown file, opened automatically. `mktsk-gui` (PySide6) offers the same
workflow interactively.

## Simplicity first

- Before implementing a fix, state in one line the simplest change that could work (for example, one palette role or one style flag) and why it is or is not enough. Prefer it.
- Do not add caches, probing/rendering of the style, new abstractions or new helper layers for a UI fix unless the simple change was tried and shown to fail; then report the evidence.
- If a fix grows beyond about 40 lines of production code or needs more than one new helper, stop and report before continuing: say what was tried, what failed, and what the simple alternative would cost.
- Tests prove the behaviour with the least machinery that reproduces it. Do not build test infrastructure larger than the code it covers.

## Docs

Read the matching one before editing the module it covers.
- `docs/DOMAIN.md` — domain rules (do not break)
- `docs/FORMAT.md` — the `.md` format
- `docs/CLI.md` — the CLI
- `docs/GUI.md` — the GUI

## Structure

`mktsk/` — CLI and domain logic, without Qt.
`mktsk/gui/` — PySide6, one module per responsability.

Run `tree mktsk/ tests/` or read the module docstrings for the layout.

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

- Run `pytest -x`, never piped through `tail` or `head`. A command that times out is never
  repeated unchanged: find which test blocks first with `-x -v`, then fix or report it.
  After a timeout, look for leftover `python.exe` processes before the next run

Inside the local venv, pyright needs the interpreter spelled out, because it does not
adopt the `.venv` on its own and reports three unresolved `PySide6` imports:

```bash
pyright --pythonpath .venv/Scripts/python.exe mktsk/
```

On Linux the path is `.venv/bin/python`. CI keeps the plain `pyright mktsk/`, where the
`gui` extra lands in the system interpreter that pyright already resolves. `--venvpath`
does not help: pyright looks for a venv named `venv`, not `.venv`, and has no flag to
change the name.

## Conventions

- English code, symbols, docs and example data; test data uses placeholders
- `snake_case` functions and variables, `PascalCase` classes, `UPPER_CASE` constants
- Type hints on public functions; docstrings with `Args:` / `Returns:` / `Raises:`
- Small functions; imports sorted by isort (`ruff check . --fix`)
- Two blank lines between top-level definitions, no whitespace on a blank line, and a
  newline at the end of the file. `W` and the `E3xx` rules enforce it from `pyproject.toml`,
  where `preview` is on because the `E3xx` rules are still preview. `preview` drops seven
  stable `DTZ` rules, `DTZ007` among them, so `DTZ` is listed explicitly and the two
  `# noqa: DTZ007` in `standards.py` are load-bearing: `RUF100` will report them as unused
  the moment the config stops selecting `DTZ007`
- Keep the ruff `select` and `extend-select` out of each other's way: a `select` next to
  `extend-select` cuts the default families back to `E`, `F` and `W`
- Comment only when it adds value; never delete existing comments
- Tests in `tests/test_*.py`; never write to real user folders (`tmp_path`)
- One test file per subject, named after it (`test_gui_listing.py`, `test_gui_target.py`,
  `test_gui_header.py`, `test_gui_actions.py`, `test_gui_create.py`, `test_gui_window.py`);
  a file that grows past a few hundred lines is split, never extended
- Fixtures go in `tests/conftest.py`; the plain helpers shared across GUI test files live
  in `tests/gui_helpers.py` and are imported as `from tests.gui_helpers import ...`, because
  `tests/__init__.py` makes `tests/` a package
- Private names the tests need are imported from the module under test, never redefined,
  so a change in `mktsk/` cannot be papered over by a stale copy in the tests

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
