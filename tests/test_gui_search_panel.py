"""The search panel under the directory tree: filtering and choosing a result."""

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication

from mktsk.gui.tree import _PATH_ROLE
from tests.gui_helpers import (
    directory_header,
    find_directory,
    select_directory,
    select_tab,
    task_listing,
)


def _top(widget, ancestor):
    """The top edge of a widget in the coordinates of an ancestor."""
    return widget.mapTo(ancestor, QPoint(0, 0)).y()


def _bottom(widget, ancestor):
    """The edge just past the bottom of a widget, in an ancestor's coordinates."""
    return widget.mapTo(ancestor, QPoint(0, widget.height())).y()


def _results(window):
    """The rows the search panel shows, in order."""
    return [
        window.search_results.topLevelItem(index)
        for index in range(window.search_results.topLevelItemCount())
    ]


def _result_files(window):
    """The task paths the search results point at, in order."""
    return [row.data(0, _PATH_ROLE) for row in _results(window)]


def _click_result(window, qtbot, row):
    """Clicks a result row, which is what chooses a task."""
    qtbot.mouseClick(
        window.search_results.viewport(),
        Qt.MouseButton.LeftButton,
        pos=window.search_results.visualItemRect(row).center(),
    )


def test_typing_filters_the_results(window, tmp_path, make_task, qtbot):
    launch = make_task(tmp_path, "260918", "SocietyLaunch")
    naive = make_task(tmp_path, "260917", "NaiveBjork")
    window.navigate_to(tmp_path)

    qtbot.keyClicks(window.search_input, "society")

    assert _result_files(window) == [str(launch)]

    window.search_input.clear()
    qtbot.keyClicks(window.search_input, "naive")

    assert _result_files(window) == [str(naive)]


def test_an_empty_query_shows_no_results(window, tmp_path, make_task):
    make_task(tmp_path, "260918", "SocietyLaunch")
    window.navigate_to(tmp_path)

    assert _results(window) == []

    window.search_input.setText("   ")

    assert _results(window) == []


def test_a_result_row_shows_the_date_the_title_and_the_category(
    window, tmp_path, make_task, qtbot
):
    make_task(tmp_path, "260918", "SocietyLaunch")
    make_task(tmp_path / "Veritas", "260925", "SocietyEcho")
    window.navigate_to(tmp_path)
    qtbot.keyClicks(window.search_input, "society")
    rows = _results(window)
    dim = window.search_results.palette().color(QPalette.ColorRole.PlaceholderText)

    assert [row.text(0) for row in rows] == ["18/09/2026", "25/09/2026"]
    assert [row.text(1) for row in rows] == ["Society Launch", "Society Echo"]
    assert [row.text(2) for row in rows] == [tmp_path.name, "Veritas"]
    for row in rows:
        assert row.foreground(2).color() == dim


def test_clicking_a_result_selects_it_in_the_table(window, tmp_path, make_task, qtbot):
    file = make_task(tmp_path / "Veritas", "260925", "SocietyEcho")
    make_task(tmp_path / "Veritas", "260918", "NaiveBjork")
    window.navigate_to(tmp_path)
    select_tab(window, "Veritas")
    qtbot.keyClicks(window.search_input, "society")

    _click_result(window, qtbot, _results(window)[0])

    assert window.tabs.tabText(window.tabs.currentIndex()) == "Veritas"
    assert task_listing(window, "Veritas").selected_entry().file == file


def test_clicking_a_result_switches_to_the_tab_holding_it(
    window, tmp_path, make_task, qtbot
):
    file = make_task(tmp_path, "260918", "SocietyLaunch")
    make_task(tmp_path / "Veritas", "260925", "NaiveBjork")
    window.navigate_to(tmp_path)
    select_tab(window, "Veritas")
    qtbot.keyClicks(window.search_input, "society")

    _click_result(window, qtbot, _results(window)[0])

    # the row is not in the Veritas tab, so another tab had to take over
    assert window.tabs.tabText(window.tabs.currentIndex()) != "Veritas"
    assert window.tabs.currentWidget().listing.selected_entry().file == file
    assert task_listing(window).selected_entry().file == file


def test_enter_on_a_result_selects_it(window, tmp_path, make_task, qtbot):
    file = make_task(tmp_path, "260918", "SocietyLaunch")
    make_task(tmp_path, "260917", "NaiveBjork")
    window.navigate_to(tmp_path)
    qtbot.keyClicks(window.search_input, "society")
    window.search_results.setFocus()
    window.search_results.setCurrentItem(_results(window)[0])

    qtbot.keyClick(window.search_results, Qt.Key.Key_Return)

    assert task_listing(window).selected_entry().file == file


