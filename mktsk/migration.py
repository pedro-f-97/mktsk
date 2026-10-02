"""Converts task .md files from the old format to the new one.

The rules of both formats are in PLAN.md. mktsk keeps writing the old format
until a later step, and this module is the only thing that reads the new one:
nothing here changes what the task modules do.

Run it over a folder of tasks with `python -m mktsk.migration <folder>`, which
only shows what it would do. Adding `--apply` writes the files, so read the
diff first and keep a backup.
"""

import argparse
import contextlib
import difflib
import os
import re
from collections import Counter
from pathlib import Path
from typing import NamedTuple

from . import listing, parsing

_WINDOWS_NEWLINE = "\r\n"

# a heading of any level, so a level 3 to 6 one can move up by one
_HEADING = re.compile(r"^( {0,3})(#{1,6})( +)(.*)$")

# what the temporary file of a write is called, so it sits beside the .md
_TEMPORARY_SUFFIX = ".part"


class Migration(NamedTuple):
    """The result of converting the text of a task .md.

    Attributes:
        content: the text in the new format.
        review: what a human has to look at, one line per warning.
    """

    content: str
    review: list[str]


class Report(NamedTuple):
    """What the migration did with one task .md.

    Attributes:
        path: the file, relative to the folder the migration was given, written
            with the separator of a diff rather than of the platform.
        status: `migrated`, `already new`, `review` or `error`.
        messages: what a human has to look at, or the error that stopped the
            file from being read or written.
        diff: the change as a unified diff, empty when there is none to show.
    """

    path: str
    status: str
    messages: list[str]
    diff: str


def _line_break(content: str) -> str:
    """Tells which line break the file uses, so it is written back the same way.

    Args:
        content: the text of the .md file, as it was read.

    Returns:
        The line break the text carries.
    """
    return _WINDOWS_NEWLINE if _WINDOWS_NEWLINE in content else "\n"


def _body(lines: list[str], title: str, review: list[str]) -> list[tuple[int, str]]:
    """Takes the title heading off the top of a file that carries one.

    The old format opens with `# <title>`, which the new one does not, so the
    heading and the blank lines under it are left out. A heading naming another
    task is content rather than the identity of this one, so it stays and the
    person migrating is asked to look at it.

    Every line that remains carries the number it had in the file, so the
    warnings point at the line they are about.

    Args:
        lines: the lines of the file.
        title: the standardized title the task folder carries.
        review: the warnings collected so far, which this adds to.

    Returns:
        The lines of the body, each with its number in the file.
    """
    start = 0

    for number, line in enumerate(lines, start=1):
        if not line.strip():
            continue

        heading = parsing._HEADING_ONE.match(line)

        # a heading with a date on it is an intervention, not the title of the
        # task, so the file is already in the new format
        if heading is not None and parsing._first_date(heading.group(1)) is None:
            text = heading.group(1).strip()

            if text.casefold() == title.casefold():
                start = number
            else:
                review.append(f"line {number}: '{text}' is not the title, left as it is")

        break

    while start < len(lines) and not lines[start].strip():
        start += 1

    return list(enumerate(lines[start:], start=start + 1))


def migrate_content(content: str, title: str) -> Migration:
    """Converts the text of a task .md from the old format to the new one.

    The `# <title>` the old format opens with is dropped and each visit, which
    was a level 2 heading with a date, becomes a level 1 one. Headings below a
    visit move up a level with it, so a date that rose from level 2 to level 1
    does not leave its own notes behind it. What cannot be converted the way the
    new format wants is left as it is and reported, because it takes a person to
    decide.

    The conversion is idempotent: a file already in the new format comes back
    the way it went in, with nothing to review.

    Args:
        content: the text of the .md file, with either line break.
        title: the standardized title the task folder carries.

    Returns:
        The text in the new format and what a human has to review.
    """
    review: list[str] = []
    lines = content.splitlines()
    newline = _line_break(content)

    # the parser is what knows a code block from the task it is written in, so
    # its lines are the only ones the format applies to
    readable = {number for number, _line in parsing._readable_lines(content)}

    result: list[str] = []
    old_section = False

    for number, line in _body(lines, title, review):
        heading = _HEADING.match(line) if number in readable else None

        if heading is None:
            result.append(line)
            continue

        indent, marks, _space, text = heading.groups()
        level = len(marks)

        # a date that never happened is not a date, so it is a heading like any
        # other and the date of a heading is what makes it an intervention
        dated = parsing._first_date(text) is not None

        if level == 2:
            if dated:
                old_section = True
                result.append(f"{indent}# {text}")
            else:
                result.append(line)

                # a level 2 heading is a note in the new format, but one that
                # sits under a date it did not date is worth a second look
                if old_section:
                    review.append(f"line {number}: '{line.strip()}' has no date, left as it is")
        elif old_section and level > 2:
            result.append(f"{indent}{'#' * (level - 1)} {text}")
        else:
            # a date that is already a level 1 heading is where the file is
            # going, and it closes a section the old format was still writing
            if level == 1 and dated:
                old_section = False

            result.append(line)

    while result and not result[-1].strip():
        result.pop()

    joined = newline.join(result)

    return Migration(content=f"{joined}{newline}" if joined else "", review=review)


def _read(file: Path) -> str:
    """Reads a .md without translating its line breaks.

    Args:
        file: the file to read.

    Returns:
        The text of the file, with the line breaks it was written with.
    """
    with open(file, encoding="utf-8", newline="") as handle:
        return handle.read()


