"""Reads the text of a task .md, in the format mktsk is moving to.

The rules of that format live in PLAN.md. Nothing here touches the disk: the
module takes the text of a file and gives data back, so every step that reads a
task can go through it. Nothing reads a .md yet; the task modules still work on
the old format.
"""

import datetime
import re
from collections.abc import Iterator
from typing import NamedTuple

STATES = ("open", "in-progress", "waiting", "closed")

_ISO_YEAR_LENGTH = 4
_TWO_DIGIT_YEAR_CENTURY = 2000
_EVENT_FORMAT = "%Y-%m-%dT%H:%M"

# a level 1 heading: one '#', a space and up to three spaces of indentation, so
# '#hashtag' and '## 12/01/2026' are not one
_HEADING_ONE = re.compile(r"^ {0,3}# +(.*)$")
_HEADING_TWO = re.compile(r"^ {0,3}## +(.*)$")

# the five date forms mktsk reads, the first valid candidate of a line wins. The
# boundaries keep '2026-10-02' from being read as the '26-10-02' that follows it,
# and the four digit year forms come first so '12/01/26' is not cut to '12/01/20'
_DATE_CANDIDATE = re.compile(
    r"(?<!\d)(?:\d{4}-\d{2}-\d{2}|\d{2}[/.]\d{2}[/.]\d{4}|\d{2}-\d{2}-\d{4}|\d{2}[/.]\d{2}[/.]\d{2})(?!\d)"
)
_DATE_SEPARATOR = re.compile(r"[./-]")

_EVENT = re.compile(r'^\[mktsk:(\d{4}-\d{2}-\d{2}T\d{2}:\d{2})\]: # "([^"]*)"$')

_FENCE_CHARACTERS = ("```", "~~~")


class Intervention(NamedTuple):
    """A visit to a task, as the level 1 heading that dates it.

    Attributes:
        date: the date the heading carries.
        heading: the text of the heading, the date and anything after it.
        line: the line the heading is on, counting from 1.
    """

    date: datetime.date
    heading: str
    line: int


class StateEvent(NamedTuple):
    """A change of state, as the event line that records it.

    Attributes:
        timestamp: when it happened, naive and local, as mktsk writes it.
        state: the state the task went to.
        line: the line the event is on, counting from 1.
    """

    timestamp: datetime.datetime
    state: str
    line: int


class ParsedTask(NamedTuple):
    """What the text of a task .md carries.

    Attributes:
        interventions: the visits to the task, in the order of the file.
        events: the state changes, in the order of the file.
        last_activity: the most recent date of the interventions, or None when
            the file carries none.
    """

    interventions: list[Intervention]
    events: list[StateEvent]
    last_activity: datetime.date | None


def _fence(line: str) -> str | None:
    """Tells whether a line opens or closes a code block.

    Args:
        line: the line to read.

    Returns:
        The fence character it carries, or None when it is not a fence.
    """
    stripped = line.strip()

    for character in _FENCE_CHARACTERS:
        if stripped.startswith(character):
            return character

    return None


def _readable_lines(content: str) -> Iterator[tuple[int, str]]:
    """Yields the lines of the content that carry the format.

    Lines inside a code block are left out, so a date written in one is a date
    of an example rather than of the task. The block is closed by the same
    character it was opened with, and a fence never closed runs to the end of
    the content. Both the fences themselves and their contents are left out.

    Args:
        content: the text of the .md file.

    Yields:
        The line and its number, counting from 1.
    """
    opened: str | None = None

    for number, line in enumerate(content.splitlines(), start=1):
        fence = _fence(line)

        if opened is None:
            if fence is None:
                yield number, line
            else:
                opened = fence
        elif fence == opened:
            opened = None


def _as_date(candidate: str) -> datetime.date | None:
    """Reads a date out of one of the five accepted forms.

    Args:
        candidate: the text of the date, without anything around it.

    Returns:
        The date, or None when it is not one that ever happened.
    """
    parts = _DATE_SEPARATOR.split(candidate)

    if len(parts[0]) == _ISO_YEAR_LENGTH:
        year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
    else:
        day, month, year = int(parts[0]), int(parts[1]), int(parts[2])

        # a two digit year belongs to the century mktsk is written in
        if year < 100:
            year += _TWO_DIGIT_YEAR_CENTURY

    try:
        return datetime.date(year, month, day)
    except ValueError:
        return None


