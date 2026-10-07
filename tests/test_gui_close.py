from mktsk.gui.tasklist import _STATE_ROLE
from tests.gui_helpers import (
    action_bar,
    select_tab,
    tab_labels,
    tab_titles,
    task_listing,
)


def test_the_close_action_archives_without_a_dialog(
    window, tmp_path, make_task, monkeypatch, fake_open
):
    file = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)

    def fail_dialog(*args, **kwargs):
        raise AssertionError("a dialog must not be created")

    class NoDialog:
        question = staticmethod(fail_dialog)
        critical = staticmethod(fail_dialog)
        warning = staticmethod(fail_dialog)

        def __init__(self, *args, **kwargs):
            raise AssertionError("a dialog must not be created")

    monkeypatch.setattr("mktsk.gui.window.QMessageBox", NoDialog)

    action_bar(window, file).close_button.click()

    assert (tmp_path / "260918 - Foo.zip").is_file()
    assert not file.parent.exists()
    # closing is over: nothing is opened
    assert fake_open == []


def test_the_close_action_reports_a_failure(
    window, tmp_path, fake_messages, monkeypatch, make_task
):
    file = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)

    def raise_error(folder, title):
        raise OSError("boom")

    monkeypatch.setattr("mktsk.tasks.close_task", raise_error)
    action_bar(window, file).close_button.click()

    assert fake_messages["critical"] == ["boom"]
    assert file.parent.is_dir()


def test_the_close_button_carries_an_icon_and_a_tooltip(window, tmp_path, make_task):
    file = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)

    button = action_bar(window, file).close_button

    assert button.text() == ""
    assert button.icon().isNull() is False
    assert button.toolTip() == "Close this task"


def test_closing_moves_the_task_to_the_closed_tab(window, tmp_path, make_task):
    file = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)

    action_bar(window, file).close_button.click()

    assert tab_titles(window) == ["All", "Closed"]
    assert tab_labels(window) == []
    assert tab_labels(window, "Closed") == [tmp_path.name, "18/09/2026  Foo"]
    assert task_listing(window, "Closed").item(1).data(_STATE_ROLE) == "closed"


def test_closed_tasks_are_hidden_from_the_other_tabs(window, tmp_path, make_task):
    file = make_task(tmp_path, "260918", "Foo")
    make_task(tmp_path, "260917", "StillOpen")
    window.navigate_to(tmp_path)

    action_bar(window, file).close_button.click()

    open_rows = [tmp_path.name, "17/09/2026  Still Open"]
    assert tab_labels(window) == open_rows
    assert tab_labels(window, tmp_path.name) == ["17/09/2026  Still Open"]
    assert tab_labels(window, "Closed") == [tmp_path.name, "18/09/2026  Foo"]


def test_a_category_of_only_closed_tasks_leaves_the_other_tabs_alone(
    window, tmp_path, make_task
):
    make_task(tmp_path, "260917", "Root")
    file = make_task(tmp_path / "Veritas", "260918", "Foo")
    window.navigate_to(tmp_path)
    select_tab(window, "Veritas")

    action_bar(window, file, "Veritas").close_button.click()

    # no heading for the category in All, no tab for it, and the selection
    # falls back to All now that the tab it was on is gone
    assert tab_titles(window) == ["All", tmp_path.name, "Closed"]
    assert tab_labels(window) == [tmp_path.name, "17/09/2026  Root"]
    assert tab_labels(window, "Closed") == ["Veritas", "18/09/2026  Foo"]
    assert window.tabs.tabText(window.tabs.currentIndex()) == "All"


def test_there_is_no_closed_tab_without_closed_tasks(window, tmp_path, make_task):
    make_task(tmp_path, "260918", "Foo")

    window.navigate_to(tmp_path)

    assert tab_titles(window) == ["All", tmp_path.name]


def test_a_closed_row_offers_no_action_bar(window, tmp_path, make_task):
    file = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    action_bar(window, file).close_button.click()

    listing = task_listing(window, "Closed")
    listing.setCurrentItem(listing.item(1))

    assert listing.selected_entry().state == "closed"
    assert listing.delegate.inset_row == -1
    assert listing.action_bar.isVisible() is False
