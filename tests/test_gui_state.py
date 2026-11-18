from freezegun import freeze_time
from PySide6.QtCore import QPoint, QSize, Qt

from mktsk.gui.icons import _ICON_SIZE
from mktsk.gui.taskrow import _STATE_ROLE
from mktsk.tasks import close_task
from tests.gui_helpers import (
    action_bar,
    find_task,
    select_directory,
    select_tab,
    select_task,
    tab_labels,
    tab_titles,
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

    # the category stands as a divider in All, it gets no tab of its own, and
    # the selection falls back to All now that the tab it was on is gone
    assert tab_titles(window) == ["All", tmp_path.name, "Closed"]
    assert tab_labels(window) == [tmp_path.name, "17/09/2026  Root", "Veritas"]
    assert tab_labels(window, "Closed") == ["Veritas", "18/09/2026  Foo"]
    assert window.tabs.tabText(window.tabs.currentIndex()) == "All"


def test_there_is_no_closed_tab_without_closed_tasks(window, tmp_path, make_task):
    make_task(tmp_path, "260918", "Foo")

    window.navigate_to(tmp_path)

    assert tab_titles(window) == ["All", tmp_path.name]


def test_a_closed_row_offers_only_the_resume_action(window, tmp_path, make_task):
    file = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    action_bar(window, file).close_button.click()

    listing = task_listing(window, "Closed")
    select_tab(window, "Closed")
    listing.setCurrentItem(listing.item(1))
    bar = listing.action_bar

    assert listing.selected_entry().state == "closed"
    # the row makes room for the bar, and the bar carries resume alone
    assert listing.delegate.inset_row == 1
    assert bar.isVisible() is True
    assert bar.resume_button.isVisible() is True
    assert bar.open_button.isVisible() is False
    assert bar.rename_button.isVisible() is False
    assert bar.state_button.isVisible() is False
    assert bar.close_button.isVisible() is False


def _rendered(button):
    """The pixels of the icon a button carries, for comparing two of them."""
    image = button.icon().pixmap(QSize(_ICON_SIZE, _ICON_SIZE)).toImage()
    step = image.width() / image.deviceIndependentSize().width()
    return [
        [
            image.pixelColor(round(x * step), round(y * step)).rgba()
            for x in range(_ICON_SIZE)
        ]
        for y in range(_ICON_SIZE)
    ]


def test_resuming_a_closed_task_reopens_it(window, tmp_path, make_task, fake_open):
    file = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    close_task(file.parent, "Foo")
    window.refresh()

    assert tab_titles(window) == ["All", "Closed"]

    select_tab(window, "Closed")
    bar = action_bar(window, tmp_path / "260918 - Foo.zip", "Closed")

    # the row of an archive offers resume alone: the other four actions all
    # speak to a folder, and only reopening makes the folder stand again
    assert bar.resume_button.isVisible() is True
    assert bar.open_button.isVisible() is False
    assert bar.rename_button.isVisible() is False
    assert bar.state_button.isVisible() is False
    assert bar.close_button.isVisible() is False

    bar.resume_button.click()

    folder = tmp_path / "260918 - Foo"
    assert folder.is_dir()
    assert not (tmp_path / "260918 - Foo.zip").exists()
    # the task is back among the open ones and its .md is opened
    assert tab_titles(window) == ["All", tmp_path.name]
    assert fake_open == [folder / "Foo.md"]
    row = task_listing(window, tmp_path.name).item(0)
    assert row.data(_STATE_ROLE) == "in-progress"


def test_resuming_a_closed_task_reports_a_failure(
    window, tmp_path, make_task, fake_messages, monkeypatch
):
    file = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    close_task(file.parent, "Foo")
    window.refresh()

    def boom(location, title):
        raise OSError("boom")

    monkeypatch.setattr("mktsk.tasks.reopen_task", boom)

    select_tab(window, "Closed")
    bar = action_bar(window, tmp_path / "260918 - Foo.zip", "Closed")
    bar.resume_button.click()

    assert fake_messages["critical"] == ["boom"]
    assert (tmp_path / "260918 - Foo.zip").exists()


def test_the_button_of_a_closed_row_has_the_reopen_tooltip(
    window, tmp_path, make_task
):
    file = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    close_task(file.parent, "Foo")
    window.refresh()

    select_tab(window, "Closed")
    bar = action_bar(window, tmp_path / "260918 - Foo.zip", "Closed")

    assert bar.resume_button.toolTip() == "Reopen this task"


def test_the_button_of_a_normal_row_keeps_the_resume_tooltip(
    window, tmp_path, make_task
):
    file = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)

    bar = action_bar(window, file)

    assert bar.resume_button.toolTip() == "Add a note for today"


