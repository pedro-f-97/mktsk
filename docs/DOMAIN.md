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
- Resuming appends `# <today>` to the `.md` after a blank line, in front of the final
  block of state events when the file has one, unless `parse_task` already shows an
  intervention for that date; a file with nothing in it is dated instead of appended to.
  The section never rewrites the body, only trailing whitespace is dropped, and the date
  is recognised the way the parser reads it, so a heading written by hand in another of
  the accepted forms, with stray spacing or inside a code block, counts
- A `.md` in the old format is refused rather than read: `append_date_section` raises
  `TaskError` naming the file and saying it is in the old format and was not read, and
  nothing is written. `is_legacy` is what recognises one
- The state follows what you do: creating records `open`, and resuming with a new section
  records `in-progress` when the state is `open`, `waiting` or `closed`. Resuming on the
  same day never changes the state, a state already `in-progress` writes nothing, and only
  a new date section counts as work; the one state a visit takes over without a section is
  `closed`, because a folder that stands again is not a task that is over, and a reopened
  same day leaves `closed` for `in-progress` the same way
- The state a resume starts from is `current_state` read before the section is added, so a
  file with no events counts as `open` and its second section takes it to `in-progress`
- The message of a create or a resume ends with ` (state: <state>)` when this visit records
  one, and with ` (state not recorded)` when writing the event failed; a state that cannot
  be written never stops the task from being opened
- `resume_task(folder, title)` resumes the folder it is given, wherever that folder
  lives; unlike `open_or_create_task`, it does no lookup and takes no directory. A folder
  that is not there but whose archive is, in the same directory, is reopened instead
- `rename_task(folder, title, raw_title)` keeps the date prefix and renames the `.md` and the
  folder, names only: the content is never read and never written, because the title of a
  task is not inside the file any more. Renaming to the title the task already has does
  nothing
- `rename_task` undoes a step that fails, in reverse, so it never leaves the task as
  `260918 - OldTitle/NewTitle.md`
- `rename_task` raises `TaskError` on an empty title, a reserved Windows name, a missing
  `.md` or a title another task of the same directory already has; it renames the `.md`
  before the folder, or the old file path stops resolving
- `move_task(task_dir, dest_category)` moves a task folder into a category and returns
  where it stands. The folder moves whole, with the `.md` and every attachment it
  carries, and it keeps its name, so the task holds its place in the history. The move
  is a rename of the folder, so nothing is read and nothing is written
- The title of a task is unique in the directory it stands in, so a category that
  already holds a task of that title refuses the move with `TaskError` naming the title
  and the category. The lookup is `find_task_folder`, so it ignores the date and the
  case: a task of another date in the category refuses the move just the same
- A task that already stands in the category stays where it is: the move does nothing
  and returns the path it already stood at
- A category inside the task folder is refused with `TaskError`, and a folder that
  cannot be moved is refused with `TaskError` naming the folder and the error of the
  system, never with the `OSError` itself
- `move_into_task(paths, task_folder)` moves files and folders into the folder of a
  task. Every file or folder moves as one item, whatever it holds, and it is `shutil.move`
  that moves it, so a file that comes from another drive is copied and deleted rather than
  renamed. The move never overwrites: a name the task folder already carries is left alone
  and the file that would take it is skipped
- Whether a name is taken is asked of the file system itself, with `os.path.lexists`, and
  never worked out by hand, so the answer is the one the system gives on the platform the
  files live on
- A file that is not there is skipped as `missing`, the task folder itself and a folder
  that holds it are skipped as `contains the task folder`, a file that already stands in
  the task folder is skipped as `already in the task folder`, and a name that is taken is
  skipped as `already exists`. The comparison of the folders is done on the resolved
  paths, so a link or a `..` in the path does not slip a folder into itself
- A move that fails is skipped with the error of the system, and the files after it are
  still moved, so one file that cannot be moved never holds the rest
- Closing compresses the task folder into an archive beside it: `close_task(folder, title)`
  writes `<folder name>.zip` under a temporary name next to the folder, with every file of
  the folder under the path `<folder name>/<relative path>` and the `.md` carried in with
  the `closed` event written into the zip rather than into the folder, so the `.md` on disk
  is never touched. It verifies the zip with `testzip`, the exact set of names and the size
  of every member, moves it into place with `os.replace`, and only then deletes the folder.
  A failure before that leaves the folder intact and removes the temporary file; a failure
  deleting the folder keeps both and raises `TaskError` saying the task is archived but the
  folder could not be removed. Nothing is ever lost. The message is `Closed: <zip name>`
