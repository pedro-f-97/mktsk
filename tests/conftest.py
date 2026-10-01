import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def make_task():
    """Creates a task folder with its .md file, as mktsk would."""

    def create(directory, date, title):
        folder = directory / f"{date} - {title}"
        folder.mkdir(parents=True)
        file = folder / f"{title}.md"
        file.write_text(f"# {title}\n", encoding="utf-8")
        return file

    return create