def test_return_in_the_search_field_selects_the_first_result(
    window, tmp_path, make_task, qtbot
):
    make_task(tmp_path, "260918", "SocietyLaunch")
    make_task(tmp_path, "260919", "SocietyEcho")
    window.navigate_to(tmp_path)
    qtbot.keyClicks(window.search_input, "society")
    assert len(_results(window)) == 2
    expected = _result_files(window)[0]

    qtbot.keyClick(window.search_input, Qt.Key.Key_Return)

    assert str(task_listing(window).selected_entry().file) == expected


def test_return_in_an_empty_search_field_selects_nothing(
    window, tmp_path, make_task, qtbot
):
    make_task(tmp_path, "260918", "SocietyLaunch")
    window.navigate_to(tmp_path)

    qtbot.keyClick(window.search_input, Qt.Key.Key_Return)

    assert task_listing(window).selected_entry() is None


def test_escape_clears_the_field_and_the_results(window, tmp_path, make_task, qtbot):
    make_task(tmp_path, "260918", "SocietyLaunch")
    window.navigate_to(tmp_path)
    qtbot.keyClicks(window.search_input, "society")
    assert len(_results(window)) == 1
    window.search_input.setFocus()

    qtbot.keyClick(window.search_input, Qt.Key.Key_Escape)

    assert window.search_input.text() == ""
    assert _results(window) == []
    assert task_listing(window).selected_entry() is None


def test_a_task_created_later_appears_in_the_results_after_a_reload(
    window, tmp_path, make_task, qtbot, fake_open
):
    make_task(tmp_path, "260918", "SocietyLaunch")
    window.navigate_to(tmp_path)
    qtbot.keyClicks(window.search_input, "society")

    window.title_input.setText("Society Echo")
    window.create_task()

    titles = [row.text(1) for row in _results(window)]
    assert len(titles) == 2
    assert "Society Echo" in titles


def test_choosing_a_result_keeps_the_new_task_destination(
    window, tmp_path, make_task, qtbot
):
    file = make_task(tmp_path, "260918", "SocietyLaunch")
    make_task(tmp_path / "Veritas", "260925", "NaiveBjork")
    window.navigate_to(tmp_path)
    category = (tmp_path / "Veritas").resolve()
    select_directory(window, category)
    qtbot.keyClicks(window.search_input, "society")

    _click_result(window, qtbot, _results(window)[0])

    assert task_listing(window).selected_entry().file == file
    assert window.creation_directory() == category
    assert window.directory_tree.currentItem() == find_directory(window, category)
    assert window.target_label.isVisible() is True


def test_the_highlighted_result_survives_a_reload(window, tmp_path, make_task, qtbot):
    make_task(tmp_path, "260918", "SocietyLaunch")
    make_task(tmp_path, "260917", "SocietyEcho")
    window.navigate_to(tmp_path)
    qtbot.keyClicks(window.search_input, "society")
    kept = _result_files(window)[1]
    window.search_results.setCurrentItem(_results(window)[1])

    window.refresh()

    current = window.search_results.currentItem()
    assert current is not None
    assert current.data(0, _PATH_ROLE) == kept


def test_a_highlight_goes_when_the_query_leaves_the_result_out(
    window, tmp_path, make_task, qtbot
):
    make_task(tmp_path, "260918", "SocietyLaunch")
    make_task(tmp_path, "260917", "SocietyEcho")
    window.navigate_to(tmp_path)
    qtbot.keyClicks(window.search_input, "society")
    assert len(_results(window)) == 2
    window.search_results.setCurrentItem(_results(window)[1])

    window.search_input.setText("launch")

    assert _result_files(window) != []
    assert window.search_results.currentItem() is None


def test_the_search_panel_sits_below_the_tree_inside_the_left_panel(window):
    container_layout = window.left_container.layout()
    splitter = window.left_splitter

    assert splitter is not None
    assert splitter.parent() is window.left_container
    assert window.left_panel.parent() is splitter
    assert window.search_panel.parent() is splitter
    assert splitter.orientation() == Qt.Orientation.Vertical
    assert _top(window.left_panel, window) < _top(window.search_panel, window)
    assert _bottom(window.left_panel, window) <= _top(window.search_panel, window)
    assert _bottom(window.search_panel, window) <= _bottom(window.left_container, window)
    assert container_layout.indexOf(splitter) >= 0
    sizes = splitter.sizes()
    assert sizes[0] > sizes[1]