- Reopening brings the archive back as a folder: `reopen_task(location, title)` finds the
  archive, extracts it into `.<folder name>.part` beside it, validating each member before
  it is written — a name that is absolute or that leaves the destination once resolved is
  refused with `TaskError` and nothing of it reaches the disk — verifies the extraction
  with `testzip`, the exact set of names and the size of every file, renames it into place,
  resumes the task with `Reopened: <folder name>` and what was added, and only then deletes
  the zip. A failure up to and including the resume removes the extracted folder, or the
  temporary directory when it has not moved yet, and leaves the archive intact; a failure
  deleting the zip keeps both and raises `TaskError` saying the task is reopened but the
  archive could not be removed. Nothing is ever lost
- A folder and an archive of the same title standing together do not fix themselves: the
  folder is the task that stands, so `reopen_task` refuses with a `TaskError` naming both
  and leaves the archive where it is, while `open_or_create_task` and `resume_task` find
  the folder first and resume it, and with only an archive there they reopen it rather
  than refusing it as archived
- A leftover extraction directory of a failed run is left where it is: `reopen_task`
  refuses it with a `TaskError` naming it rather than writing into it or taking it away,
  and only the hand that put it there takes it away
- `is_task_archive(name)` is `is_task_folder` on the name without its `.zip`, so a name
  that is not a task folder gives no archive, and a directory named like one is not one;
  `find_task_archive(location, title)` looks one up by title ignoring the case and taking
  the most recent date, the same way `find_task_folder` does
- The title of a task is unique in a directory whether it stands as a folder or as an
  archive: `mktsk Foo` with `Foo.zip` there reopens the archive, leaving the folder and no
  zip, `rename_task` refuses a task whose archive is there, the target of a
  rename cannot be a title an archive already has, and `_rename` reports the archive when
  the folder it was given is gone
- The listing reads an archive as a task with the state `closed`, whatever the `.md`
  inside it says, and takes the intervention count and the last activity from that file
  with the same rules as a folder: the archive path is `<zip name minus .zip>/<title>.md`,
  a zip that cannot be read, holds no `.md` or holds one in the old format falls back to
  the date in its name with 0 interventions, and a failure reading one never brings the
  listing down. Closed entries sort with the folders by last activity, in the category
  they sit in, so closing moves a task within the listing rather than out of it
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
  directory, visible in the tree and a category of its own, rather than a task that could
  be opened
- A category is a direct subdirectory of the base directory that is not a task folder, so
  the listing stops one level down and a task inside a subdirectory of a subdirectory is
  not found. A subdirectory whose name starts with `.` is no category at all: it is left
  out of the listing and of the tree
- The base folder lives in the shared config file, not in QSettings: JSON
  `{"base_folder": "<absolute path>"}` at `%APPDATA%\mktsk\config.json` on Windows,
  `$XDG_CONFIG_HOME/mktsk/config.json` or `~/.config/mktsk/config.json` on Linux, and
  `~/Library/Application Support/mktsk/config.json` on macOS. The GUI and the CLI read the
  same file, so a folder chosen once is the folder both work in
- Reading the config never raises: a missing, unreadable, corrupt or invalid file, a file
  that is not an object, or a `base_folder` that is missing, empty or not a string all mean
  that no folder is saved. Resolving it gives `OK` when the saved path is a directory,
  `NOT_CONFIGURED` when nothing is saved, and `MISSING` when the saved path is no longer a
  directory; the missing result carries the path so it can be named
- The old QSettings value is migrated once, and only while the config file does not exist:
  the key is `last_path`, under the organization and application `mktsk`, which is what the
  GUI writes. The value is only read, never changed or removed, and a folder that no longer
  exists is saved all the same so the missing result can name it. PySide6 is imported only
  for this migration, so a machine without the GUI is never asked for it
- Writing the config is atomic: a temporary file in the same folder is moved into place
  with `os.replace`, so a reader never sees half a file and a failed write leaves no
  temporary file behind
- `validate_category` strips whitespace and refuses a name that is empty, carries a
  character Windows does not allow (`<>:"/\|?*` or a control character), is reserved,
  starts with `.` or `_`, looks like a task folder (`260918 - Foo`) or ends in a dot or a
  space. Two categories of the same name in any case are refused
- `run_setup` validates the base folder and every category first, then creates the base
  folder and the category subfolders, and only then writes the config file. A validation
  or creation failure leaves the old config untouched, and an old path is replaced only
  after the new setup succeeded. At most two categories are accepted
- A subdirectory without tasks is a category all the same and comes with no task, so it
  stands as a divider of its own in the `All` tab. A subdirectory that holds nothing but
  closed tasks stands as a divider as well: its tasks are gone into their archives, so what
  is left of them is the folder. A task folder whose `.md` says the task is closed is a
  task that still stands on disk, so it keeps the folder with it and the folder does not
  stand alone. A subdirectory whose name starts with `_`, that Windows marks hidden or as
  a system file, or that cannot be read, is not such a category: a working folder is left
  out, and a folder that cannot be read may well hold tasks that are only out of reach
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
- `standardize_string`, `create_category` and the search fold share `_without_accents` for
  the NFKD folding, so the accent removal is only implemented once
