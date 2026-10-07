from pathlib import Path

from mktsk.listing import find_task_groups

# what a text file written by some editors starts with, and that is not text
BOM = "\ufeff"


def _entry(tmp_path):
    """The single task entry of a directory, which the tests below check."""
    return find_task_groups(tmp_path)[0].entries[0]


def test_entry_carries_the_state_of_the_file(tmp_path, make_task):
    file = make_task(tmp_path, "260918", "Foo")
    file.write_text(
        "# 18/09/2026\n\n\n"
        '[mktsk:2026-09-18T10:02]: # "open"\n'
        '[mktsk:2026-10-02T09:40]: # "waiting"\n',
        encoding="utf-8",
    )

    entry = _entry(tmp_path)

    # the last event in the file is the state the task is in
    assert entry.state == "waiting"


def test_entry_derives_the_state_without_events(tmp_path, make_task):
    file = make_task(tmp_path, "260918", "Foo")
    file.write_text("# 18/09/2026\n\n# 30/09/2026\n\n", encoding="utf-8")

    entry = _entry(tmp_path)

    # more than one section and no event: the task was worked on
    assert entry.state == "in-progress"


def test_entry_of_one_section_and_no_events_is_open(tmp_path, make_task):
    make_task(tmp_path, "260918", "Foo")

    entry = _entry(tmp_path)

    assert entry.state == "open"


def test_unreadable_file_is_open(tmp_path, make_task, monkeypatch):
    make_task(tmp_path, "260918", "Foo")
    real_read_text = Path.read_text

    def guarded_read_text(self, *args, **kwargs):
        if self.name == "Foo.md":
            raise PermissionError
        return real_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded_read_text)

    entry = _entry(tmp_path)

    # nothing can be read out of the file, so the task counts as open
    assert entry.state == "open"


def test_file_that_is_not_utf8_is_open(tmp_path):
    folder = tmp_path / "260918 - Foo"
    folder.mkdir()
    (folder / "Foo.md").write_bytes(b"# 18/09/2026\n\ncaf\xe9\n")

    entry = _entry(tmp_path)

    assert entry.state == "open"


def test_old_format_file_is_open(tmp_path):
    folder = tmp_path / "260918 - Foo"
    folder.mkdir()
    (folder / "Foo.md").write_text(
        "# Foo\n\n## 18/09/2026\n\nnotes\n", encoding="utf-8"
    )

    entry = _entry(tmp_path)

    # the old format is never read as the new one, so nothing says otherwise
    assert entry.state == "open"


def test_file_starting_with_a_bom_carries_its_state(tmp_path, make_task):
    file = make_task(tmp_path, "260918", "Foo")
    file.write_text(
        f'{BOM}# 18/09/2026\n\n\n[mktsk:2026-10-02T09:40]: # "in-progress"\n',
        encoding="utf-8",
    )

    entry = _entry(tmp_path)

    assert entry.state == "in-progress"
