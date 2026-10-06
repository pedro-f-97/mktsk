"""State handling for task files in the new .md format.

Pure functions for reading and updating task state events, plus a thin
function that writes back to disk atomically.
"""

import datetime
from pathlib import Path

from . import helpers, parsing


def _has_bom(content: str) -> bool:
    """Returns True if the content starts with a byte order mark."""
    return content.startswith(parsing.BOM)


def _split_event_block(content: str) -> tuple[str, str]:
    """Splits the text into what precedes the final block of state events and
    the block itself, which mktsk keeps at the end of the file. A line is part
    of the block when `parsing._event` reads it as one, so the block is cut
    exactly where the parser would read the events.

    Args:
        content: the text of the .md file, without the byte order mark.

    Returns:
        The content before the block and the block itself, either empty when
        the file holds none.
    """
    lines = content.splitlines(keepends=True)
    block_start = len(lines)

    for index in range(len(lines) - 1, -1, -1):
        if parsing._event(index, lines[index]) is None:
            break
        block_start = index

    return "".join(lines[:block_start]), "".join(lines[block_start:])


def _ends_with_section(prefix: str) -> bool:
    """Tells whether a text ends with a section heading and nothing under it.

    The last line that carries text is where a note would be typed, and when
    that line dates a section, the events that follow it need two blank lines
    of their own so the note never runs into them. A heading inside a code
    block is not a section, so the lines are read the way the parser reads
    them.

    Args:
        prefix: what precedes the final block of state events.

    Returns:
        True when the last line of text is a dated level 1 heading.
    """
    last = ""

    for _number, line in parsing._readable_lines(prefix):
        if line.strip():
            last = line

    return parsing._intervention(1, last) is not None


def current_state(content: str) -> str:
    """Returns the current state of the task."""
    parsed = parsing.parse_task(content)
    events = parsed.events
    if events:
        return events[-1].state
    interventions = parsed.interventions
    if len(interventions) <= 1:
        return "open"
    return "in-progress"


def with_state(content: str, state: str, now: datetime.datetime) -> str:
    """Returns content with the state event appended."""
    if state not in parsing.STATES:
        raise helpers.TaskError(f"invalid state: {state}")

    parsed = parsing.parse_task(content)
    events = parsed.events
    if events and events[-1].state == state:
        return content

    prefix, event_block = _split_event_block(parsing.without_bom(content))
    bom = parsing.BOM if _has_bom(content) else ""

    timestamp = now.strftime(parsing._EVENT_FORMAT)
    new_event_line = f"[mktsk:{timestamp}]: # \"{state}\"\n"
    new_event_block = event_block + new_event_line

    # the block is what needs a blank line in front of it, and the whitespace
    # before an existing one is kept exactly as it is: the two blank lines a
    # section was written with must survive every state write that follows
    if event_block:
        result_prefix = prefix
    elif not prefix.strip():
        # a prefix that carries nothing leaves the block alone at the top
        result_prefix = ""
    elif _ends_with_section(prefix):
        # a section heading with nothing under it gets two blank lines, so a
        # note typed on the first one never runs into the events
        result_prefix = prefix.rstrip("\n\r") + "\n\n\n"
    elif prefix.endswith("\n\n"):
        # the text already stands apart from the block by a blank line
        result_prefix = prefix
    else:
        trailing = len(prefix) - len(prefix.rstrip("\n\r"))

        if trailing == 0:
            result_prefix = prefix + "\n\n"
        elif trailing == 1:
            result_prefix = prefix + "\n"
        else:
            result_prefix = prefix.rstrip("\n\r") + "\n\n"

    return bom + result_prefix + new_event_block


def set_state(file: Path, state: str) -> bool:
    """Reads the file, sets the state, writes atomically, returns whether wrote."""
    content = file.read_text(encoding="utf-8")
    # the event line carries no zone, so the wall clock of the machine is
    # enough and the time is kept naive, the way the format writes it
    now = datetime.datetime.now()  # noqa: DTZ005
    new_content = with_state(content, state, now)

    if new_content == content:
        return False

    tmp = file.with_name(file.name + ".tmp")
    try:
        tmp.write_text(new_content, encoding="utf-8")
        tmp.replace(file)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass

    return True