def _write(file: Path, content: str) -> None:
    """Replaces the text of a .md through a temporary file beside it.

    A migration rewrites every file of a tree, so a failure halfway through one
    of them must not leave that one truncated. The temporary file is renamed
    over the original, which is atomic, so the file a reader sees is either the
    old one or the new one. It carries no `.md` of its own, so a folder the
    listing walks holds nothing that is not a task.

    Args:
        file: the file to write.
        content: the text to write, with the line breaks the file uses.

    Raises:
        OSError: If the text could not be written.
    """
    temporary = file.with_name(f".{file.name}{_TEMPORARY_SUFFIX}")

    try:
        with open(temporary, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)

        os.replace(temporary, file)
    except OSError:
        # the original is untouched, and what is left of the attempt is not
        # worth keeping around the task
        with contextlib.suppress(OSError):
            temporary.unlink()

        raise


def _status(migration: Migration, content: str) -> str:
    """Says what happened to one file.

    A file with something to review is reported as such whatever else changed,
    because the person running the migration is the one who has to look at it.

    Args:
        migration: the result of converting the file.
        content: the text the file had.

    Returns:
        `review`, `migrated` or `already new`.
    """
    if migration.review:
        return "review"

    return "already new" if migration.content == content else "migrated"


def _diff(path: str, before: str, after: str) -> str:
    """Builds the unified diff of what the migration would change.

    The lines are joined without the line breaks of the files, so the diff of a
    Windows task reads the same as the diff of a Linux one.

    Args:
        path: the file the diff is about.
        before: the text the file has.
        after: the text it would have.

    Returns:
        The diff, or an empty string when nothing changes.
    """
    if before == after:
        return ""

    return "\n".join(
        difflib.unified_diff(
            before.splitlines(),
            after.splitlines(),
            fromfile=path,
            tofile=path,
            lineterm="",
        )
    )


def _migrate_file(file: Path, title: str, location: Path, apply: bool) -> Report:
    """Converts one task .md and, when asked to, writes it.

    A file that cannot be read or written is reported and the migration goes on
    to the next one, because one unreadable task in a folder of hundreds is no
    reason to leave the rest untouched.

    Args:
        file: the .md of the task.
        title: the standardized title the task folder carries.
        location: the folder the migration was given, the paths are shown
            relative to it.
        apply: whether the converted text is written back.

    Returns:
        What happened to the file.
    """
    # a report is read on a screen, where a separator from either platform is
    # understood, so the two spellings of the same path read the same
    path = file.relative_to(location).as_posix()

    try:
        content = _read(file)
    except (OSError, UnicodeDecodeError) as error:
        return Report(path, "error", [str(error)], "")

    migration = migrate_content(content, title)

    if apply and migration.content != content:
        try:
            _write(file, migration.content)
        except OSError as error:
            return Report(path, "error", [str(error)], "")

    # a run that applies the change has shown it by making it, so the diff
    # belongs to the simulation, where the change is still to come
    return Report(
        path,
        _status(migration, content),
        migration.review,
        "" if apply else _diff(path, content, migration.content),
    )


def _print(report: Report) -> None:
    """Prints what happened to one file and what to look at in it.

    A blank line closes the block, so the diff of one file is never read as part
    of the file after it.

    Args:
        report: what happened to the file.
    """
    print(f"{report.path}: {report.status}")

    for message in report.messages:
        print(f"  {message}")

    if report.diff:
        print(report.diff)

    print()


def _summary(reports: list[Report]) -> str:
    """Says in one line how the whole run went.

    Args:
        reports: one entry per file the migration walked.

    Returns:
        The count of each status.
    """
    counts = Counter(report.status for report in reports)

    return (
        f"Summary: {counts['migrated']} migrated,"
        f" {counts['already new']} already new,"
        f" {counts['review']} to review,"
        f" {counts['error']} failed"
    )


def migrate_folder(location: Path, apply: bool) -> int:
    """Converts the task .md files of a directory and of its categories.

    The walk is the one the listing does: the tasks of the directory itself and
    of its immediate subdirectories, and nothing deeper. Only the `.md` named
    after the title of the folder is converted.

    Args:
        location: the folder holding the tasks.
        apply: whether the converted text is written back.

    Returns:
        0 when every file was converted, 1 when one of them failed.
    """
    location = location.resolve()

    if not location.is_dir():
        print(f"Error: {location} is not a folder")
        return 1

    if apply:
        print(f"Keep a backup of {location} before applying the migration.")
        print()

    reports = []

    for group in listing.find_task_groups(location):
        for entry in group.entries:
            reports.append(_migrate_file(entry.file, entry.title, location, apply))

    for report in reports:
        _print(report)

    print(_summary(reports))

    return 1 if any(report.status == "error" for report in reports) else 0


def build_parser() -> argparse.ArgumentParser:
    """Builds the parser for the migration.

    Returns:
        The parser.
    """
    parser = argparse.ArgumentParser(
        prog="mktsk.migration",
        description="Convert task .md files from the old format to the new one.",
    )
    parser.add_argument(
        "folder",
        help="the folder holding the tasks and their categories",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="write the migration, instead of only showing what it would do",
    )
    return parser


def parse_arguments() -> argparse.Namespace:
    """Reads what the migration was asked to do.

    Returns:
        The arguments of the command line.
    """
    return build_parser().parse_args()


def main() -> int:
    """Converts the tasks of a folder, or shows what it would do.

    Returns:
        0 when every file was converted, 1 when one of them failed.
    """
    arguments = parse_arguments()

    return migrate_folder(Path(arguments.folder), arguments.apply)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
