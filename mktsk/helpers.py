from pathlib import Path


def validate_name(name: str) -> None:
    if Path(name).name != name:
        raise ValueError(f"name must be a single path component, got: {name!r}")