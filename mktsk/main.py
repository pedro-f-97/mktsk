import argparse
import sys
from collections.abc import Callable
from pathlib import Path
from typing import TextIO

from . import config, files, helpers, listing, parsing, standards, state, tasks

_RENAME_MINIMUM_ARGUMENTS = 2
EXIT_NOT_CONFIGURED = 3


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
        "--only",
        metavar="STATE",
        help="with --list, show only the tasks in that state",
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
    parser.add_argument(
        "--close",
        metavar="TITLE",
        help="close a task into an archive, given its title",
    )
    parser.add_argument(
        "--folder",
        metavar="PATH",
        help="use this base folder instead of the configured one",
    )
    return parser


def parse_arguments() -> argparse.Namespace:
    parser = build_parser()
    args = parser.parse_args()

    # every option names what it needs, so each is checked on its own and only
    # the plain form falls back to the title
    if args.only is not None and not args.list:
        parser.error("--only goes with --list")

    if args.rename and args.list:
        parser.error("--rename and --list do not go together")

    if args.close is not None and (
        args.rename
        or args.list
        or args.new_category is not None
        or args.state is not None
    ):
        parser.error("--close does not go with --rename, --list, --new-category or --state")

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
    elif args.close is not None:
        if args.title:
            parser.error("--close takes one title")
    elif not args.title:
        parser.error("a task title is required")

    return args


def main(
    input_fn: Callable[[str], str] | None = None,
    output: TextIO | None = None,
) -> int:
    args = parse_arguments()

    read = input if input_fn is None else input_fn
    stream = sys.stdout if output is None else output

    location = _base_location(args.folder, read, stream)
    if isinstance(location, int):
        return location

    if args.new_category is not None:
        return _new_category(location, args.new_category)

    if args.list:
        try:
            return _list(location, args.only)
        except helpers.TaskError as error:
            print(f"Error: {error}")
            return 1

    if args.state is not None:
        return _set_state(location, args.state[0], args.state[1])

    if args.close is not None:
        return _close(location, args.close)

    try:
        if args.rename:
            return _rename(location, args.title[0], " ".join(args.title[1:]))

        result = tasks.open_or_create_task(location, " ".join(args.title))
        print(result.message)
    except (OSError, helpers.TaskError) as error:
        print(f"Error: {error}")
        return 1

    try:
        helpers.open_file(result.file)
    except OSError as error:
        print(f"Warning: {error}")

    return 0


def _interactive() -> bool:
    """Tells whether both ends of the command are a terminal."""
    return sys.stdin.isatty() and sys.stdout.isatty()


def _ask(
    prompt: str,
    input_fn: Callable[[str], str],
    output: TextIO,
) -> str:
    """Writes a prompt and returns the answer, stripped."""
    output.write(prompt)
    output.flush()
    return input_fn("").strip()


def _valid_base_folder(raw: str) -> Path | None:
    """Resolves a typed base folder, or returns None when it cannot be."""
    if "\0" in raw:
        return None

    try:
        return Path(raw).expanduser().resolve()
    except (OSError, ValueError):
        return None


def _setup(input_fn: Callable[[str], str], output: TextIO) -> Path | int:
    """Asks for a base folder and up to two categories, and sets them up."""
    base: Path | None

    while True:
        raw_base = _ask("Base folder: ", input_fn, output)

        if not raw_base:
            output.write("Error: base folder must not be empty\n")
            continue

        base = _valid_base_folder(raw_base)

        if base is None:
            output.write(f"Error: '{raw_base}' is not a usable folder\n")
            continue

        break

    categories: list[str] = []
    while len(categories) < config.MAXIMUM_CATEGORIES:
        raw_category = _ask("Category (optional): ", input_fn, output)

        if not raw_category:
            break

        try:
            categories.append(config.validate_category(raw_category, categories))
        except ValueError as error:
            output.write(f"Error: {error}\n")

    try:
        folder = config.run_setup(base, categories)
    except OSError as error:
        output.write(f"Error: {error}\n")
        return 1

    output.write(f"Configured: {folder}\n")

    return folder


