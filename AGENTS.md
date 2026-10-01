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

Inside the local venv, pyright needs the interpreter spelled out, because it does not
adopt the `.venv` on its own and reports three unresolved `PySide6` imports:

```bash
pyright --pythonpath .venv/Scripts/python.exe mktsk/
```

On Linux the path is `.venv/bin/python`. CI keeps the plain `pyright mktsk/`, where the
`gui` extra lands in the system interpreter that pyright already resolves. `--venvpath`
does not help: pyright looks for a venv named `venv`, not `.venv`, and has no flag to
change the name.

## Domain rules (do not break)

- Date prefix: `datetime.now().astimezone().strftime("%y%m%d")` + `" - "`
- Standardize titles: NFKD, strip accents, keep only alphanumerics, join words in
  CamelCase with the first letter uppercase. An apostrophe is not a separator: it is
  dropped before the split, so a contraction stays one word and `It's Alive!` gives
  `ItsAlive`, not `ItSAlive`. Both `'` and `’` are dropped. Every other non-alphanumeric
  still separates, so `Sigur Rós` gives `SigurRos` and `bJÖrk_naÏve-fAçAde!!` gives
  `BjorkNaiveFacade`
- Folder: `<date> - <StandardizedTitle>`; file: `<StandardizedTitle>.md`
- Sign an empty `.md` with `# <StandardizedTitle>`, a blank line, then `## <dd/mm/YYYY>`
  from `strftime("%d/%m/%Y")`, and a blank line. A `.md` whose leading heading is not
  `# <StandardizedTitle>` gains the missing heading at the start and keeps everything
  below it, so content from another task, in a folder copied by hand or restored from a
  backup, is never mistaken for the identity of this one. Nothing is ever rewritten or
  dropped; `sign_md_file` returns whether it dated a file that had no date of its own
- The title of a task is unique within its directory, or category, so a lookup by title is
  unambiguous there. Lookup runs before any creation, in the current directory only, and
  ignores the date: `260918 - Foo` is what `mktsk Foo` resumes weeks later. The same title
  in another directory is a different task, and that is what makes it legitimate
- Renaming to a title the directory already holds is refused, on any date, so `rename_task`
  cannot be the way to end up with two of one title. A folder copied by hand, or restored
  from a backup, can, and `find_task_folder` then takes the most recent rather than
  whichever came first out of `iterdir()`
- Resuming signs first, then appends `## <today>` at the end of the `.md` unless that
  date is already there; the dated section never rewrites the body, only trailing
  whitespace is dropped; headings are matched loosely, so `##  05/08/2026 ` counts as
  05/08/2026. Signing a file that had nothing in it dates it, so the append is skipped
  for that file, which is the only case in which resuming adds no dated section
- `resume_task(folder, title)` resumes the folder it is given, wherever that folder
  lives; unlike `open_or_create_task`, it does no lookup and takes no directory
- `rename_task(folder, title, raw_title)` keeps the date prefix, renames the folder and
  the `.md`, and rewrites only the first non-empty line, and only when it is exactly
  `# <old title>`; a heading it does not recognise, and everything after it, is left
  alone; renaming to the title the task already has does nothing
- `rename_task` undoes a step that fails, in reverse, so it never leaves the task as
  `260918 - OldTitle/NewTitle.md` nor with a heading that disagrees with its folder.
  The `.md` is read before anything moves, so a later failure can put it back
- `rename_task` raises `TaskError` on an empty title, a reserved Windows name, a missing
  `.md` or a title another task of the same directory already has; it renames the `.md`
  before the folder, or the old file path stops resolving
- `task_folder_title(name)` returns the standardized title a task folder name carries, or
  None when the name is not a task folder; it is how the CLI reads the current title of a
  folder the user named, so the CLI never has to know how the name is split
- `is_task_folder(name)` is a shape check: a real `%y%m%d` date, ` - `, then an ASCII
  alphanumeric title that does not start with a lowercase letter (`2026` counts) and is
  not a Windows reserved name. The date prefix keeps `261001 - CON` out of the reserved
  set as a folder name, but the `.md` inside it would be `CON.md`, so a title the shape
  check accepted would still be one that cannot be opened
