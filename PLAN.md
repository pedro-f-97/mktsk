# PLAN.md

Plan to evolve `mktsk` from a folder creator into a mini task manager, with the `.md` as the
single source of truth. One step at a time, each with a prompt for the agent.

Starting point: v0.4.1 with `workers.py` already split into the `standards`, `files`,
`listing` and `tasks` modules (344 tests and 100% coverage before the split).

## How to use

1. Commit this file on a `docs/plan` branch (`docs: add the plan`)
2. Run the steps in order. One prompt per agent session, one branch per step
3. Review the diff, merge into `main`, and only then move on to the next step
4. Between step 2 and step 3, run the migration on the real tasks (see step 2)

## Steps

| # | Step | Branch |
|---|------|--------|
| 1 | Pure parser for the `.md` | `feat/md-parser` |
| 2 | Format migration script | `feat/md-migration` |
| 3 | New format in the code | `feat/new-md-format` |
| 4 | Listing by last activity (CLI) | `feat/activity-listing` |
| 5 | Split `gui.py` | `refactor/split-gui` |
| 6 | GUI with activity | `feat/gui-activity` |
| 7 | State as data and `--state` | `feat/task-state` |
| 8 | Automatic state transitions | `feat/state-transitions` |
| 9 | State in the listings and a GUI action | `feat/state-listing` |
| 10 | Close = compressed archive | `feat/close-task` |
| 11 | Reopen an archived task | `feat/reopen-task` |

Why this order: the parser carries no risk and everything depends on it; the migration comes
early because every new task in the old format is one more to convert; reading (4 to 6)
comes before writing state (7 to 9) and validates the parser against real data; closing and
reopening (10 and 11) are the only steps that delete folders, so they come last.

## Decisions made

- States: `open`, `in-progress`, `waiting`, `closed`
- The state lives in the `.md` itself, as events that are invisible when rendered
- The date of each intervention is a level 1 heading: `# 02/10/2026`
- The `.md` no longer has a `# Title`; the title is the one in the folder and file name
- Closing compresses the folder into a zip; the zip is the `closed` state
- No compatibility with the old format: everything is migrated at once
- Everything in the repository is in English: code, strings, docs and state names

## Open decisions (defaults already in the prompts)

- `waiting` state: included. If you do not want it, drop it from step 1 (`STATES`) and from
  steps 7 and 9
- Where the zip goes: next to where the folder was, as `YYMMDD - Title.zip`. The alternative
  is an `_Archive` folder, which would have to be treated as an exception in the categories
- Resuming an archived task: reopens without asking for confirmation, because closing again
  is cheap

## The .md format

```markdown
# 18/09/2026

Customer request, see attachment.

## Problem

Free text, with levels 2 to 6 available.

# 02/10/2026

Supplier replied.

[mktsk:2026-09-18T10:02]: # "open"
[mktsk:2026-10-02T09:40]: # "in-progress"
```

Rules:

1. No `# Title`. The folder and the `.md` file name say which task it is
2. Intervention: a level 1 heading whose line contains a valid date. Canonical form
   `# dd/mm/yyyy` (`DATE_FORMAT`). When reading, `dd-mm-yyyy`, `dd.mm.yyyy`, `yyyy-mm-dd` and
   `dd/mm/yy` are tolerated, and so is text after the date (`# 29/09/2026 - reply`). An
   impossible date does not count. A `# Something else` with no date is just a heading
3. Levels 2 to 6 are free for notes
4. State: lines `[mktsk:YYYY-MM-DDTHH:MM]: # "state"`, local time, anywhere in the file.
   mktsk always writes them in a block at the end, after a blank line. Without that blank
   line, Markdown renders them as text
5. Current state: the last event in file order. An unknown value is ignored. With no events,
   the state is derived: `open` with at most one intervention, `in-progress` with more
