# Contributing

The conventions for code, tests, commits and releases are in [AGENTS.md](AGENTS.md). This
file covers setting up a machine and the details that depend on it.

## Setup

```bash
python -m venv .venv
python -m pip install -e ".[dev,gui]"
```

The `gui` extra is required even for work outside the GUI, so pyright resolves the Qt
imports.

## Checks

```bash
ruff check .
pyright mktsk/
pytest
```

CI runs the same three on Ubuntu and Windows and fails under 95% coverage.

## Type checking in a local venv

Pyright does not adopt a `.venv` on its own and reports the `PySide6` imports as
unresolved. Spell the interpreter out:

```bash
pyright --pythonpath .venv/bin/python mktsk/          # Linux, macOS
pyright --pythonpath .venv/Scripts/python.exe mktsk/  # Windows, or a Windows venv used from WSL
```

A venv created by Windows Python and used from WSL only has `.venv/Scripts/python.exe`;
`.venv/bin/python` does not exist there. `--venvpath` does not help: pyright looks for a
venv named `venv`, not `.venv`, and has no flag to change the name. CI keeps the plain
`pyright mktsk/`, because the `gui` extra lands in the system interpreter there.

## Tests

- GUI tests run headless: `tests/conftest.py` forces `QT_QPA_PLATFORM=offscreen`, so no
  window opens
- Each test has a 30 second timeout (`pytest-timeout`). When a run times out, find the
  blocking test with `pytest -x -v` rather than re-running the whole suite
- On Windows a timed-out run can leave `python.exe` processes behind that hold files in
  `tmp_path` open; end them before the next run

## Images

- Tests assert state and geometry first. When only pixels prove a behaviour, render the
  widget in-process to a `QImage` with `tests/gui_helpers.render_row` or
  `row_background`; tests never write image files
- No screenshots or probe images in the repository root
- The README images live in `docs/images/` and use placeholder data only: no real task
  titles, paths or names. Recapture them when the GUI changes visibly, and keep the GIF
  small (under about 300 KB)