- Open files and folders with the OS default application: `os.startfile` on Windows,
  `xdg-open` on Linux when it is there, `gio open` otherwise
- Folder and file names are ASCII only
- `TaskEntry` carries two dates: `date` is the one in the name of the folder, the day the task
  was created, and `last_activity` is the one the `.md` knows. The listing reads every `.md`
  with `parse_task`, and `interventions` is how many interventions it found. `state` is read
  from that same text with `current_state`, so the listing never reads a file twice, and it is
  `open` when the file is in the old format or cannot be read, which is what a file with
  nothing in it is. `last_activity` falls back to the folder date when the file is in the old
  format, when it carries no
  intervention, or when it cannot be read, and `interventions` is then 0: a task is still a
  task when nothing can be read out of it. An old file is never read as the new one, so a
  dated heading a conversion left in the body is content rather than a visit. A `.md` that
  cannot be read never brings the listing down, the same rule as a directory that cannot be
  read
- The attachments of a task are what its folder carries beside the task itself: every
  direct entry counts, a subfolder as one whatever it holds, and the folder is read one
  level deep and never walked into. The `.md` named after the task is the task rather than
  an attachment, and hidden entries (a dot-prefixed name, or the Windows hidden or system
  attribute), `desktop.ini`, `Thumbs.db` and Office lock files named `~$…` are not
  attachments. A folder that is missing or cannot be read carries none and never raises,
  and an archive carries none either, because it is never opened
- `read_archived_task(zip_path)` reads the `.md` and the other entries of a task from
  inside its archive, without extracting anything. It accepts two layouts: the nested one
  the closing writes (`<folder>/<title>.md` and `<folder>/...`) and a flat one with the
  members at the zip root (`<title>.md`, `...`). The `.md` is decoded with `utf-8-sig`
  and `errors="replace"`, so a BOM is accepted and invalid bytes become U+FFFD. The
  attachments are the direct children of the task root (the zip root, or the single
  top-level folder in the nested layout) minus the task `.md`; a folder counts as one
  entry (inferred from the first path segment, since zips may have no explicit directory
  entries), with the same ignored names and the same display names as `list_attachments`
  uses. The result is sorted case-insensitively. A corrupt zip, a zip without the `.md`,
  a password-protected member, or any OS error returns `("", [])` or the entries that
  could still be listed with an empty text; it never raises.
- Tasks of a category are listed by `last_activity`, newest first, and alphabetical for tasks
  of the same last activity. Coming back to a task moves it to the top, whichever day it was
  created
- Reading a title back for display (`readable_title`): every uppercase letter starts a
  word and a digit starts one too, so `FSocietyEverbind` reads as `F Society Everbind`
  and `Task2` as `Task 2`; consecutive digits stay together, so `2026` survives
- `search_tasks(entries, query)` filters the entries whose title holds every word of the
  query, matched against the text the `Task` column shows (`readable_title`), so a search
  reaches a task the way a reader of the table spells it: the query is split on whitespace
  and every word must be a substring of that text, in any order. Case and accents are folded
  on both sides through `_without_accents` and `casefold`, so `SOCIETY` finds `F Society` and
  `björk` finds `Bjork Naive`. An empty or whitespace-only query matches nothing, no title
  holding every word gives an empty list, the input order is kept, closed entries are matched
  like open ones, and the function is pure: no Qt

## Reminders

- Reminders live in `reminders.json`, next to the shared config file (the parent of
  `config.config_path()`), so they travel with the base folder configuration.
- The file holds `{"version": 1, "reminders": [...]}`, each reminder carrying `id`, `due`
  (`YYYY-MM-DDTHH:MM`), `message`, `task` and `title`, written UTF-8 with
  `ensure_ascii=False` and indent 2.
- A reminder's identity is its task folder name (`YYMMDD - TaskName`), never an absolute
  path; `title` is a readable snapshot used when the task can no longer be found.
- `due` is a naive local time at minute precision; the core accepts any date, and validation
  of past dates belongs to the UI.
- Writes are atomic: a temp file in the same directory moved into place with `os.replace`,
  so no temp file is ever left behind.
- A missing file loads as `[]`; an unreadable or corrupted file is renamed to
  `reminders.json.bad` (replacing an existing `.bad`) and loads as `[]`; an invalid entry
  (missing key, bad date) is skipped and the valid ones kept.
- `pop_due` returns the reminders due at or before `now`, sorted by due (`due == now`
  counts as due), removes them from the file before returning, and leaves the rest: each
  reminder fires at most once.
- There is no scheduler and no reminder file is touched unless a system tray is available;
  without a tray, reminders stay pending.