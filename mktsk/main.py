import argparse
from pathlib import Path

from . import files, helpers, listing, standards, state, tasks

_RENAME_MINIMUM_ARGUMENTS = 2


def build_parser() -> argparse.ArgumentParser:
    """Builds the parser for the command line.

    The title is optional on the parser, because `--rename` takes a task
    folder and a new title instead of a title to create. Each option checks
    what it was given, so a missing argument is refused the way argparse
    refuses anything else.

    Returns:
        The parser.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("title", nargs="*")
    parser.add_argument(
        "--rename",
        action="store_true",
        help="rename a task folder, given its name and the new title",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="list the tasks here and in the categories below, and open nothing",
    )
    parser.add_argument(
        "--new-category",
        metavar="NAME",
        help="create a category folder here, for tasks to be kept apart in",
    )
    parser.add_argument(
        "--state",
        nargs=2,
        metavar=("TITLE", "STATE"),
        help="set the state of a task (open, in-progress, waiting)",
    )
    return parser


def parse_arguments() -> argparse.Namespace:
    parser = build_parser()
    args = parser.parse_args()

    # every option names what it needs, so each is checked on its own and only
    # the plain form falls back to the title
    if args.rename and args.list:
        parser.error("--rename and --list do not go together")

    if args.new_category is not None:
        if args.rename or args.list or args.state:
            parser.error("--new-category does not go with --rename or --list")

        if args.title:
            parser.error("--new-category takes one name, so quote it")
    elif args.list:
        # the list is of what is here, so a title alongside it is a mistake
        if args.title or args.state:
            parser.error("--list takes no title")
    elif args.rename:
        # the new title is every argument after the folder, so a title made of
        # several words needs no quoting, the same way a task title does not
        if len(args.title) < _RENAME_MINIMUM_ARGUMENTS or args.state:
            parser.error("--rename takes a task folder and a new title")
    elif args.state is not None:
        if args.title:
            parser.error("--state takes TITLE and STATE")
    elif not args.title:
        parser.error("a task title is required")

    return args


def main() -> int:
    args = parse_arguments()

    if args.new_category is not None:
        return _new_category(Path.cwd(), args.new_category)

    if args.list:
        return _list(Path.cwd())

    if args.state is not None:
        return _set_state(Path.cwd(), args.state[0], args.state[1])

    try:
        if args.rename:
            return _rename(Path.cwd(), args.title[0], " ".join(args.title[1:]))

        result = tasks.open_or_create_task(Path.cwd(), " ".join(args.title))
        print(result.message)
    except (OSError, helpers.TaskError) as error:
        print(f"Error: {error}")
        return 1

    try:
        helpers.open_file(result.file)
    except OSError as error:
        print(f"Warning: {error}")

    return 0


def _task_label(entry: listing.TaskEntry) -> str:
    """Formats one task as the listing shows it.

    The date of the folder, two spaces and the title read as words are what the
    GUI shows, and what goes after them is what the .md carries: how many times
    the task was worked on and the last of those days. A task whose .md cannot
    be read is still listed, with the date of its folder as its last activity.

    Args:
        entry: the task to format.

    Returns:
        The line that goes under a directory heading.
    """
    date = entry.date.strftime(helpers.DATE_FORMAT)
    activity = entry.last_activity.strftime(helpers.DATE_FORMAT)
    title = helpers.readable_title(entry.title)
    noun = "intervention" if entry.interventions == 1 else "interventions"

    return f"{date}  {title}  ({entry.interventions} {noun}, last activity {activity})"


def _list(location: Path) -> int:
    """Prints the tasks of a directory and of its categories, and opens nothing.

    Each category is a heading of its own name, the directory here included, and
    the tasks under it read as they do in the GUI: the date, two spaces, then the
    title read as words. The tasks of a category come by last activity, so the
    one you worked on last is the first. A directory with no tasks prints nothing
    at all.

    Args:
        location: the directory to list.

    Returns:
        0.
    """
    for group in listing.find_task_groups(location):
        name = location.name or str(location)
        print(f"{name if group.category is None else group.category.name}/")

        for entry in group.entries:
            print(f"  {_task_label(entry)}")

    return 0


def _new_category(location: Path, raw_name: str) -> int:
    """Creates a category folder in the given directory, and reports it.

    The folder is not opened: making somewhere to put tasks is not working on
    one. A name that is already there is not an error, because the point is to
    have the folder, not to be the first to make it.

    Args:
        location: the directory to create the category in.
        raw_name: the name to give the category, as typed by the user.

    Returns:
        0 on success, 1 when the name cannot be used.
    """
    try:
        category = files.create_category(location, raw_name)
    except (OSError, helpers.TaskError) as error:
        print(f"Error: {error}")
        return 1

    print(f"Created: {category}")

    return 0


def _rename(location: Path, folder_name: str, raw_title: str) -> int:
    """Renames a task folder given its name, and reports what happened.

    The file is not opened: renaming is not working on the task, and the notes
    keep the content they had.

    Args:
        location: the directory that holds the task folder.
        folder_name: the name of the task folder to rename.
        raw_title: the new title, as typed by the user.

    Returns:
        0 on success, 1 when the folder cannot be renamed.
    """
    title = standards.task_folder_title(folder_name)

    if title is None:
        print(f"Error: '{folder_name}' is not a task folder")
        return 1

    folder = location / folder_name

    if not folder.is_dir():
        print(f"Error: '{folder_name}' is not there")
        return 1

    try:
        result = tasks.rename_task(folder, title, raw_title)
    except (OSError, helpers.TaskError) as error:
        print(f"Error: {error}")
        return 1

    print(result.message)

    return 0


_STATE_CHOICES = ("open", "in-progress", "waiting")


def _set_state(location: Path, raw_title: str, new_state: str) -> int:
    """Sets the state of a task given its title, and reports it.

    The title is resolved the way `mktsk Foo` resolves it, by normalizing it
    and looking it up in the current directory, on any date. A title that is
    not there does not create a task. `closed` is not accepted here: closing
    is a different operation, for a later step.

    Args:
        location: the directory the task belongs to.
        raw_title: the task title, as typed by the user.
        new_state: the state to set.

    Returns:
        0 on success, 1 when the task or the state cannot be used.
    """
    if new_state not in _STATE_CHOICES:
        print(f"Error: '{new_state}' is not a state open, in-progress or waiting")
        return 1

    title = standards.standardize_string(raw_title)
    folder = listing.find_task_folder(location, title)

    if folder is None:
        print(f"Error: '{raw_title}' is not a task here")
        return 1

    file = folder / f"{standards.task_folder_title(folder.name) or title}.md"

    try:
        state.set_state(file, new_state)
    except (OSError, helpers.TaskError) as error:
        print(f"Error: {error}")
        return 1

    print(f"{folder.name}: {new_state}")

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
