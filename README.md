# mktsk

CLI tool and desktop GUI for quickly setting up task folders.

## Features

* Creates task folders using the `YYMMDD - TaskName` naming convention.
* Creates an associated Markdown file.
* Adds the task title to the Markdown file, as a heading, followed by the task date.
* Finds an existing task by title in the current directory, on any date, and starts a new
  dated section in it.
* Can be run from any directory.
* Optional desktop GUI (`mktsk-gui`) for the same workflow.

## Installation

From the project directory:

```bash
python -m pip install .
```

For development:

```bash
python -m pip install -e .
```

The desktop GUI requires the optional `gui` extra (PySide6):

```bash
python -m pip install ".[gui]"
```

For development with the GUI (including its tests):

```bash
python -m pip install -e ".[dev,gui]"
```

## Usage

Run:

```bash
mktsk It's Alive!
```

Creates:

```text
260923 - ItsAlive/
└── ItsAlive.md
```

The Markdown file contains:

```markdown
# ItsAlive

## 23/09/2026

Your notes go here.
```

The task folder is created in the directory from which `mktsk` is executed.

The Markdown file is then automatically opened with the system's default application.

Titles that normalize to an empty name, or to a Windows reserved name (`CON`, `PRN`, `AUX`,
`NUL`, `COM1-9`, `LPT1-9`), are rejected with an error.

## Returning to a task

The title is looked up before anything is created, on **any** date. Running the same
command again days later picks up the task you already have:

```bash
mktsk It's Alive!
```

```text
Opened: 260923 - ItsAlive (added ## 30/09/2026)
```

No new folder is created. A second level heading with today's date is appended as a new
section at the end of the existing Markdown file, so each day you work on a task keeps
its own notes:

```markdown
# ItsAlive

## 23/09/2026

Your notes go here.

## 30/09/2026

```

Running it twice on the same day does not add a second heading for that date. Your text
is never rewritten; only trailing whitespace is dropped.

The search stays in the directory you run `mktsk` from, so with this layout:

```text
tasks/
├── 260923 - ItsAlive/
├── Veritas/
│   └── 260925 - FSociety/
└── SteelMountain/
    └── 260924 - Everbind/
```

`mktsk It's Alive!` from `tasks/` picks up `260923 - ItsAlive`, while `mktsk F Society`
from there creates `tasks/260930 - FSociety`, because the Veritas one lives in another
directory. To resume a task, run the command from the directory that holds it.

## Renaming a task

Pass `--rename` with the name of the task folder and the title you want instead:

```bash
mktsk --rename "260923 - ItsAlive" "It's Still Alive"
```

```text
Renamed: 260923 - ItsStillAlive
```

The date stays, so the task keeps its place in the history, and only the `#` heading at
the top of the file is rewritten. The notes are left exactly as they were, and the file
is not opened, because renaming is not working on the task.

The folder is named rather than looked up by title, so the task you name is the task you
rename. A name that is not a task folder is refused, as is a new title that is empty, a
Windows reserved name, or one another task already has.

A task title belongs to one task in a directory, so two tasks with the same title should not
be sitting in the same category, and renaming is refused rather than allowed to make it so.
The same title in a different category is a different task, and that is fine.

## Listing tasks

Pass `--list` to see what is there, without opening anything:

```bash
mktsk --list
```

```text
tasks/
  23/09/2026  Its Alive
  18/09/2026  F Society
Able/
  19/09/2026  Foo
Veritas/
  24/09/2026  F Society Everbind
```

Each directory is a heading, the one you are in first, and the tasks under it read the
same way the GUI shows them: the date, two spaces, then the title read as words
(`FSocietyEverbind` shows as `F Society Everbind`). Newest first inside each directory,
and the directories themselves in alphabetical order.

A task folder without its Markdown file is left out, since there is nothing to open.

## Creating a category

Pass `--new-category` with a name, and the folder is made in the directory you are in:

```bash
mktsk --new-category "Produção"
```

```text
Created: /home/you/tasks/Producao
```

A category is a plain folder for keeping tasks apart, not a task, so its name is only
stripped of accents (`Produção` becomes `Producao`) and is otherwise left as you typed
it, spaces and punctuation included. A name that is already there is not an error, since
the point is to have the folder rather than to be the first to make it.