def _base_location(
    explicit_folder: str | None,
    input_fn: Callable[[str], str],
    output: TextIO,
) -> Path | int:
    """Finds the base folder to work in, setting it up on a first run.

    An explicit folder wins and skips the config file entirely. Otherwise the
    saved folder is used, and a first run asks for one when the command is
    interactive; when it is not, the command stops and says why.
    """
    if explicit_folder is not None:
        return Path(explicit_folder).expanduser()

    while True:
        resolved = config.resolve_base_folder()

        if resolved.state is config.BaseFolderState.OK:
            assert resolved.path is not None
            return resolved.path

        if resolved.state is config.BaseFolderState.NOT_CONFIGURED:
            if not _interactive():
                print(
                    "mktsk is not configured: no base folder saved. "
                    "Run it from a terminal to set it up.",
                    file=sys.stderr,
                )
                return EXIT_NOT_CONFIGURED

            answer = _ask(
                "mktsk is not configured yet. Start setup? [Y/n] ", input_fn, output
            )

            if answer.lower() in {"n", "no"}:
                return 1

            return _setup(input_fn, output)

        assert resolved.path is not None

        if not _interactive():
            print(
                "mktsk is not configured: the saved base folder does not exist: "
                f"{resolved.path}. Run it from a terminal to set it up.",
                file=sys.stderr,
            )
            return EXIT_NOT_CONFIGURED

        output.write(f"The saved base folder does not exist: {resolved.path}\n")
        answer = _ask(
            "[r]etry, [c]hoose another folder, [q]uit? ", input_fn, output
        ).lower()

        if answer in {"r", "retry"}:
            continue

        if answer in {"c", "choose"}:
            return _setup(input_fn, output)

        if answer in {"q", "quit"}:
            return 1


def _task_label(entry: listing.TaskEntry) -> str:
    """Formats one task as the listing shows it.

    The date of the folder, two spaces and the title read as words are what the
    GUI shows, and what goes after them is what the .md carries: the state the
    task is in, how many times it was worked on and the last of those days. A
    task whose .md cannot be read is still listed, with the date of its folder
    as its last activity and the state `open`.

    Args:
        entry: the task to format.

    Returns:
        The line that goes under a directory heading.
    """
    date = entry.date.strftime(helpers.DATE_FORMAT)
    activity = entry.last_activity.strftime(helpers.DATE_FORMAT)
    title = helpers.readable_title(entry.title)
    noun = "intervention" if entry.interventions == 1 else "interventions"

    return (
        f"{date}  {title}  ({entry.state}, {entry.interventions} {noun}, "
        f"last activity {activity})"
    )


def _list(location: Path, only: str | None = None) -> int:
    """Prints the tasks of a directory and of its categories, and opens nothing.

    Each category is a heading of its own name, the directory here included, and
    the tasks under it read as they do in the GUI: the date, two spaces, then the
    title read as words. The tasks of a category come by last activity, so the
    one you worked on last is the first. A closed task is left out by default,
    so what stands as folders is what the listing shows; `only` names a state to
    show instead, `closed` included, which is how the archives are read. A
    directory with no tasks prints nothing at all, and so does a category left
    without a task by the state filter.

    Args:
        location: the directory to list.
        only: a state to filter by, listing every task that is not closed when
            None.

    Returns:
        0.

    Raises:
        TaskError: when `only` is not a state.
    """
    if only is not None and only not in parsing.STATES:
        raise helpers.TaskError(f"invalid state: {only}")

    for group in listing.find_task_groups(location):
        if only is None:
            entries = [entry for entry in group.entries if entry.state != "closed"]
        else:
            entries = [entry for entry in group.entries if entry.state == only]
        if not entries:
            continue

        name = location.name or str(location)
        print(f"{name if group.category is None else group.category.name}/")

        for entry in entries:
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
        # an archive is the task closed, and its folder is gone: renaming it
        # is refused rather than reported as a folder that is not there
        if listing.find_task_archive(location, title) is not None:
            print(f"Error: '{title}' is already archived")
            return 1

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
    is `--close`, which archives the folder.

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


def _close(location: Path, raw_title: str) -> int:
    """Closes a task given its title, and reports the archive.

    The title is resolved the way `mktsk Foo` resolves it, by normalizing it
    and looking it up in the current directory, on any date. A title that is
    not there does not create a task. Nothing is opened: the task is over.

    Args:
        location: the directory the task belongs to.
        raw_title: the task title, as typed by the user.

    Returns:
        0 on success, 1 when the task or the archive cannot be used.
    """
    title = standards.standardize_string(raw_title)
    folder = listing.find_task_folder(location, title)

    if folder is None:
        print(f"Error: '{raw_title}' is not a task here")
        return 1

    try:
        # the .md of a task is named after the title its own folder carries,
        # so a folder renamed by hand still has its file found
        folder_title = standards.task_folder_title(folder.name) or title
        result = tasks.close_task(folder, folder_title)
    except tasks.TaskInUseError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    except (OSError, helpers.TaskError) as error:
        print(f"Error: {error}")
        return 1

    print(result.message)

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