def test_set_reopening_false_restores_the_resume_icon_and_tooltip(
    window, tmp_path, make_task
):
    file = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    bar = action_bar(window, file)
    icon = _rendered(bar.resume_button)
    tooltip = bar.resume_button.toolTip()

    bar.set_reopening(True)
    reopened = _rendered(bar.resume_button)

    bar.set_reopening(False)

    assert reopened != icon
    assert bar.resume_button.toolTip() == tooltip
    assert _rendered(bar.resume_button) == icon


def test_clicking_the_button_of_a_closed_row_emits_the_resume_signal(
    window, tmp_path, make_task, fake_open
):
    file = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    close_task(file.parent, "Foo")
    window.refresh()

    select_tab(window, "Closed")
    listing = task_listing(window, "Closed")
    bar = action_bar(window, tmp_path / "260918 - Foo.zip", "Closed")
    entries = []
    listing.resume_requested.connect(entries.append)

    bar.resume_button.click()

    assert [entry.file for entry in entries] == [tmp_path / "260918 - Foo.zip"]


# The Closed tab: the reopen button and the preview of a closed task.


def _left_in(window, button):
    """The left edge of a button, in window coordinates."""
    return button.mapTo(window, QPoint(0, 0)).x()


def _click_result(window, qtbot, index):
    """Clicks a result of the search panel, which is what chooses a task."""
    row = window.search_panel.search_results.topLevelItem(index)
    qtbot.mouseClick(
        window.search_panel.search_results.viewport(),
        Qt.MouseButton.LeftButton,
        pos=window.search_panel.search_results.visualItemRect(row).center(),
    )


def test_the_reopen_button_starts_where_the_first_action_starts(
    window, tmp_path, make_task
):
    active = make_task(tmp_path, "260918", "Foo")
    make_task(tmp_path, "260919", "Bar")
    close_task(tmp_path / "260919 - Bar", "Bar")
    window.navigate_to(tmp_path)

    open_left = _left_in(window, action_bar(window, active).open_button)

    select_tab(window, "Closed")
    closed_bar = action_bar(window, tmp_path / "260919 - Bar.zip", "Closed")

    assert _left_in(window, closed_bar.resume_button) == open_left


def test_the_reopen_button_is_not_centred_in_the_action_line(
    window, tmp_path, make_task
):
    file = make_task(tmp_path, "260918", "Foo")
    close_task(file.parent, "Foo")
    window.navigate_to(tmp_path)
    select_tab(window, "Closed")

    bar = action_bar(window, tmp_path / "260918 - Foo.zip", "Closed")
    geometry = bar.resume_button.geometry()

    assert geometry.left() != (bar.width() - geometry.width()) // 2


def test_selecting_a_closed_task_shows_the_archived_preview(
    window, tmp_path, make_task
):
    file = make_task(tmp_path, "260918", "Foo")
    file.write_text("# 18/09/2026\n\nThe body\n", encoding="utf-8")
    close_task(file.parent, "Foo")
    window.navigate_to(tmp_path)
    select_tab(window, "Closed")

    select_task(window, tmp_path / "260918 - Foo.zip", "Closed")

    assert window.preview_area.isHidden() is False
    assert window.preview_area.preview_text.isReadOnly() is True
    assert "The body" in window.preview_area.preview_text.toPlainText()
    assert window.preview_area.preview_text_header.isVisible() is True
    assert window.preview_area.preview_list_header.isVisible() is False


def test_switching_to_the_closed_tab_shows_the_archived_preview(
    window, tmp_path, make_task
):
    active = make_task(tmp_path, "260918", "Foo")
    make_task(tmp_path, "260919", "Bar")
    close_task(tmp_path / "260919 - Bar", "Bar")
    window.navigate_to(tmp_path)
    select_tab(window, "Closed")
    select_task(window, tmp_path / "260919 - Bar.zip", "Closed")
    assert window.preview_area.isHidden() is False

    select_tab(window, "All")
    select_task(window, active)
    assert window.preview_area.isHidden() is False

    select_tab(window, "Closed")

    assert window.preview_area.isHidden() is False