def _first_date(text: str) -> datetime.date | None:
    """Reads the first date that exists in a piece of text.

    Args:
        text: the text to read, the heading of an intervention.

    Returns:
        The date, or None when the text carries no date that ever happened.
    """
    for candidate in _DATE_CANDIDATE.findall(text):
        date = _as_date(candidate)

        if date is not None:
            return date

    return None


def _intervention(line_number: int, line: str) -> Intervention | None:
    """Reads an intervention out of a line.

    Args:
        line_number: the number of the line, counting from 1.
        line: the line to read.

    Returns:
        The intervention, or None when the line is not a dated level 1 heading.
    """
    heading = _HEADING_ONE.match(line)

    if heading is None:
        return None

    date = _first_date(heading.group(1))

    if date is None:
        return None

    return Intervention(date=date, heading=heading.group(1).strip(), line=line_number)


def _event(line_number: int, line: str) -> StateEvent | None:
    """Reads a state event out of a line.

    An event that cannot be read is left out rather than refused, because a
    hand edited file is still a task file and the rest of it has to be read.

    Args:
        line_number: the number of the line, counting from 1.
        line: the line to read.

    Returns:
        The event, or None when the line is not an event mktsk wrote.
    """
    match = _EVENT.match(line)

    if match is None:
        return None

    timestamp, state = match.groups()

    if state not in STATES:
        return None

    try:
        # only the wall clock of the machine matters here, no zone to convert
        parsed = datetime.datetime.strptime(timestamp, _EVENT_FORMAT)  # noqa: DTZ007
    except ValueError:
        return None

    return StateEvent(timestamp=parsed, state=state, line=line_number)


def parse_task(content: str) -> ParsedTask:
    """Reads a task .md and returns what it carries.

    An intervention is a level 1 heading with a date that exists, a state event
    is a whole line of the form `[mktsk:YYYY-MM-DDTHH:MM]: # "state"`. Anything
    else, free text and headings of level 2 to 6 alike, is left alone.

    Args:
        content: the text of the .md file, with either line break.

    Returns:
        The interventions, the state events and the last activity of the task.
    """
    interventions: list[Intervention] = []
    events: list[StateEvent] = []

    for number, line in _readable_lines(content):
        intervention = _intervention(number, line)

        if intervention is not None:
            interventions.append(intervention)
            continue

        event = _event(number, line)

        if event is not None:
            events.append(event)

    dates = [intervention.date for intervention in interventions]

    return ParsedTask(
        interventions=interventions,
        events=events,
        last_activity=max(dates) if dates else None,
    )


def _first_title(lines: list[str]) -> str | None:
    """Reads the title an old format file opens with.

    Args:
        lines: the lines of the file, outside the code blocks.

    Returns:
        The text of the leading heading, or None when the file does not open
        with a level 1 heading carrying no date, which is what an old file does.
    """
    for line in lines:
        if not line.strip():
            continue

        heading = _HEADING_ONE.match(line)

        if heading is None or _first_date(heading.group(1)) is not None:
            return None

        return heading.group(1).strip()

    return None


def _is_dated_heading_two(line: str) -> bool:
    """Tells whether a line is a level 2 heading carrying a date.

    Args:
        line: the line to read.

    Returns:
        True when the line is a dated level 2 heading.
    """
    heading = _HEADING_TWO.match(line)

    return heading is not None and _first_date(heading.group(1)) is not None


def is_legacy(content: str) -> bool:
    """Tells whether a task .md is in the old format.

    An old file opens with `# <title>`, a level 1 heading with no date on it, and
    dates each visit with a level 2 heading. It is never read as the new format,
    so the caller can refuse it instead of mistaking the title for an
    intervention and the dated sections for notes.

    Args:
        content: the text of the .md file.

    Returns:
        True when the file is in the old format.
    """
    lines = [line for _number, line in _readable_lines(content)]

    if _first_title(lines) is None:
        return False

    return any(_is_dated_heading_two(line) for line in lines)
