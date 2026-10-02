# AGENTS.md

Instructions for AI agents (and humans) working in this repository.

## Project

`mktsk` is a Python CLI that creates task folders named `YYMMDD - TaskName` with an
associated Markdown file, opened automatically. `mktsk-gui` (PySide6) offers the same
workflow interactively.

## Structure

- `mktsk/main.py` — CLI entry point
- `mktsk/gui/` — PySide6 interface, one module per responsibility: `__init__.py` is the
  entry point and re-exports `MainWindow` and `main`, `__main__.py` runs it with
  `python -m mktsk.gui`, `icons.py` draws the icons, `tree.py` is the directory tree,
  `listing.py` the tasks of a category with the action bar over the selected row, and
  `window.py` the main window
- `mktsk/__main__.py` — module entry point and PyInstaller target; keep the absolute
  import, relative imports fail once frozen
- `mktsk/helpers.py` — name validation, reserved Windows names, opening files, the
  date format the CLI and the GUI share
- `mktsk/standards.py` — the rules of a task name: standardization, recognition of
  the folder shape, reading a title back. No I/O
- `mktsk/files.py` — everything that writes: creating the folder, creating the
  `.md`, appending a dated section, creating a category
- `mktsk/listing.py` — everything that reads a directory: finding, listing,
  grouping, and the activity of each task
- `mktsk/tasks.py` — the verbs the CLI and the GUI call: create or open, resume,
  rename
- `mktsk/parsing.py` — reads the text of a `.md` in the new format: interventions,
  state events, last activity. Pure functions, no I/O
- `mktsk/migration.py` — converts the text of a `.md` from the old format to the
  new one, and the command line that applies it to a tree of tasks
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
- The `.md` carries no title: the folder and the file name say which task it is. A new one is
  born with `# <dd/mm/YYYY>` from `strftime("%d/%m/%Y")` and a blank line, so the body can be
  typed straight away. Nothing is ever rewritten or dropped to make room for it
- The title of a task is unique within its directory, or category, so a lookup by title is
  unambiguous there. Lookup runs before any creation, in the current directory only, and
  ignores the date: `260918 - Foo` is what `mktsk Foo` resumes weeks later. The same title
  in another directory is a different task, and that is what makes it legitimate. The
  comparison ignores the case, because `standardize_string` lowers the capitals inside a
  title and a folder renamed by hand keeps them, so pasting a folder name into the terminal
  has to reach the task it names rather than create a second one
- The `.md` of a task is always named after the title its folder carries, so `_resume_task`
  reads that title out of the folder name and hands it to `create_md_file`. A folder renamed
  by hand keeps the capitals of its own name, and the normalized title would otherwise point
  at a `.md` that does not exist
- Renaming to a title the directory already holds is refused, on any date and in any case, so
  `rename_task` cannot be the way to end up with two of one title. It passes `exclude` so the
  folder it is renaming never clashes with itself over the case alone. A folder copied by
  hand, or restored from a backup, can, and `find_task_folder` then takes the most recent
  rather than whichever came first out of `iterdir()`
- Resuming appends `# <today>` at the end of the `.md`, after a blank line, unless
  `parse_task` already shows an intervention for that date; a file with nothing in it is
  dated instead of appended to. The section never rewrites the body, only trailing whitespace
  is dropped, and the date is recognised the way the parser reads it, so a heading written by
  hand in another of the accepted forms, with stray spacing or inside a code block, counts
- A `.md` in the old format is refused rather than read: `append_date_section` raises
  `TaskError` naming the file and `python -m mktsk.migration`, and nothing is written, so the
  migration can still convert it. `is_legacy` is what recognises one
- `resume_task(folder, title)` resumes the folder it is given, wherever that folder
  lives; unlike `open_or_create_task`, it does no lookup and takes no directory
- `rename_task(folder, title, raw_title)` keeps the date prefix and renames the `.md` and the
  folder, names only: the content is never read and never written, because the title of a
  task is not inside the file any more. Renaming to the title the task already has does
  nothing
- `rename_task` undoes a step that fails, in reverse, so it never leaves the task as
  `260918 - OldTitle/NewTitle.md`
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
- `TaskEntry` carries two dates: `date` is the one in the name of the folder, the day the task
  was created, and `last_activity` is the one the `.md` knows. The listing reads every `.md`
  with `parse_task`, and `interventions` is how many interventions it found. `last_activity`
  falls back to the folder date when the file is in the old format, when it carries no
  intervention, or when it cannot be read, and `interventions` is then 0: a task is still a
  task when nothing can be read out of it. An old file is never read as the new one, so a
  dated heading a conversion left in the body is content rather than a visit. A `.md` that
  cannot be read never brings the listing down, the same rule as a directory that cannot be
  read
- Tasks of a category are listed by `last_activity`, newest first, and alphabetical for tasks
  of the same last activity. Coming back to a task moves it to the top, whichever day it was
  created
- Reading a title back for display (`readable_title`): every uppercase letter starts a
  word and a digit starts one too, so `FSocietyEverbind` reads as `F Society Everbind`
  and `Task2` as `Task 2`; consecutive digits stay together, so `2026` survives

## The new .md format

This is the format mktsk writes: `files.append_date_section` writes it and reads it
back with `mktsk/parsing.py`, and `mktsk/migration.py` converts a file that was
written in the old one, a `# <StandardizedTitle>` heading and a
`## <dd/mm/YYYY>` heading per visit. The plan the steps come from is in
`PLAN.md`.

```markdown
# 18/09/2026

Customer request, see attachment.

## Problem

Free text, with levels 2 to 6 available.

# 02/10/2026

[mktsk:2026-09-18T10:02]: # "open"
[mktsk:2026-10-02T09:40]: # "in-progress"
```