def test_a_closed_search_result_shows_the_archived_preview(
    window, tmp_path, make_task, qtbot
):
    active = make_task(tmp_path, "260918", "SocietyLaunch")
    naive = make_task(tmp_path, "260919", "NaiveBjork")
    close_task(naive.parent, "NaiveBjork")
    window.navigate_to(tmp_path)
    select_task(window, active)
    assert window.preview_area.isHidden() is False

    qtbot.keyClicks(window.search_panel.search_input, "naive")
    _click_result(window, qtbot, 0)

    assert window.preview_area.isHidden() is False
    # the archived .md carries the closed event
    assert "closed" in window.preview_area.preview_text.toPlainText()


def test_selecting_an_active_task_restores_the_title(
    window, tmp_path, make_task
):
    active = make_task(tmp_path, "260918", "Foo")
    active.write_text("# 18/09/2026\n\nThe body\n", encoding="utf-8")
    make_task(tmp_path, "260919", "Bar")
    close_task(tmp_path / "260919 - Bar", "Bar")
    window.navigate_to(tmp_path)
    select_tab(window, "Closed")
    select_task(window, tmp_path / "260919 - Bar.zip", "Closed")
    assert window.preview_area.isHidden() is False

    select_tab(window, "All")
    select_task(window, active)

    assert window.preview_area.isHidden() is False
    assert window.preview_area.preview_text.toPlainText() == "# 18/09/2026\n\nThe body\n"


def test_selecting_a_closed_task_keeps_the_new_task_destination(
    window, tmp_path, make_task
):
    file = make_task(tmp_path, "260918", "Foo")
    make_task(tmp_path / "Veritas", "260925", "NaiveBjork")
    close_task(file.parent, "Foo")
    window.navigate_to(tmp_path)
    category = (tmp_path / "Veritas").resolve()
    select_directory(window, category)
    select_tab(window, "Closed")

    select_task(window, tmp_path / "260918 - Foo.zip", "Closed")

    assert window.creation_directory() == category


def test_search_result_selects_low_closed_task_and_shows_it(
    window, tmp_path, make_task, qtbot
):
    """Picking a closed task low in the table from search shows the row fully."""
    # Create many tasks so the closed one is low in the list
    active = make_task(tmp_path, "260917", "FirstTask")
    for i in range(10):
        make_task(tmp_path, f"2609{18+i:02d}", f"Task{i}")
    file = make_task(tmp_path, "260928", "LowClosed")
    close_task(file.parent, "LowClosed")
    window.navigate_to(tmp_path)
    # Select an active task first (as the existing test does)
    from tests.gui_helpers import select_task
    select_task(window, active)
    qtbot.wait(100)

    # Search for the low task
    qtbot.keyClicks(window.search_panel.search_input, "Low Closed")
    qtbot.waitUntil(lambda: window.search_panel.search_results.topLevelItemCount() > 0)
    from tests.gui_helpers import task_listing
    listing = task_listing(window, "Closed")
    item = window.search_panel.search_results.topLevelItem(0)
    assert item is not None
    window.search_panel.search_results.setCurrentItem(item)
    window.search_panel.activate_result(item, 0)

    # The selected row should be fully visible in the table viewport (vertically)
    selected_item = listing.currentItem()
    assert selected_item is not None
    row_rect = listing.visualItemRect(selected_item)
    viewport_rect = listing.viewport().rect()
    # Check vertical containment: row top and bottom within viewport
    assert viewport_rect.top() <= row_rect.top()
    assert row_rect.bottom() <= viewport_rect.bottom()


def test_search_result_selects_low_open_task_and_shows_it(
    window, tmp_path, make_task, qtbot
):
    """Picking an open task low in the table from search shows the row fully."""
    active = make_task(tmp_path, "260917", "FirstTask")
    for i in range(10):
        make_task(tmp_path, f"2609{18+i:02d}", f"Task{i}")
    make_task(tmp_path, "260928", "LowOpen")
    window.navigate_to(tmp_path)
    # Select an active task first
    from tests.gui_helpers import select_task
    select_task(window, active)
    qtbot.wait(100)

    qtbot.keyClicks(window.search_panel.search_input, "Low Open")
    qtbot.waitUntil(lambda: window.search_panel.search_results.topLevelItemCount() > 0)
    from tests.gui_helpers import task_listing
    listing = task_listing(window, "All")
    item = window.search_panel.search_results.topLevelItem(0)
    assert item is not None
    window.search_panel.search_results.setCurrentItem(item)
    window.search_panel.activate_result(item, 0)

    selected_item = listing.currentItem()
    assert selected_item is not None
    row_rect = listing.visualItemRect(selected_item)
    viewport_rect = listing.viewport().rect()
    # Check vertical containment: row top and bottom within viewport
    assert viewport_rect.top() <= row_rect.top()
    assert row_rect.bottom() <= viewport_rect.bottom()
