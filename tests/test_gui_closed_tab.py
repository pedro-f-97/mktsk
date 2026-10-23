"""The Closed tab: the reopen button and the preview of a closed task."""

from PySide6.QtCore import QPoint, Qt

from mktsk.tasks import close_task
from tests.gui_helpers import action_bar, select_directory, select_tab, select_task


def _left_in(window, button):
    """The left edge of a button, in window coordinates."""
    return button.mapTo(window, QPoint(0, 0)).x()


def _click_result(window, qtbot, index):
    """Clicks a result of the search panel, which is what chooses a task."""
    row = window.search_results.topLevelItem(index)
    qtbot.mouseClick(
        window.search_results.viewport(),
        Qt.MouseButton.LeftButton,
        pos=window.search_results.visualItemRect(row).center(),
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
    assert window.preview_text.isReadOnly() is True
    assert "The body" in window.preview_text.toPlainText()
    assert window.preview_text_header.isVisible() is True
    assert window.preview_list_header.isVisible() is False


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

    qtbot.keyClicks(window.search_input, "naive")
    _click_result(window, qtbot, 0)

    assert window.preview_area.isHidden() is False
    # the archived .md carries the closed event
    assert "closed" in window.preview_text.toPlainText()


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
    assert window.preview_text.toPlainText() == "# 18/09/2026\n\nThe body\n"


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
    qtbot.keyClicks(window.search_input, "Low Closed")
    qtbot.waitUntil(lambda: window.search_results.topLevelItemCount() > 0)
    from tests.gui_helpers import task_listing
    listing = task_listing(window, "Closed")
    item = window.search_results.topLevelItem(0)
    assert item is not None
    window.search_results.setCurrentItem(item)
    window._activate_search_result(item, 0)

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

    qtbot.keyClicks(window.search_input, "Low Open")
    qtbot.waitUntil(lambda: window.search_results.topLevelItemCount() > 0)
    from tests.gui_helpers import task_listing
    listing = task_listing(window, "All")
    item = window.search_results.topLevelItem(0)
    assert item is not None
    window.search_results.setCurrentItem(item)
    window._activate_search_result(item, 0)

    selected_item = listing.currentItem()
    assert selected_item is not None
    row_rect = listing.visualItemRect(selected_item)
    viewport_rect = listing.viewport().rect()
    # Check vertical containment: row top and bottom within viewport
    assert viewport_rect.top() <= row_rect.top()
    assert row_rect.bottom() <= viewport_rect.bottom()
