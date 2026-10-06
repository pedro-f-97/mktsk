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

    prefix, event_block = _split_event_block(content)
    bom = parsing.BOM if _has_bom(content) else ""

    timestamp = now.strftime(parsing._EVENT_FORMAT)
    new_event_line = f"[mktsk:{timestamp}]: # \"{state}\"\n"

    if event_block:
        new_event_block = event_block + new_event_line
    else:
        new_event_block = new_event_line

    # Build result prefix with proper spacing
    result_prefix = prefix
    if prefix:
        # Ensure blank line before event block
        stripped = prefix.rstrip("\n\r")
        if stripped:
            # Has content - need blank line
            if not prefix.endswith("\n\n"):
                trailing = len(prefix) - len(prefix.rstrip("\n\r"))
                if trailing == 0:
                    result_prefix = prefix + "\n\n"
                elif trailing == 1:
                    result_prefix = prefix + "\n"
                else:
                    result_prefix = prefix.rstrip("\n\r") + "\n\n"
            else:
                result_prefix = prefix
        else:
            result_prefix = ""
    else:
        result_prefix = ""

    return bom + result_prefix + new_event_block


def set_state(file: Path, state: str) -> bool:
    """Reads the file, sets the state, writes atomically, returns whether wrote."""
    content = file.read_text(encoding="utf-8")
    now = datetime.datetime.now().astimezone()
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