- No `# <title>`: the folder and the `.md` name say which task it is
- `STATES` is `("open", "in-progress", "waiting", "closed")`
- An intervention is a level 1 heading: a single `#`, a space and up to three spaces of
  indentation, so `#hashtag` and `## 12/01/2026` are not one. Its line holds a date and
  may hold text after it (`# 29/09/2026 - reply`), and the first valid date of the line
  is the one that counts
- `dd/mm/yyyy` is the canonical form and `DATE_FORMAT` is what a writer uses; `dd-mm-yyyy`,
  `dd.mm.yyyy`, `dd/mm/yy` and `yyyy-mm-dd` are only tolerated when reading, and a two
  digit year means 2000 plus the year. A date glued to another number is not a date, which
  is what keeps `2026-10-02` from being read as the `26-10-02` inside it
- A date that never happened is not a date, so `# 31/02/2026` is a heading like any
  other and not an intervention
- A state event is a whole line `[mktsk:YYYY-MM-DDTHH:MM]: # "state"`, local time with no
  zone, anywhere in the file. mktsk writes them in a block at the end, after a blank line,
  or Markdown renders them as text. The last event in file order is the current state; an
  event that cannot be read is left out and never an error, because a hand edited file is
  still a task file
- `last_activity` is the most recent date of the interventions, not the last one in the
  file, and `None` when there are none
- Code blocks (``` and `~~~`, closed with the same character) are ignored everywhere, so a
  date or an event written in an example is not one of the task. A fence that is never
  closed runs to the end of the file
- A file may start with a utf-8 byte order mark, which `utf-8` reads as U+FEFF rather than
  taking off, and a mark is not text: left in place it hides the first heading from
  `parse_task`, `is_legacy` and the migration. `parsing.without_bom` takes it off, and it is
  the one place that does, so every reader goes through it. Nothing that writes adds a mark
  or takes one away, so a file keeps the one it was written with, and the migration puts it
  back in front of what it writes
- `is_legacy` recognises the old format: the first non-empty line is a level 1 heading
  with no date on it, and the file has a level 2 heading with a date. It is never read as
  the new one, so the title is not mistaken for an intervention
- `parse_task` takes text, not a `Path`, so it never opens anything, and it accepts either
  line break. `line` is the line of the file, counting from 1, code blocks included

## The migration

- `python -m mktsk.migration <folder>` walks a folder and its immediate subdirectories, like
  `find_task_groups`, so only the tasks `is_task_folder` recognises are converted, each through
  the `.md` named after the title of its folder. Without `--apply` it prints the status of
  every file and its unified diff, and writes nothing; with `--apply` it writes each file and
  first says to keep a backup
- The order is the one to hand to the person running it: zip the folder, simulate, read the
  diff, then apply
- The status of a file is `migrated`, `already new` or `review`, and `review` wins over the
  other two: a file with something to look at in it is the one a person has to read
- A file that cannot be read or written is reported and the run goes on to the next one, and
  the exit code is 1 when any of them failed
- Files are read and written with `newline=""`, so a file keeps the line break it was written
  with
- A write goes to a `.<name>.md.part` beside the file and is renamed over it with
  `os.replace`, so a failure halfway leaves the original as it was and the temporary file is
  removed
- `migrate_content(content, title)` is pure and idempotent: a file already in the new format
  comes back the way it went in, with nothing to review
- It drops the leading `# <title>` when the heading names the title of the folder, comparing
  the case apart, because a folder renamed by hand keeps its capitals. A heading naming
  another task is content rather than the identity of this one, so it stays and is reported
- It turns each `## <date>` into `# <date>` and moves the headings of level 3 to 6 under it up
  one level, and the first `# <date>` it finds closes that section, so the notes of an
  intervention that was already written are left alone
- A `##` carrying no date under a section it did not date stays where it is and goes into
  `review`, which is what the status of the file then says
- Code blocks are the ones `parsing._readable_lines` leaves out, so an example is never
  converted, and the result always ends with a single line break

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
  its tasks under it. A row is `_task_label`: `DATE_FORMAT`, two spaces,
  `readable_title`, then two spaces and `(3 interventions, last activity 18/09/2026)`,
  with `intervention` in the singular for one. The first three are the row the GUI shows;
  the count and the activity are CLI only, until the GUI shows them too. The order is the
  one `find_task_groups` already gives, which is by last activity, so a directory with no
  tasks prints nothing. Never format a date or a title in the CLI by hand, or the two
  listings drift apart
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
- One module per responsibility, and a widget never takes over from its neighbour: the
  window imports the widgets it is built from, and a widget only reports what it was
  asked for, so new code goes in the module that matches what it does
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
- Within a category, by last activity, newest first, alphabetical for tasks of the same
  last activity. The row still shows the date of the folder, so the date on a row and the
  order of the rows can disagree, until the GUI shows the activity too
- A task folder with no `.md` is not listed; a task two levels down is not found
- A task label is `dd/mm/yyyy` + two spaces + `readable_title`, with the full path as
  tooltip
- Selecting a task shows an action bar over that row, aligned to the left, with the
  `Open`, `Resume` and `Rename` buttons; it moves with the selection and disappears with
  it
- The buttons carry an icon and a tooltip, never a text label; the icons are a folder for
  `Open`, a plus for `Resume` and a pencil for `Rename`, all drawn with `QPainter` in
  `gui/icons.py`, so no image file has to be collected for a frozen build
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
  `test_gui_header.py`, `test_gui_actions.py`, `test_gui_create.py`, `test_gui_window.py`,
  `test_migration.py`); a file that grows past a few hundred lines is split, never extended
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
