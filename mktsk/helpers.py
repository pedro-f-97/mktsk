from pathlib import Path


def validate_name(name: str) -> None:
    """Validates that the given name is a single path component.

    Args:
        name: Name to be validated.

    Raises:
        ValueError: If the name contains path separators or is otherwise
            not a single path component.
    """
    if Path(name).name != name:
        raise ValueError(f"Name must be a single path component, got: {name!r}")