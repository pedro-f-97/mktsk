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
        content, "in-progress", datetime.datetime(2026,10,2,9,40,tzinfo=datetime.UTC)
    )
    assert '[mktsk:2026-10-02T09:40]: # "in-progress"' in result


def test_with_state_preserves_existing_events_and_appends():
    content = """\
# 18/09/2026

Hello

[mktsk:2026-10-02T09:40]: # "in-progress"
"""
    result = state.with_state(
        content, "waiting", datetime.datetime(2026,10,2,10,0,tzinfo=datetime.UTC)
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
        content, "in-progress", datetime.datetime(2026,10,2,11,0,tzinfo=datetime.UTC)
    )
    assert result == content


def test_with_state_rejects_invalid_state():
    content = "# 18/09/2026\n"
    with pytest.raises(helpers.TaskError):
        state.with_state(content, "invalid", datetime.datetime.now(datetime.UTC))


def test_with_state_adds_blank_line_before_block():
    content = "# 18/09/2026\nHello\n"
    result = state.with_state(
        content, "waiting", datetime.datetime(2026,10,2,10,0,tzinfo=datetime.UTC)
    )
    assert "\n\n[mktsk:2026-10-02T10:00]: # \"waiting\"" in result


def test_with_state_preserves_bom():
    bom = "\ufeff"
    content = bom + "# 18/09/2026\n\nHello\n"
    result = state.with_state(
        content, "waiting", datetime.datetime(2026,10,2,10,0,tzinfo=datetime.UTC)
    )
    assert result.startswith(bom)


def test_set_state_writes_atomically(tmp_path):
    file = tmp_path / "Test.md"
    file.write_text("# 18/09/2026\n\nHello\n", encoding="utf-8")
    changed = state.set_state(file, "waiting")
    assert changed
    changed_again = state.set_state(file, "waiting")
    assert not changed_again
    assert "waiting" in file.read_text(encoding="utf-8")
