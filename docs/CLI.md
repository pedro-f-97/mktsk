## CLI

- `mktsk <title>` creates, resumes or reopens the task and opens its `.md`
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
  `readable_title`, then two spaces and `(open, 3 interventions, last activity 18/09/2026)`,
  the state first and `intervention` in the singular for one. The date and the title are the
  task column of the GUI row; the state, the count and the date are the CLI wording, because
  the GUI counts in words rather than in dates. The order is the one `find_task_groups`
  already gives, which is by last activity, so a directory with no tasks prints nothing.
  Never format a date or a title in the CLI by hand, or the two listings drift apart. A
  closed task is left out without `--only`, so what the plain listing shows is what still
  stands as folders, and `--only closed` is how the archives are read
- `--only <state>` goes with `--list` and keeps only the tasks in that state. It accepts the
  four states of `parsing.STATES`, `closed` included, because it filters what a `.md`
  carries rather than what this CLI can set, and anything else raises `TaskError`, which
  `main` prints as `Error: invalid state: <state>` with exit code 1. A category left
  without a task by the filter prints no heading at all. On its own it is refused with
  `parser.error("--only goes with --list")`, so it never reaches `_list`
- `--new-category <name>` creates a category in the current directory and prints the path;
  it opens nothing, because making somewhere to put tasks is not working on one. The name
  is one argument, so a name with spaces in it has to be quoted, unlike a task title or a
  new title for `--rename`. It refuses to go with `--rename` or `--list`
- `--state <title> <state>` sets the state of the task with that title in the current
  directory. It accepts `open`, `in-progress` and `waiting`; `closed` is not accepted from
  the CLI here, closing is `--close`. The title is looked up the same way as for
  `mktsk <title>` (normalized and found by `find_task_folder`). It prints one line with the
  new state and opens nothing. An unknown title gives `TaskError` and does not create the
  task
- `--close <title>` closes the task with that title in the current directory, found the
  same way as for `mktsk <title>`. It prints one line with the name of the archive created
  and opens nothing, because closing is the end of the task; an unknown title gives
  `TaskError` and does not create the task. It goes with no other option: alongside
  `--rename`, `--list`, `--new-category` or `--state` it is refused, and a title of the
  plain form alongside it too
- Each option checks only what it needs, and only the plain form falls back to the title;
  when a second option arrives alongside, the refusal is about the two options, not about
  the title