- `standardize_string` is not idempotent (`BigWord` becomes `Bigword`); never test
  `standardize_string(title) == title`
- Lookup uses `is_task_folder`; a folder that fails the check is never resumed, and the
  new task is created beside it
- Reject reserved Windows names (`CON`, `PRN`, `AUX`, `NUL`, `COM1-9`, `LPT1-9`) on the
  stem, so `con.txt` and `com1.log` are as reserved as `con`. `create_md_file` checks
  it, because the `.md` of a title is as reserved as the title, which covers
  `resume_task` on a folder copied by hand, where no lookup ever ran; `open_or_create_task`
  and `rename_task` check the title as well. `create_folder` does not, and is not the
  place for the rule: it never receives a bare title, and a task folder name carries a
  date prefix, which keeps `261001 - CON` out of the reserved set
- `create_category(location, raw_name)` makes a plain subdirectory, not a task folder, so
  it does not call `standardize_string`: it folds the accents out (`Produção` becomes
  `Producao`) and leaves the case, the spacing and the punctuation alone; it raises
  `TaskError` on a name that is empty, cannot be made ASCII, carries a path separator, is
  reserved, starts with `.` or looks like a task folder (`260918 - Foo`), because any of
  those would be missing from the listing; a name that is already there is not an error.
  It also refuses `_reserved_task_title`, which is what `is_task_folder` now rejects, so a
  category cannot take the name a task folder would have had; a folder like that is a plain
  directory, visible in the tree, rather than a task and a category that neither open
- `validate_name` uses the Windows rules on every platform, because Windows is the
  strictest of the two and a name it takes is taken everywhere: a character from
  `<>:"/\|?*`, a control character, a name that is empty or only spaces, a name that is not
  a single component, or one that ends in a dot or a space, which Windows drops. The
  emptiness check comes first, so `""` and `"   "` give the same message rather than `"   "`
  being refused as a trailing space, which it also is. It must never let the platform decide,
  so it never uses `Path`, which follows the system we are on and takes `C:\foo` for a
  single name on Linux. Refuse with `TaskError`, not with the `OSError` of the machine:
  an `OSError` from `mkdir` is `[WinError 267]` on Windows and nothing on Linux
- Reserved names are checked on the stem, so `con.txt` and `com1.log` are as reserved as
  `con`
- `standardize_string` and `create_category` share `_without_accents` for the NFKD folding,
  so the accent removal is only implemented once
- Open files and folders with the OS default application: `os.startfile` on Windows,
  `xdg-open` on Linux when it is there, `gio open` otherwise
- Folder and file names are ASCII only
- Reading a title back for display (`readable_title`): every uppercase letter starts a
  word and a digit starts one too, so `FSocietyEverbind` reads as `F Society Everbind`
  and `Task2` as `Task 2`; consecutive digits stay together, so `2026` survives

## CLI

- `mktsk <title>` creates or resumes the task and opens its `.md`
- The title is `nargs="*"`, not `nargs="+"`, because the options take arguments of their
  own; `parse_arguments` then checks what each option was given and calls
  `parser.error()`, so a missing argument still exits with code 2. Do not let that check
  be skipped, or `mktsk` with no arguments creates a folder instead of failing
- `--rename <folder> <new title>` takes the name of the task folder, not a title to look
  up, so the task you name is the task you rename; everything after the folder is the new
  title, which is why a title of several words needs no quoting. It prints the message and
  does not open the `.md`, because renaming is not working on the task
- `--list` takes no title and opens nothing; it prints each directory as a heading and
  its tasks under it, formatted the way the GUI shows them, which is `DATE_FORMAT`, two
  spaces and `readable_title`. The order is the one `find_task_groups` already gives, so
  a directory with no tasks prints nothing. Never format a date or a title in the CLI by
  hand, or the two listings drift apart
- `--new-category <name>` creates a category in the current directory and prints the path;
  it opens nothing, because making somewhere to put tasks is not working on one. The name
  is one argument, so a name with spaces in it has to be quoted, unlike a task title or a
  new title for `--rename`. It refuses to go with `--rename` or `--list`
