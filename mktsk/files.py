import datetime
from pathlib import Path

from . import helpers, parsing, standards

# the command that converts a tree of tasks to the format mktsk writes
_MIGRATION_COMMAND = "python -m mktsk.migration"


def _has_bom(content: str) -> bool:
    return content.startswith(parsing.BOM)


def _block_is_event_line(line: str) -> bool:
    match = parsing._EVENT.match(line)
    if match is None:
        return False
    timestamp, state = match.groups()
    if state not in parsing.STATES:
        return False
    try:
        datetime.datetime.strptime(timestamp, parsing._EVENT_FORMAT)  # noqa: DTZ007
    except ValueError:
        return False
    return True


def _split_event_block(content: str) -> tuple[str, str]:
    lines = content.splitlines(keepends=True)
    block_start = len(lines)
    for i in range(len(lines) - 1, -1, -1):
        if _block_is_event_line(lines[i]):
            block_start = i
        else:
            break
    prefix_lines = lines[:block_start]
    event_block_lines = lines[block_start:]
    return "".join(prefix_lines), "".join(event_block_lines)


def create_folder(location: Path, name: str) -> Path:
    """Creates a folder with the given name at the given location."""
    helpers.validate_name(name)

    folder_to_create = location / name

    folder_to_create.mkdir(parents=True, exist_ok=True)

    return folder_to_create


def create_md_file(location: Path, name: str) -> Path:
    """Creates an .md file with the given name at the given location"""
    helpers.validate_name(name)

    if helpers.is_reserved_name(name):
        raise helpers.TaskError(f"'{name}' is a reserved name")

    file_to_create = location / f"{name}.md"
    file_to_create.touch()

    return file_to_create


def append_date_section(file: Path, date: datetime.date) -> bool:
    """Adds a first level heading with the given date to the given .md file."""
    formatted = date.strftime(helpers.DATE_FORMAT)
    content = file.read_text(encoding="utf-8")
    bom = parsing.BOM if _has_bom(content) else ""
    content_no_bom = content[len(bom):] if bom else content

    if parsing.is_legacy(content):
        raise helpers.TaskError(
            f"'{file.name}' is in the old format: run "
            f"'{_MIGRATION_COMMAND} <folder>' to convert it"
        )

    parsed = parsing.parse_task(content)
    if any(intervention.date == date for intervention in parsed.interventions):
        return False

    prefix, event_block = _split_event_block(content_no_bom)
    body = prefix.rstrip()

    if not body:
        if event_block:
            file.write_text(f"{bom}# {formatted}\n\n{event_block}", encoding="utf-8")
        else:
            file.write_text(f"{bom}# {formatted}\n\n", encoding="utf-8")
        return True

    new_body = body
    if not new_body.endswith("\n\n"):
        trailing = len(new_body) - len(new_body.rstrip("\n\r"))
        if trailing == 0:
            new_body = new_body + "\n\n"
        elif trailing == 1:
            new_body = new_body + "\n"
        else:
            new_body = new_body.rstrip("\n\r") + "\n\n"

    new_content = bom + new_body + f"# {formatted}\n\n" + event_block
    file.write_text(new_content, encoding="utf-8")
    return True


def create_category(location: Path, raw_name: str) -> Path:
    """Creates a new category folder in the given directory."""
    name = standards._without_accents(raw_name)

    if not name.strip() or not name.isascii():
        raise helpers.TaskError("invalid category name")

    helpers.validate_name(name)

    if helpers.is_reserved_name(name):
        raise helpers.TaskError(f"'{name}' is a reserved name")

    if name.startswith("."):
        raise helpers.TaskError("invalid category name")

    if standards.is_task_folder(name) or standards._reserved_task_title(name):
        raise helpers.TaskError("invalid category name")

    category = location / name

    category.mkdir(exist_ok=True)

    return category
