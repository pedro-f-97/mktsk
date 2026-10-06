import datetime

import pytest

from mktsk import helpers, state


def test_current_state_returns_open_with_at_most_one_intervention():
    content = "# 18/09/2026\n\nNotes\n"
    assert state.current_state(content) == "open"


def test_current_state_returns_in_progress_with_more_than_one_intervention():
    content = "# 18/09/2026\n\n# 19/09/2026\n"
    assert state.current_state(content) == "in-progress"


def test_current_state_returns_last_event_state():
    content = """\
# 18/09/2026

[mktsk:2026-10-02T09:40]: # "in-progress"
[mktsk:2026-10-02T10:00]: # "waiting"
"""
    assert state.current_state(content) == "waiting"


def test_current_state_ignores_invalid_event_state():
    content = '[mktsk:2026-10-02T10:00]: # "done"\n'
    assert state.current_state(content) == "open"


def test_with_state_appends_new_event():
    content = "# 18/09/2026\n\nHello\n"
    result = state.with_state(
        content, "in-progress", datetime.datetime.fromisoformat("2026-10-02T09:40")
    )
    assert '[mktsk:2026-10-02T09:40]: # "in-progress"' in result


def test_with_state_preserves_existing_events_and_appends():
    content = """\
# 18/09/2026

Hello

[mktsk:2026-10-02T09:40]: # "in-progress"
"""
    result = state.with_state(
        content, "waiting", datetime.datetime.fromisoformat("2026-10-02T10:00")
    )
    assert "[mktsk:2026-10-02T09:40]: # \"in-progress\"" in result
    assert "[mktsk:2026-10-02T10:00]: # \"waiting\"" in result


def test_with_state_does_not_duplicate_last_state():
    content = """\
# 18/09/2026

Hello

[mktsk:2026-10-02T09:40]: # "in-progress"
"""
    result = state.with_state(
        content, "in-progress", datetime.datetime.fromisoformat("2026-10-02T11:00")
    )
    assert result == content


def test_with_state_rejects_invalid_state():
    content = "# 18/09/2026\n"
    with pytest.raises(helpers.TaskError):
        state.with_state(
            content,
            "invalid",
            datetime.datetime.fromisoformat("2026-10-02T10:00"),
        )


def test_with_state_adds_blank_line_before_block():
    content = "# 18/09/2026\nHello\n"
    result = state.with_state(
        content, "waiting", datetime.datetime.fromisoformat("2026-10-02T10:00")
    )
    assert "\n\n[mktsk:2026-10-02T10:00]: # \"waiting\"" in result


def test_with_state_preserves_bom():
    # the mark opens the file and the split sees the text behind it, so it is
    # written once, in front of everything
    bom = "\ufeff"
    content = bom + "# 18/09/2026\n\nHello\n"
    result = state.with_state(
        content, "waiting", datetime.datetime.fromisoformat("2026-10-02T10:00")
    )
    assert result == (
        bom + '# 18/09/2026\n\nHello\n\n[mktsk:2026-10-02T10:00]: # "waiting"\n'
    )


def test_with_state_on_a_body_without_a_final_newline():
    content = "# 18/09/2026\n\nHello"
    result = state.with_state(
        content, "waiting", datetime.datetime.fromisoformat("2026-10-02T10:00")
    )
    assert result == (
        '# 18/09/2026\n\nHello\n\n[mktsk:2026-10-02T10:00]: # "waiting"\n'
    )


def test_with_state_on_a_body_with_windows_line_endings():
    content = "# 18/09/2026\r\n\r\nHello\r\n"
    result = state.with_state(
        content, "waiting", datetime.datetime.fromisoformat("2026-10-02T10:00")
    )
    assert result == (
        '# 18/09/2026\r\n\r\nHello\n\n[mktsk:2026-10-02T10:00]: # "waiting"\n'
    )


def test_with_state_on_a_body_of_blank_lines():
    content = "\n\n"
    result = state.with_state(
        content, "waiting", datetime.datetime.fromisoformat("2026-10-02T10:00")
    )
    assert result == '[mktsk:2026-10-02T10:00]: # "waiting"\n'


def test_with_state_on_a_file_of_only_events():
    content = '[mktsk:2026-10-02T09:40]: # "open"\n'
    result = state.with_state(
        content, "waiting", datetime.datetime.fromisoformat("2026-10-02T10:00")
    )
    assert result == (
        '[mktsk:2026-10-02T09:40]: # "open"\n'
        '[mktsk:2026-10-02T10:00]: # "waiting"\n'
    )


def test_set_state_writes_atomically(tmp_path):
    file = tmp_path / "Test.md"
    file.write_text("# 18/09/2026\n\nHello\n", encoding="utf-8")
    changed = state.set_state(file, "waiting")
    assert changed
    changed_again = state.set_state(file, "waiting")
    assert not changed_again
    assert "waiting" in file.read_text(encoding="utf-8")


def test_set_state_fails_when_the_file_cannot_be_written(tmp_path):
    file = tmp_path / "Test.md"
    file.write_text("# 18/09/2026\n\nHello\n", encoding="utf-8")
    # a directory where the temporary file goes makes the write fail, and the
    # temporary file cannot be removed after it either
    (tmp_path / "Test.md.tmp").mkdir()

    with pytest.raises(OSError):
        state.set_state(file, "waiting")

    assert file.read_text(encoding="utf-8") == "# 18/09/2026\n\nHello\n"