The name is refused when it is empty, hidden, looks like a task folder (`260918 - Foo`), or
carries anything Windows refuses in a name. That last rule is checked on every platform,
not just Windows, so a category you create on Linux is still one you can open on Windows.
It covers a Windows reserved name (`con`, and also `con.txt`, because Windows reserves the
name before the extension), a path separator, a character from `<>:"/\|?*`, and a name
ending in a dot or a space, which Windows drops.

Then create tasks inside it by running `mktsk` from there, and `--list` will show them
under its own heading.

## Migrating existing task files

The Markdown of a task is moving to a format without the `#` title heading, with each
visit dated by a first level heading instead of a second level one. To convert the tasks
you already have, run the migration over the folder that holds them:

```bash
python -m mktsk.migration ~/tasks
```

It walks the folder and its immediate subdirectories, finds every task in it and shows
what it would do, one file at a time, without writing anything:

```text
260918 - SupplierReply/SupplierReply.md: migrated
--- 260918 - SupplierReply/SupplierReply.md
+++ 260918 - SupplierReply/SupplierReply.md
@@ -1,6 +1,4 @@
-# SupplierReply
-
-## 18/09/2026
+# 18/09/2026
 
 Customer request, see attachment.
 
Summary: 1 migrated, 0 already new, 0 to review, 0 failed
```

The status of each file is one of:

* `migrated`: the file was converted;
* `already new`: the file is already in the new format, and nothing was changed;
* `review`: the file was converted, and something in it needs your eye, printed under
  the status. A heading naming another task, or a `##` that carries no date, stays where
  it is;
* `error`: the file could not be read or written, and the run carried on without it.

Once you have read the diff, zip the folder and apply the migration:

```bash
python -m mktsk.migration ~/tasks --apply
```

Each file is written through a temporary one in the same folder, so an interruption
never leaves one of them half converted, and the line breaks each file was written with
are kept. Running the migration again over the same folder reports every file as
`already new`.

## Desktop GUI

Launch with:

```bash
mktsk-gui
```

Or as a module:

```bash
python -m mktsk
```

Opens a window where you can:

* pick a base folder with the native file dialog or navigate inside the window;
* see on the left the current folder and its subfolders;
* create a subfolder with the `+` at the right of the `Directory` heading. The name has no
  accents (`Produção` becomes `Producao`), and a folder that is already there is opened
  rather than refused. The new folder is left selected, so the task you type next lands
  inside it;
* create a task in a subfolder by selecting it on the left, without opening it. A quiet
  note beside the title field says which subfolder the task will land in, and stays on it
  until you select another one;
* see on the right every existing task, including the ones in subfolders. Each category
  gets its own tab, the current folder included, plus an `All` tab that lists everything
  under a heading per category. Newest first, with the date as `dd/mm/yyyy` and the
  title read as words (`260923 - FSocietyEverbind` shows as `23/09/2026  F Society
  Everbind`);
* create a task with the same rules as the CLI, opening the resulting Markdown file with
  the default application;
* act on an existing task by selecting it, which brings a bar of buttons over its row.
  The room for the buttons appears only on the row you clicked:
  * `Open` reveals the task folder in the file manager, without touching the task;
  * `Resume` adds a section for today, wherever the task lives, and opens it;
  * `Rename` asks for a new title, renames the folder and the file keeping the date, and
    rewrites the `#` heading at the top of the file. The body is left alone, and a title
    another task already has is refused.

  The buttons show an icon each, and the name of the action on hover.

The last visited folder is remembered between sessions.

## Standalone executable

Release builds include a single-file executable of the GUI, for people who do not
want to install Python:

* `mktsk-gui-windows-x64.exe` for Windows;
* `mktsk-gui-linux-x86_64-glibc<version>` for Linux, named after the glibc it was
  built against.

The first launch unpacks the executable to a temporary folder, so it takes a
few seconds. The executables are not code signed, so antivirus software may
report them.

The source distribution (`mktsk-*.tar.gz`) attached to the same release is the
corresponding source for these executables, as required by GPL-3.0 section 6.

## Tests

Run with:

```bash
pytest
```

The project maintains high test coverage (95%+ enforced in CI).

## License

GPL-3.0-or-later. See [LICENSE](LICENSE).