def test_the_left_pane_has_a_vertical_splitter_holding_the_directory_block_and_search_panel(
    window
):
    splitter = window.left_splitter
    assert splitter is not None
    assert splitter.orientation() == Qt.Orientation.Vertical
    assert splitter.parent() is window.left_container
    assert window.left_panel.parent() is splitter
    assert window.search_panel.parent() is splitter


def test_set_sizes_changes_the_search_panel_height_and_both_stay_inside_the_left_pane(
    window
):
    splitter = window.left_splitter
    total_height = window.left_container.height()
    directory_height = total_height // 2
    search_height = total_height - directory_height
    splitter.setSizes([directory_height, search_height])

    QApplication.processEvents()

    sizes = splitter.sizes()
    assert sum(sizes) > 0
    assert all(s > 0 for s in sizes)
    assert _top(window.left_panel, window) >= _top(window.left_container, window)
    assert _bottom(window.search_panel, window) <= _bottom(window.left_container, window)


def test_the_initial_split_keeps_the_directory_block_larger(window):
    splitter = window.left_splitter
    sizes = splitter.sizes()

    assert len(sizes) == 2
    assert sizes[0] > 0
    assert sizes[1] > 0
    assert sizes[0] > sizes[1]


def test_neither_child_can_be_collapsed_to_zero_height(window):
    splitter = window.left_splitter

    splitter.setSizes([0, window.left_container.height()])
    QApplication.processEvents()

    sizes = splitter.sizes()
    assert sizes[0] > 0
    assert sizes[1] >= 0

    splitter.setSizes([window.left_container.height(), 0])
    QApplication.processEvents()

    sizes = splitter.sizes()
    assert sizes[0] >= 0
    assert sizes[1] > 0


def test_the_search_panel_keeps_the_left_pane_margin_on_its_left_and_bottom(window):
    search_margins = window.search_panel.layout().getContentsMargins()
    panel_margins = window.left_panel.layout().getContentsMargins()

    assert search_margins[0] == panel_margins[0]
    assert search_margins[3] == panel_margins[3]


def test_the_search_panel_holds_the_header_the_field_and_the_results(window):
    panel = window.search_panel

    assert window.search_header.parent() is panel
    assert window.search_input.parent() is panel
    assert window.search_results.parent() is panel
    assert _bottom(window.search_header, panel) <= _top(window.search_input, panel)
    assert _bottom(window.search_input, panel) <= _top(window.search_results, panel)
    assert window.search_results.height() > 0
    assert window.search_header.height() == directory_header(window).height()


def test_off_mode_searches_while_typing_and_excerpt_column_hidden(
    window, tmp_path, make_task, qtbot
):
    make_task(tmp_path, "260918", "SocietyLaunch")
    window.navigate_to(tmp_path)

    # OFF by default
    assert window.search_content_checkbox.isChecked() is False
    qtbot.keyClicks(window.search_input, "society")
    assert len(_results(window)) == 1
    # excerpt column hidden in off mode
    assert window.search_results.isColumnHidden(3) is True


def test_on_mode_does_not_search_while_typing_enter_runs_and_shows_excerpt(
    window, tmp_path, make_task, qtbot
):
    file = make_task(tmp_path, "260918", "SocietyLaunch")
    file.write_text("# 18/09/2026\n\nfindsecret here\n\n", encoding="utf-8")
    window.navigate_to(tmp_path)

    window.search_content_checkbox.setChecked(True)
    qtbot.keyClicks(window.search_input, "findsecret")
    # should not search while typing
    assert len(_results(window)) == 0
    qtbot.keyClick(window.search_input, Qt.Key.Key_Return)
    # should show results and excerpt column visible
    assert len(_results(window)) == 1
    assert window.search_results.isColumnHidden(3) is False


def test_toggling_clears_results_toggling_back_to_off_reruns_title_search(
    window, tmp_path, make_task, qtbot
):
    make_task(tmp_path, "260918", "SocietyLaunch")
    window.navigate_to(tmp_path)
    qtbot.keyClicks(window.search_input, "society")
    assert len(_results(window)) == 1

    window.search_content_checkbox.setChecked(True)
    assert len(_results(window)) == 0

    window.search_content_checkbox.setChecked(False)
    # toggling back to OFF re-runs the live title search for the current text
    assert len(_results(window)) == 1


def test_empty_field_gives_no_results_in_both_modes(
    window, tmp_path, make_task, qtbot
):
    make_task(tmp_path, "260918", "SocietyLaunch")
    window.navigate_to(tmp_path)

    # off mode empty
    window.search_input.clear()
    assert _results(window) == []

    # on mode empty
    window.search_content_checkbox.setChecked(True)
    window.search_input.clear()
    qtbot.keyClick(window.search_input, Qt.Key.Key_Return)
    assert _results(window) == []