6. Code blocks (` ``` ` and `~~~`) are ignored everywhere
7. Old format: the first non-empty line is `# <text without a date>` and the file has at
   least one `## <date>`. It is never read as the new format

## Common rules

They apply to every prompt.

- Read `AGENTS.md` and this `PLAN.md` before touching any code
- `workers.py` no longer exists: it was split into the `standards`, `files`, `listing` and
  `tasks` modules. Where this plan names a function that used to live there, find where it
  is now with `grep`. Put new code in the module whose responsibility it matches, and never
  recreate `workers.py`. The new modules of this plan (`parsing`, `migration`, `state`)
  sit next to them in `mktsk/`
- One branch per step, created from an up-to-date `main`, with the name given. Never work
  on `main`. Never push, open a PR or create tags
- Commits `<type>: <description>`, one line, lowercase, no trailing period. One commit per
  topic
- Before finishing, everything green: `ruff check .`, `pyright mktsk/` and `pytest`, with
  coverage at 100%
- Tests use `tmp_path` only. Never read from or write to the real task folders
- Update `AGENTS.md` (Structure, Domain rules, CLI, GUI) and `README.md` when visible
  behaviour changes. A rule in `AGENTS.md` that the step replaces is rewritten in the same
  commit, never left contradicting the code
- Style: short, direct, no emojis. Small functions, docstrings with `Args:` / `Returns:` /
  `Raises:`, never delete existing comments
- Design doubt: pick the simplest option and record it in the report. Stop and ask only if
  there is a risk of losing user data
- Final report, at most 15 lines: what changed per file, number of tests and coverage,
  decisions taken, open doubts

---

## Step 1 — Pure parser for the .md

**Result:** a new, tested module that reads the text of a `.md` and returns interventions,
state events and last activity. It is not wired into anything else.

**Done when:** the module covers every edge case and the rest of the code is unchanged.

````text
Role: you are a senior Python engineer working on the mktsk repository, a CLI and GUI that
creates task folders named `YYMMDD - Title`, each with a `.md` file.

Objective: create the module `mktsk/parsing.py`, with pure functions only, that turns the
text of a task `.md` into data. This step does not wire the module into anything:
no existing module changes (`main.py`, `gui.py` and the ones that replaced `workers.py`).

Before starting, read `AGENTS.md` and, in `PLAN.md`, the sections "Common rules" and "The .md
format". Branch: `feat/md-parser`.

Details:
- The format is the one described in "The .md format". This step implements reading only
- API (you may adjust names if there is a reason, and record it in the report):
  - `STATES = ("open", "in-progress", "waiting", "closed")`
  - `Intervention(NamedTuple)`: `date: datetime.date`, `heading: str`, `line: int` (1-based)
  - `StateEvent(NamedTuple)`: `timestamp: datetime.datetime` (naive, local time),
    `state: str`, `line: int`
  - `ParsedTask(NamedTuple)`: `interventions: list[Intervention]`,
    `events: list[StateEvent]`, `last_activity: datetime.date | None`
  - `parse_task(content: str) -> ParsedTask`
  - `is_legacy(content: str) -> bool`, following rule 7 of the format
- Intervention: a line starting with a single `#` followed by a space (up to 3 spaces of
  indentation). `#hashtag` and `##` do not count
- Dates: find candidates with regular expressions (`dd/mm/yyyy`, `dd-mm-yyyy`, `dd.mm.yyyy`,
  `dd/mm/yy`, `yyyy-mm-dd`) and validate them with `datetime.date(...)`. Two-digit years mean
  2000 plus the year. Use the first valid candidate in the heading. A `2026-10-02` must not
  also be read as `26-10-02`
- Event: a whole line `[mktsk:YYYY-MM-DDTHH:MM]: # "state"`. An invalid timestamp or a state
  outside `STATES` makes the event ignored, never an error
- `last_activity`: the most recent date among the interventions, not the last in file order
- Lines inside code blocks (` ``` ` and `~~~`, closed with the same character) are ignored
  everywhere
- The parser takes text, not a `Path`. It accepts `\r\n` and `\n`
- Ruff has the `DTZ` rules enabled (see `pyproject.toml` and `AGENTS.md`); follow the
  `# noqa: DTZ007` pattern the existing code already uses (`grep` for it)

Tests in `tests/test_parsing.py`, covering at least: empty file; interventions only; events
only; heading with text after the date; impossible date; `#hashtag`; dates out of order; the
five date formats; `2026-10-02` without a double reading; events in any position; invalid
event; code block with a `# 12/01/2026` inside; CRLF; `is_legacy` with an old file, a new
one and an empty one, and with a `## Deadline 05/10/2026` in a new file, which is not old.

Documentation: add the module to "Structure" in `AGENTS.md` and describe the format in a
section of its own, marked as not yet used by the task modules.

Verification: `ruff check .`, `pyright mktsk/` and `pytest` green, coverage 100%, and
`git diff --stat` showing only the new module, the new tests and `AGENTS.md`.

Commit: `feat: add a parser for the task markdown`.

Answer format: the final report described in "Common rules" of `PLAN.md`.
````

---

## Step 2 — Format migration script

**Result:** a script that converts a `.md` from the old format to the new one, simulating by
default. mktsk still writes the old format.

**Done when:** the migration is tested and the dry run shows a correct diff on a copy of the
real tasks.

**Done by you, after the merge:** zip the tasks folder, run the script without `--apply`,
read the diff, run it with `--apply`. Only then step 3.

````text
Role: you are a senior Python engineer working on the mktsk repository. The task `.md` files
are in the old format and are moving to a new one.

Objective: create `mktsk/migration.py` with the conversion of a `.md` from the old format to
the new one, and a command line mode that applies it to a tree of tasks. mktsk keeps writing
the old format in this step.

Before starting, read `AGENTS.md` and, in `PLAN.md`, "Common rules" and "The .md format". The
module `mktsk/parsing.py` already exists and should be reused to recognise dates and code
blocks. Branch: `feat/md-migration`.

Old format: the `.md` starts with `# <Title>` (the folder title), each visit is a
`## dd/mm/yyyy`, and the notes sit below it. New format: no `# Title`; each visit is
`# dd/mm/yyyy`.

Details:
- `migrate_content(content: str, title: str) -> Migration`, with `Migration(NamedTuple)`:
  `content: str` and `review: list[str]` (warnings for a human to review). Pure function
- Rules:
  1. If the first non-empty line is `# <text>`, the text has no date and equals `title`,
     delete it and the blank lines that follow it. If the text is different, leave it and
     warn
  2. Each `## <date>` becomes `# <date>`. The date is recognised as in `parsing.py`
  3. Inside an old date section, headings of level 3 to 6 move up one level
  4. A `##` without a date inside those sections stays as it is and goes into `review`
  5. A `# <date>` that is already in the new format is left alone
  6. Code blocks are never touched
  7. The result ends with a single line break
- Idempotent: migrating an already migrated file returns the same content and no warnings
- Command line `python -m mktsk.migration <folder> [--apply]`: walks the folder and its
  immediate subfolders (the categories), like `find_task_groups`, only tasks recognised by
  `is_task_folder`, and uses the `.md` named after the title. Without `--apply` it only
  simulates: it prints, per file, the status (`migrated`, `already new`, `review`) and a
  unified diff, and writes nothing. With `--apply` it writes each file atomically (a
  temporary file in the same folder and `os.replace`) and, before starting, reminds the user
  to keep a backup
- Read and write with `newline=""` to preserve each file's line separator
- Each file fails in isolation: a read error goes into the report and the script carries on
- Only the `if __name__ == "__main__"` block is excluded with `pragma: no cover`

Tests in `tests/test_migration.py`: title removed; different title warned about and kept;
`## date` converted; `###` moving up; `##` without a date warned about; already new file
unchanged; a `# 29/09/2026` with a single `#` unchanged; code blocks; CRLF preserved; file
with a title only; empty file; idempotency; simulation without writing; `--apply` writing;
isolated error per file.

Documentation: `AGENTS.md` (Structure and a paragraph on how to run the migration) and
`README.md` if it makes sense.

Verification: everything green, coverage 100%, and the simulation over a test directory in
the old format shows the expected diff.

Commit: `feat: add a migration for the task markdown format`.

Answer format: the final report described in "Common rules" of `PLAN.md`.
````

---

## Step 3 — New format in the code

**Result:** mktsk writes and reads only the new format. A file in the old format gives a
clear error instead of being misread.

**Done when:** creating, resuming and renaming tasks works on the real, already migrated
tasks.

````text
Role: you are a senior Python engineer working on the mktsk repository.

Objective: make the task code (the `files` and `tasks` modules) write and read the new `.md`
format, and refuse the old format
with a clear error. The real tasks have already been migrated by the user.

Before starting, read `AGENTS.md` (especially "Domain rules") and, in `PLAN.md`, "Common
rules" and "The .md format". Reuse `mktsk/parsing.py`. Branch: `feat/new-md-format`.

Details:
- New task: the `.md` is born with `# dd/mm/yyyy` (today's date) and a blank line. It no
  longer has a `# Title`
- Resume: the folder's `.md` is still the one for the title the folder carries. If the file
  is empty, write `# <today>`. Otherwise append `# <today>` at the end (after `rstrip` and a
  blank line) unless `parse_task` already shows an intervention with today's date. The
  message returned to the user still says what happened and shows the new heading
- Remove `sign_md_file` and `_retitled`: there is no title inside the file any more
- `rename_task` now touches names only: it renames the `.md` inside the folder and then the
  folder, keeping the current undo if the second step fails. Whatever depended on the content
  of the heading goes away
- Guard: if `is_legacy(content)` is true when resuming, raise `TaskError` with a message that
  names the file and the migration command. Nothing is written in that case
- `find_task_folder`, the title uniqueness rule and `exclude` do not change
- Do not touch the listing or the GUI beyond what the existing tests require

Tests: update the existing ones that relied on the old format and add: a new task with
`# today`; resume appends `# today`; resume on the same day does not duplicate; empty file;
an old file gives `TaskError` without writing; a case-only rename still works; rename does
not touch the file content.

Documentation: rewrite in `AGENTS.md` the domain rules that mention the title heading and
`## date`, and update `README.md` where it describes the `.md`.

Verification: everything green, coverage 100%, and a pass over the code confirming that no
reference to `sign_md_file`, `_retitled` or to `##` as a date is left.

Commit: `feat: write the new markdown format`.

Answer format: the final report described in "Common rules" of `PLAN.md`.
````

---

## Step 4 — Listing by last activity (CLI)

**Result:** `TaskEntry` knows the last activity and the number of interventions, ordering is
by activity and `--list` shows both.

**Done when:** a task resumed today shows up first in the listing.

````text
Role: you are a senior Python engineer working on the mktsk repository.

Objective: make the task listing use the last activity from the `.md` instead of the folder
date, and show it in `--list`.

Before starting, read `AGENTS.md` and, in `PLAN.md`, "Common rules" and "The .md format".
Reuse `mktsk/parsing.py`. Branch: `feat/activity-listing`.

Details:
- `TaskEntry` gains `last_activity: datetime.date` and `interventions: int`. `date` is still
  the folder date
- `_tasks_in` reads each task's `.md` with `parse_task`. `last_activity` is the one from
  `parse_task`, or the folder date when the file does not exist, cannot be read or has no
  interventions. A read error never brings the listing down
- Ordering: by `last_activity` descending, then by title
- `--list` shows, for each task, the number of interventions and the last activity, keeping
  the format and the language of what already exists. Read the "CLI" section of `AGENTS.md`
  and `README.md` before choosing the format
- The GUI does not change by decision. If the GUI list order changes as a consequence,
  record it

Tests: a task resumed later moves up the order; a file with no interventions falls back to
the folder date; an unreadable file does not bring the listing down; intervention count; a
file in the old format falls back to the folder date; the `--list` output.

Documentation: `AGENTS.md` (listing and CLI rules) and `README.md`.

Verification: everything green, coverage 100%.

Commit: `feat: list tasks by their last activity`.

Answer format: the final report described in "Common rules" of `PLAN.md`.
````

---

## Step 5 — Split gui.py

**Result:** `gui.py` (about 730 lines) is split by responsibility, with no change in
behaviour.

**Done when:** the GUI tests pass with no changes beyond imports and the executable still
builds.

````text
Role: you are a senior Python engineer working on the mktsk repository, experienced with
PySide6.

Objective: split `mktsk/gui.py` into modules by responsibility, without changing behaviour.

Before starting, read `AGENTS.md` (sections "Structure", "GUI" and "Conventions") and, in
`PLAN.md`, "Common rules". Branch: `refactor/split-gui`.

Details:
- Turn `mktsk/gui.py` into a package `mktsk/gui/`. Separate, for example, the drawn icons,
  the task listing and the main window. Decide the boundaries by reading the code. Each
  module should end up with one responsibility and a reasonable size
- The path `mktsk.gui` and everything the tests and the `mktsk-gui` entry point import keep
  working. `__init__.py` re-exports what is needed
- Search for every reference to `gui.py` and `mktsk.gui` in `pyproject.toml`, `.github/`,
  `README.md` and `AGENTS.md`, and confirm that the PyInstaller target and the absolute
  import in `__main__.py` are still valid
- Do not change logic, class names, texts, shortcuts or styles. Only moving code and the
  imports it needs
- Keep the tests as they are; only import changes are allowed. If a test uses
  `monkeypatch` on a path that moved, adjust only that path
- Two commits: first the move, then, if needed, the documentation update

Verification: everything green, coverage 100%, the GUI tests with no behavioural
differences, and `git diff --stat -M` showing mostly renames and moves.

Commits: `refactor: split the gui module` and, if any, `docs: update the gui structure`.

Answer format: the final report described in "Common rules" of `PLAN.md`, with the list of
new modules and the responsibility of each.
````

---

## Step 6 — GUI with activity

**Result:** the GUI shows the number of interventions and how many days ago the last
activity of each task was.

**Done when:** each row in the list shows both values and the order is the activity order.

````text
Role: you are a senior Python engineer working on the mktsk repository, experienced with
PySide6.

Objective: show, on each task in the GUI list, the number of interventions and how many days
ago the last activity was.

Before starting, read `AGENTS.md` (section "GUI") and, in `PLAN.md`, "Common rules".
`TaskEntry` already has `last_activity` and `interventions`. Branch: `feat/gui-activity`.

Details:
- Each row shows the number of interventions and a relative age ("today", "yesterday",
  "N days ago"), in the style of the strings the GUI already has
- The age is computed against today's date, injectable for the tests (`freeze_time` is
  already used in the project)
- The list order is the one the listing layer already returns; do not reorder in the GUI
- Keep the category tabs, the action bar and everything else as it is
- Follow the style of the existing cells and widgets; add no new dependencies

Tests (headless, like the existing ones): row with activity text; "today", "yesterday" and
"N days ago"; a task with no interventions; ordering by activity.

Documentation: `AGENTS.md` (section "GUI").

Verification: everything green, coverage 100%.

Commit: `feat: show the activity of a task in the gui`.

Answer format: the final report described in "Common rules" of `PLAN.md`.
````

---

## Step 7 — State as data and --state

**Result:** mktsk can read and write the state of a task in the `.md`, and there is a command
line option to change it. No automatic transitions yet.

**Done when:** `mktsk --state Foo waiting` records the event and the parser reads it back.

````text
Role: you are a senior Python engineer working on the mktsk repository.

Objective: keep the state of a task as events at the end of the `.md`, and add a command line
option to change it.

Before starting, read `AGENTS.md` and, in `PLAN.md`, "Common rules" and "The .md format",
especially rules 4 and 5. Reuse `mktsk/parsing.py`. Branch: `feat/task-state`.

Details:
- New module `mktsk/state.py`, with a pure layer and a thin one:
  - `current_state(content: str) -> str`: the last valid event, or the value derived by
    rule 5 when there are no events
  - `with_state(content: str, state: str, now: datetime.datetime) -> str`: returns the
    content with the event appended. Pure function. Rejects states outside `STATES` with
    `TaskError`
  - `set_state(file: Path, state: str) -> bool`: reads, applies `with_state`, writes
    atomically and returns whether it wrote
- `with_state`: takes the contiguous block of events at the end (if there is one), keeps the
  old events in the same order, appends the new one, and writes the block at the end after a
  blank line. Events located elsewhere in the file are not touched. Adds nothing if the last
  event already carries that state
- Time: local, format `YYYY-MM-DDTHH:MM`, no time zone
- `append_date_section` now inserts the new date before the final event block, so the block
  always stays at the end. With no block it behaves as today
- CLI: `--state TITLE STATE`, in the style of `--list`, `--rename` and `--new-category`. The
  title is resolved as in `mktsk Foo` (normalised and looked up with `find_task_folder`).
  It accepts `open`, `in-progress` and `waiting`; `closed` will only come from step 10. It
  prints one line with the new state and opens nothing. An unknown title gives `TaskError`
  and does not create the task
- No other behaviour changes

Tests: `with_state` with and without a block; old events preserved; the same state not
duplicated; invalid state; blank line before the block; `current_state` with events, without
events and with invalid events; `append_date_section` inserting before the block; `--state`
working, an unknown title and `closed` refused.

Documentation: `AGENTS.md` (Structure, state rules, CLI) and `README.md`.

Verification: everything green, coverage 100%.

Commit: `feat: keep the state of a task in its markdown`.

Answer format: the final report described in "Common rules" of `PLAN.md`.
````

---

## Step 8 — Automatic state transitions

**Result:** the state follows what you do without you having to touch it: creating gives
`open` and coming back to the task on a new day gives `in-progress`.

**Done when:** the cycle create, resume on another day, resume again has the right events.

````text
Role: you are a senior Python engineer working on the mktsk repository.

Objective: make mktsk record the obvious state changes by itself.

Before starting, read `AGENTS.md` and, in `PLAN.md`, "Common rules" and "The .md format".
The module `mktsk/state.py` already exists. Branch: `feat/state-transitions`.

Transition rules:
- Creating a task records the event `open`
- Resuming a task where a new date section was added, because it is a new day, records
  `in-progress` when the current state was `open`, `waiting` or `closed`
- Resuming on the same day (no new section) never changes the state
- If the state is already `in-progress`, no event is written
- Opening a task only to look at it is not a sign of work: only a new date section counts

Details:
- The current state is the one from `current_state`, computed before the section is added
- The message returned by `open_or_create_task` and `resume_task` mentions the state change,
  when there is one (for example `(state: in-progress)`)
- If writing the state fails, the task still opens and the message says the state was not
  recorded; opening is never lost because of the state
- No new interface in this step

Tests: creating records `open`; a new day from `open` records `in-progress`; a new day from
`waiting`; same day does not change it; already `in-progress` writes nothing; a task with no
events (derived state) on a new day; a failed state write does not prevent opening; the
messages.

Documentation: `AGENTS.md` (state rules) and `README.md`.

Verification: everything green, coverage 100%.

Commit: `feat: change the state of a task as it is used`.

Answer format: the final report described in "Common rules" of `PLAN.md`.
````

---

## Step 9 — State in the listings and a GUI action

**Result:** the state shows in the CLI and GUI listings, can be filtered in the CLI and
changed by hand in the GUI.

**Done when:** `mktsk --list --only waiting` shows only the waiting tasks and the GUI lets
you switch between the three open states.

````text
Role: you are a senior Python engineer working on the mktsk repository, experienced with
PySide6.

Objective: show the state of each task in the listings and allow changing it.

Before starting, read `AGENTS.md` (sections "CLI" and "GUI") and, in `PLAN.md`, "Common
rules" and "The .md format". Branch: `feat/state-listing`.

Details:
- `TaskEntry` gains `state: str`, computed with `current_state` from the `.md` the listing
  already reads, without a second read. If the file cannot be read, the state is `open`
- CLI: `--list` shows the state of each task. `--list --only STATE` filters by state. Do not
  use `--state`, which already exists for something else. An unknown state gives `TaskError`
- GUI: each row shows the state, in the style of the existing cells, and there is a "change
  state" action with the three states `open`, `in-progress` and `waiting`. `closed` does not
  appear, because the only way to it is closing the task (step 10). The action uses
  `set_state` and refreshes the list
- Keep the ordering by activity and the category tabs as they are
- Follow the language and style of the strings already in the GUI and the CLI

Tests: state on each row; the `--only` filter; the filter with an unknown state; an
unreadable file gives `open`; the GUI action changes the state and the list; the action does
not offer `closed`.

Documentation: `AGENTS.md` (CLI, GUI) and `README.md`.

Verification: everything green, coverage 100%.

Commit: `feat: show and change the state of a task`.

Answer format: the final report described in "Common rules" of `PLAN.md`.
````

---

## Step 10 — Close = compressed archive

**Result:** closing a task compresses its folder into a zip next to the original. The zip is
the `closed` state. Reopening only arrives in step 11.

**Done when:** `mktsk --close Foo` leaves a verified zip, deletes the folder only after
verifying it, and `mktsk Foo` does not create a duplicate task.

````text
Role: you are a senior Python engineer working on the mktsk repository. This step deletes
user folders: the rule is never to delete anything before confirming that the result exists
and opens.

Objective: close a task by compressing its folder into a zip file.

Before starting, read `AGENTS.md` and, in `PLAN.md`, "Common rules" and "The .md format". The
modules `mktsk/parsing.py` and `mktsk/state.py` already exist. Branch: `feat/close-task`.

Design:
- The archive sits in the same directory as the folder, named `YYMMDD - Title.zip`. Inside,
  every file of the folder with the path `YYMMDD - Title/<relative path>`, and `ZIP_DEFLATED`
  compression
- The `.md` inside the archive carries the `closed` event, obtained with `with_state` and
  written with `ZipFile.writestr`. The `.md` in the original folder is never changed, so a
  failure halfway does not leave the task half done
- `close_task(folder: Path, title: str) -> TaskResult`, in this order:
  1. refuse if an archive with that title already exists in that directory
  2. write the zip under a temporary name in the same directory (for example
     `.<name>.zip.part`)
  3. verify: `testzip()` returns `None`, the set of names is the expected one and the sizes
     match
  4. `os.replace` to the final name
  5. only then delete the folder with `shutil.rmtree`
- Failure before step 5: delete the temporary file and leave the folder intact. Failure in
  step 5 (on Windows, a file open in an editor, for example): keep the zip and the folder and
  raise `TaskError` explaining that the task is archived but the folder could not be
  removed. Nothing is ever lost
- Archived tasks: `is_task_archive(name)` recognises `YYMMDD - Title.zip` and
  `find_task_archive(location, title)` looks them up ignoring case. The title uniqueness rule
  now includes archives: `mktsk Foo` does not create a new task if `Foo.zip` exists; it
  raises `TaskError` saying it is archived (reopening is step 11). Renaming an archived task
  also gives `TaskError`, and the target of a rename cannot clash with an archive
- Listing: archived tasks show up as entries with the state `closed`, read from the `.md`
  inside the zip, with the same intervention count and last activity. By default the listing
  hides closed tasks; `--list --only closed` shows them. A failure reading a zip never
  brings the listing down
- CLI: `--close TITLE`. The title is chosen as in `--state`. It prints one line with the name
  of the archive created. `--state ... closed` stays refused
- GUI: a "close" action on a task, with a confirmation box, and a "closed" tab that lists the
  archives. Follow the style of the existing tabs and actions

Tests: closing creates the zip and deletes the folder; the `.md` in the zip has the `closed`
event and the folder's was not touched beforehand; extra files and subfolders go in the zip;
a failure writing the zip leaves the folder; a failure deleting leaves both and gives
`TaskError`; `mktsk Foo` with `Foo.zip` does not duplicate; rename refused; listing of the
closed ones; `--list` hides them by default; GUI with confirmation and tab. Use `tmp_path`,
never real folders.

Documentation: `AGENTS.md` (archive rules, CLI, GUI) and `README.md`.

Verification: everything green, coverage 100%.

Commit: `feat: close a task into an archive`.

Answer format: the final report described in "Common rules" of `PLAN.md`, with a description
of any decision about how the archive appears in the listing.
````

---

## Step 11 — Reopen an archived task

**Result:** `mktsk Foo` and the GUI button extract the archive, the task becomes a folder
again and is `in-progress`.

**Done when:** closing and reopening gives back the folder exactly as it was, plus a date
section and the new event.

````text
Role: you are a senior Python engineer working on the mktsk repository. This step extracts
archives and deletes a zip: the rule is never to delete the archive before confirming that
the extracted folder exists, is complete and opens.

Objective: reopen an archived task.

Before starting, read `AGENTS.md` and, in `PLAN.md`, "Common rules" and "The .md format".
Closing (`close_task`, `find_task_archive`) already exists. Branch: `feat/reopen-task`.

Design:
- `reopen_task(location: Path, title: str) -> TaskResult`, in this order:
  1. find the archive with `find_task_archive`
  2. extract into a temporary directory in the same directory (for example `.<name>.part`),
     validating each member before writing it: reject absolute paths and any member that,
     once resolved, leaves the destination directory (zip slip)
  3. verify: `testzip()` returns `None`, and the extracted files match the archive's set
     and sizes
  4. rename the temporary directory to the folder name
  5. resume the task with the normal resume logic: it appends today's date section and, by
     the step 8 rule, changes the state from `closed` to `in-progress`
  6. only then delete the zip
- Any failure up to and including step 5: remove the extracted folder (or the temporary
  one) and leave the archive intact. A failure deleting the zip: keep both and raise
  `TaskError` explaining the situation
- `open_or_create_task` and `resume_task` now reopen an archive instead of raising the step
  10 error. The message says `Reopened: <folder>` and what was added
- Reopen without asking for confirmation, in the CLI and in the GUI. In the GUI, the resume
  action on a task in the "closed" tab reopens and refreshes the lists
- The title uniqueness rule holds: after reopening, there is no zip and folder with the same
  title
- If a folder and an archive with the same title both exist (left over from an old failure),
  the folder wins and the situation does not fix itself; `TaskError` with a clear message

Tests: the close and reopen cycle gives back the same files, plus today's section and the
`in-progress` event; a member with `..` is rejected and nothing is written outside the
destination; a member with an absolute path is rejected; a corrupt zip leaves the archive and
does not create the folder; a failure resuming removes the extracted folder; a failure
deleting the zip leaves both and gives `TaskError`; the `Reopened` message; the GUI reopening
from the "closed" tab. Use `tmp_path`.

Documentation: `AGENTS.md` (archive rules, CLI, GUI) and `README.md`.

Verification: everything green, coverage 100%.

Commit: `feat: reopen an archived task`.

Answer format: the final report described in "Common rules" of `PLAN.md`.
````

---

## After step 11

- Delete `mktsk/migration.py` when it is no longer needed, in a separate `refactor:` commit
- Bump `version` in `pyproject.toml` in its own branch and only then create the tag, as
  `AGENTS.md` says
