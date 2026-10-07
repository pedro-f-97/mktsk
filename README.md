# mktsk

CLI tool and desktop GUI for quickly setting up task folders.

## Features

* Creates task folders using the `YYMMDD - TaskName` naming convention.
* Creates an associated Markdown file, born with a heading holding today's date. The title
  of the task is the folder and file name, so it is not repeated inside the file.
* Finds an existing task by title in the current directory, on any date, and starts a new
  dated section in it.
* Lists tasks by when they were last worked on, not by the date in the folder name.
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
# 23/09/2026

Your notes go here.

[mktsk:2026-09-23T00:00]: # "open"
```

A new task is `open`, and the event that says so sits under two blank lines, so a note
typed on the first one never runs into it.

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
Opened: 260923 - ItsAlive (added # 30/09/2026) (state: in-progress)
```

No new folder is created. A first level heading with today's date is appended as a new
section to the existing Markdown file, so each day you work on a task keeps
its own notes, and coming back on a new day moves the task to `in-progress`:

```markdown
# 23/09/2026

Your notes go here.

# 30/09/2026



[mktsk:2026-09-30T00:00]: # "in-progress"
```

Running it twice on the same day does not add a second heading for that date and never
changes the state. Your text is never rewritten; only trailing whitespace is dropped.

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

The date stays, so the task keeps its place in the history. Only the names move, the
file inside the folder and the folder itself: the file is never read and never written,
because the title of a task is not inside it. The file is not opened either, because
renaming is not working on the task.

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
  18/09/2026  Its Alive  (in-progress, 2 interventions, last activity 30/09/2026)
  23/09/2026  F Society  (open, 1 intervention, last activity 23/09/2026)
Able/
  19/09/2026  Foo  (open, 1 intervention, last activity 19/09/2026)
Veritas/
  25/09/2026  F Society Everbind  (open, 1 intervention, last activity 25/09/2026)
```

Each directory is a heading, the one you are in first, and the tasks under it read the
same way the GUI shows them: the date of the folder, two spaces, then the title read as
words (`FSocietyEverbind` shows as `F Society Everbind`). What the Markdown file knows
comes after it: the state the task is in, how many dated sections the file has, the one
the task was born with counted, and the date of the last of them.

Tasks come by last activity, so the one you worked on last is the first, whichever day it
was created, and coming back to a task moves it to the top. Tasks of the same last activity
are alphabetical, and the directories themselves are in alphabetical order.

Pass `--only` with a state to keep only the tasks in it:

```bash
mktsk --list --only waiting
```

It takes `open`, `in-progress`, `waiting` and `closed`, since it filters what the files
carry rather than what the command can set. A category left without a task prints no
heading at all, and any other word is an error. On its own, without `--list`, it is
refused before anything is listed.

A task folder without its Markdown file is left out, since there is nothing to open. A
Markdown file that cannot be read keeps its task in the list, and so does one with no
dated section, or one still in the old format: the date of the folder stands in as its
last activity, since there is nothing in the file to read it from, and the state of such
a task is `open`, which is what a file with nothing in it is.

## Setting the state of a task

Pass `--state` with the title of the task and the state to give it:

```bash
mktsk --state "It's Alive!" waiting
```

```text
260923 - ItsAlive: waiting
```

The accepted states are `open`, `in-progress` and `waiting`. `closed` is a state a file
can carry, but this command does not set it. The title is found the same way as for
`mktsk <title>`, on any date and in the directory you are in, and a title that is not a
task there is an error that creates nothing. The file is not opened either, because
changing the state is not working on the task.

The state lives in the Markdown file as a line at the end of it, after a blank line, so
Markdown keeps it out of your notes:

```markdown
[mktsk:2026-10-02T09:40]: # "waiting"
```

Every change appends one line, stamped with the local time of the moment, and the last
line in the file is the state the task is in now. A section written by a resume lands in
front of those lines rather than after them, so the events stay at the end of the file.

You rarely have to run this command, because mktsk records the obvious changes by itself:
a new task starts `open`, and coming back to it on a new day moves it to `in-progress`
when it was `open`, `waiting` or `closed`. Coming back on the same day never changes the
state, and a task already `in-progress` stays as it is: only a new section, a new day of
work, counts. The message of the command says what was recorded, for example
`(state: in-progress)`, or that the state was not recorded when writing it failed; the
task is opened either way.

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

A task used to open its Markdown with a `# <title>` heading and date each visit with a
second level one. The format mktsk writes has neither: the title is the folder and file
name, and each visit is a first level heading. To convert the tasks you created before,
run the migration over the folder that holds them:

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

A task still in the old format is refused rather than misread: opening or resuming it
fails with an error naming the file and this command, and nothing is written to it, so
it can still be migrated.

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
  under a heading per category. By last activity, so the task you worked on last comes
  first;
* read each task as four columns under their headings: the task itself, the date of the
  folder as `dd/mm/yyyy` with the title read as words (`260923 - FSocietyEverbind` shows
  as `23/09/2026  F Society Everbind`), the state the task is in, the number of
  interventions, and how long ago the last of them was, as `today`, `yesterday` or
  `N days ago`;
* create a task with the same rules as the CLI, opening the resulting Markdown file with
  the default application;
* act on an existing task by selecting it, which brings a bar of buttons over its row.
  The room for the buttons appears only on the row you clicked:
  * `Open` reveals the task folder in the file manager, without touching the task;
  * `Resume` adds a section for today, wherever the task lives, and opens it;
  * `Rename` asks for a new title and renames the folder and the file, keeping the date.
    The content is left exactly as it was, and a title another task already has is
    refused.
  * the last button carries a menu with `open`, `in-progress` and `waiting`: pick one and
    the state of the task changes where it lives, a line at the end of its Markdown file,
    and the list shows the new state at once. A file can carry `closed` too, but this
    menu does not set it.

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