- Each option checks only what it needs, and only the plain form falls back to the title;
  when a second option arrives alongside, the refusal is about the two options, not about
  the title

## GUI

- Entry point `mktsk-gui`; PySide6 comes in the optional `gui` extra; tests in
  `tests/test_gui_listing.py`, `tests/test_gui_target.py`, `tests/test_gui_header.py`,
  `tests/test_gui_actions.py`, `tests/test_gui_create.py` and `tests/test_gui_window.py`
  with pytest-qt
- No Qt imports in the CLI or the business logic
- Two panes in a `QSplitter`: a `QTreeWidget` on the left holding the current directory
  and its immediate subdirectories, so it shows where new tasks are created; a
  `QTabWidget` on the right holding one `QListWidget` per task category
- The tree lists folders only, one level deep, and never task folders or hidden
  directories (`list_subdirectories`); double-clicking a subdirectory navigates to it
  and the root does nothing
- A directory that cannot be read holds nothing and is left out rather than raising, so
  `_tasks_in` and `list_subdirectories` both return nothing for one and `find_task_groups`
  lists the categories it can read; this is why `refresh` in the GUI needs no `try` around
  `_reload_tree`, and it is also why a locked directory disappears instead of complaining
- A `+` button sits at the right end of the `Directory` header row and creates a category
  in the current directory (`create_category`); the button is a child of the header widget
  and is placed by arithmetic against the header size, because
  `QHeaderView.sectionViewportGeometry` is missing from the PySide6 stubs
- The button is squared off to the header height, so it cannot overflow the row, and
  carries an icon and a tooltip like every other button in the window
- A new category is left selected, so it becomes the creation target at once; a category
  that is already there is not an error, it is just selected
- A subdirectory selected in the tree is where a new task is created
  (`creation_directory`), so a task lands in a category without entering it; the root,
  or nothing selected, makes the current directory the target; selecting does not
  navigate and does not change the active tab
- The tree selection survives a refresh, so a second task lands in the same category; a
  selected category that is no longer there is dropped and the current directory takes
  over
- Lookup for a title runs in the target directory, not in the current one, so the same
  title in another directory is still a different task
- A hint beside the title field reads `New tasks in <category>`, shown only when the
  target is not the current directory; it sits between the title field and the `Create`
  button, in the same font and only the colour tells it apart, so it adds no height, and
  the full path is its tooltip
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
- Selecting a task shows an action bar over that row, aligned to the left, with the
  `Open`, `Resume` and `Rename` buttons; it moves with the selection and disappears with
  it
- The buttons carry an icon and a tooltip, never a text label; the icons are a folder for
  `Open`, a plus for `Resume` and a pencil for `Rename`, all drawn with `QPainter` in
  `gui.py`, so no image file has to be collected for a frozen build
- The bar only ever sits on a task row; a heading is not selectable, and `TaskListing`
  checks the item holds a `TaskEntry` before showing or placing the bar
- Only the selected row is inset to make room for the bar, so the space appears when the
  row is clicked and is given back when the selection goes; every row keeps the height
  the bar needs, or the list would shift as the selection moves
- `Open` replaces the double click on a task; `Open` reveals the task folder in the file
  manager and touches nothing, `Resume` opens the `.md`, `Rename` does not open it, it
  just refreshes the list
- `Resume` is the only browse action that appends a date, and it appends it to the task
  it was asked for, not to one looked up in the current directory
- Remember the last path with `QSettings`
- Show `TaskError` in a `QMessageBox`; if opening the file fails, warn but never delete
  what was created; the warning carries the error as it is, `helpers.open_file` already
  words it, so the path is never hidden behind a duplicated prefix
- Keep the window open and clear the title field after creating

## Conventions

- English code, symbols, docs and example data; test data uses placeholders
- `snake_case` functions and variables, `PascalCase` classes, `UPPER_CASE` constants
- Type hints on public functions; docstrings with `Args:` / `Returns:` / `Raises:`
- Small functions; imports sorted by isort (`ruff check . --fix`)
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
