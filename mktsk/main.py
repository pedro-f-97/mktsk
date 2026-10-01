import argparse
from pathlib import Path

from . import helpers, workers

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
    return parser


def parse_arguments() -> argparse.Namespace:
    parser = build_parser()
    args = parser.parse_args()

    if args.rename and args.list:
        parser.error("--rename and --list do not go together")

    if args.list:
        # the list is of what is here, so a title alongside it is a mistake
        if args.title:
            parser.error("--list takes no title")
    elif args.rename:
        # the new title is every argument after the folder, so a title made of
        # several words needs no quoting, the same way a task title does not
        if len(args.title) < _RENAME_MINIMUM_ARGUMENTS:
            parser.error("--rename takes a task folder and a new title")
    elif not args.title:
        parser.error("a task title is required")

    return args

def main() -> int:
    args = parse_arguments()

    if args.list:
        return _list(Path.cwd())

    try:
        if args.rename:
            return _rename(Path.cwd(), args.title[0], " ".join(args.title[1:]))

        result = workers.open_or_create_task(Path.cwd(), " ".join(args.title))
        print(result.message)
    except (OSError, helpers.TaskError) as error:
        print(f"Error: {error}")
        return 1

    try:
        helpers.open_file(result.file)
    except OSError as error:
        print(f"Warning: {error}")

    return 0

def _list(location: Path) -> int:
    """Prints the tasks of a directory and of its categories, and opens nothing.

    Each category is a heading of its own name, the directory here included, and
    the tasks under it read as they do in the GUI: the date, two spaces, then the
    title read as words. A directory with no tasks prints nothing at all.

    Args:
        location: the directory to list.

    Returns:
        0.
    """
    for group in workers.find_task_groups(location):
        name = location.name or str(location)
        print(f"{name if group.category is None else group.category.name}/")

        for entry in group.entries:
            date = entry.date.strftime(workers.DATE_FORMAT)
            print(f"  {date}  {helpers.readable_title(entry.title)}")

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
    title = workers.task_folder_title(folder_name)

    if title is None:
        print(f"Error: '{folder_name}' is not a task folder")
        return 1

    folder = location / folder_name

    if not folder.is_dir():
        print(f"Error: '{folder_name}' is not there")
        return 1

    try:
        result = workers.rename_task(folder, title, raw_title)
    except (OSError, helpers.TaskError) as error:
        print(f"Error: {error}")
        return 1

    print(result.message)

    return 0

if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
