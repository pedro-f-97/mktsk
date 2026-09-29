# AGENTS.md

Instructions for AI agents (and humans) working in this repository.

## Project

`mktsk` is a small Python CLI that creates task folders with a `YYMMDD - TaskName`
naming convention and an associated Markdown file, opened automatically.

## Structure

- `mktsk/main.py` — CLI entry point (`argparse`), orchestrates the flow.
- `mktsk/helpers.py` — OS helpers: name validation, reserved Windows names, opening files.
- `mktsk/workers.py` — task logic: title standardization, folder/file creation, signing.
- `tests/` — pytest test suite.
- `pyproject.toml` — packaging, dependencies and tooling configuration.

## Commands

```bash
python -m pip install -e ".[dev]"
ruff check .
pyright mktsk/
pytest
```

CI runs `ruff check .`, `pyright mktsk/` and `pytest` (coverage ≥ 95% enforced).

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