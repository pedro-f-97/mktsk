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
    return parser


def parse_arguments() -> argparse.Namespace:
    parser = build_parser()
    args = parser.parse_args()

    if args.rename:
        # the new title is every argument after the folder, so a title made of
        # several words needs no quoting, the same way a task title does not
        if len(args.title) < _RENAME_MINIMUM_ARGUMENTS:
            parser.error("--rename takes a task folder and a new title")
    elif not args.title:
        parser.error("a task title is required")

    return args

def main() -> int:
    args = parse_arguments()

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
