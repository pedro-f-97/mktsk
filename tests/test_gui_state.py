from freezegun import freeze_time

from mktsk.gui.tasklist import _STATE_ROLE
from tests.gui_helpers import (
    action_bar,
    find_task,
    select_tab,
    task_listing,
)


def test_a_row_carries_the_state_of_the_task(window, tmp_path, make_task):
    file = make_task(tmp_path, "260918", "Foo")

    window.navigate_to(tmp_path)

    assert find_task(window, file).data(_STATE_ROLE) == "open"


def test_a_row_carries_the_state_written_in_the_file(window, tmp_path, make_task):
    file = make_task(tmp_path, "260918", "Foo")
    file.write_text(
        '# 18/09/2026\n\n\n[mktsk:2026-09-18T10:02]: # "waiting"\n',
        encoding="utf-8",
    )

    window.navigate_to(tmp_path)

    assert find_task(window, file).data(_STATE_ROLE) == "waiting"


def test_a_heading_carries_no_state(window, tmp_path, make_task):
    make_task(tmp_path, "260918", "Foo")

    window.navigate_to(tmp_path)

    assert task_listing(window).item(0).data(_STATE_ROLE) is None


def test_the_action_offers_the_three_open_states(window, tmp_path, make_task):
    file = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)

    menu = action_bar(window, file).state_button.menu()

    # closed only comes from closing the task, so it is not offered here
    assert [action.text() for action in menu.actions()] == [
        "open",
        "in-progress",
        "waiting",
    ]


def test_the_state_button_carries_an_icon_and_a_tooltip(window, tmp_path, make_task):
    file = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)

    button = action_bar(window, file).state_button

    assert button.text() == ""
    assert button.icon().isNull() is False
    assert button.toolTip() == "Change the state of this task"


@freeze_time("2026-10-02 09:40")
def test_the_action_changes_the_state_and_the_list(window, tmp_path, make_task):
    file = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    bar = action_bar(window, file)

    bar.state_button.menu().actions()[1].trigger()

    assert file.read_text(encoding="utf-8") == (
        '# 18/09/2026\n\n\n[mktsk:2026-10-02T09:40]: # "in-progress"\n'
    )
    assert find_task(window, file).data(_STATE_ROLE) == "in-progress"


@freeze_time("2026-10-02 09:40")
def test_the_action_keeps_the_active_tab(window, tmp_path, make_task):
    file = make_task(tmp_path / "Veritas", "260918", "Foo")
    window.navigate_to(tmp_path)
    select_tab(window, "Veritas")
    bar = action_bar(window, file, "Veritas")

    bar.state_button.menu().actions()[2].trigger()

    assert window.tabs.tabText(window.tabs.currentIndex()) == "Veritas"
    assert find_task(window, file, "Veritas").data(_STATE_ROLE) == "waiting"


def test_the_action_without_a_selection_changes_nothing(
    window, tmp_path, make_task
):
    file = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    listing = task_listing(window)
    menu = listing.action_bar.state_button.menu()
    listing.setCurrentItem(None)

    menu.actions()[1].trigger()

    assert file.read_text(encoding="utf-8") == "# 18/09/2026\n\n"
    assert listing.action_bar.isVisible() is False


def test_the_action_reports_a_failure(
    window, tmp_path, fake_messages, monkeypatch, make_task
):
    file = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    bar = action_bar(window, file)

    def raise_error(path, new_state):
        raise OSError("boom")

    monkeypatch.setattr("mktsk.state.set_state", raise_error)
    bar.state_button.menu().actions()[0].trigger()

    assert fake_messages["critical"] == ["boom"]
    assert file.read_text(encoding="utf-8") == "# 18/09/2026\n\n"
