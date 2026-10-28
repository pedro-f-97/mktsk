"""The Content toggle icon and the empty-state message of the search panel."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QToolButton

from mktsk.gui.window import _SearchResults


def _toggle(window):
    return window.search_content_checkbox


def test_toggle_is_a_checkable_tool_button_off_by_default(window):
    toggle = _toggle(window)
    assert isinstance(toggle, QToolButton)
    assert toggle.isCheckable()
    assert toggle.isChecked() is False
    assert toggle.toolTip() == "Search in content"


def test_toggle_matches_the_directory_header_buttons(window):
    toggle = _toggle(window)
    header_buttons = (
        window.choose_button,
        window.up_button,
        window.directory_tree.header_button,
        window.directory_tree.bell_button,
    )
    for button in header_buttons:
        assert toggle.iconSize() == button.iconSize()
        assert toggle.sizeHint() == button.sizeHint()


def test_toggle_on_with_nothing_searched_shows_the_hint(window, tmp_path, make_task):
    make_task(tmp_path, "260918", "SocietyLaunch")
    window.navigate_to(tmp_path)

    _toggle(window).setChecked(True)

    assert isinstance(window.search_results, _SearchResults)
    assert window.search_results._empty_message == "Press Enter to search content"
    assert window.search_results.topLevelItemCount() == 0


def test_enter_with_hits_leaves_no_message(window, tmp_path, make_task, qtbot):
    file = make_task(tmp_path, "260918", "SocietyLaunch")
    file.write_text("# 18/09/2026\n\nfindsecret here\n\n", encoding="utf-8")
    window.navigate_to(tmp_path)

    _toggle(window).setChecked(True)
    qtbot.keyClicks(window.search_input, "findsecret")
    qtbot.keyClick(window.search_input, Qt.Key.Key_Return)

    assert window.search_results.topLevelItemCount() == 1
    assert window.search_results._empty_message == ""


def test_enter_with_zero_hits_shows_no_results(window, tmp_path, make_task, qtbot):
    make_task(tmp_path, "260918", "SocietyLaunch")
    window.navigate_to(tmp_path)

    _toggle(window).setChecked(True)
    qtbot.keyClicks(window.search_input, "findsecret")
    qtbot.keyClick(window.search_input, Qt.Key.Key_Return)

    assert window.search_results.topLevelItemCount() == 0
    assert window.search_results._empty_message == "No results"


def test_editing_the_text_after_a_search_restores_the_hint(
    window, tmp_path, make_task, qtbot
):
    file = make_task(tmp_path, "260918", "SocietyLaunch")
    file.write_text("# 18/09/2026\n\nfindsecret here\n\n", encoding="utf-8")
    window.navigate_to(tmp_path)

    _toggle(window).setChecked(True)
    qtbot.keyClicks(window.search_input, "findsecret")
    qtbot.keyClick(window.search_input, Qt.Key.Key_Return)
    assert window.search_results.topLevelItemCount() == 1
    assert window.search_results._empty_message == ""

    window.search_input.setText("findsecret other")
    assert window.search_results.topLevelItemCount() == 0
    assert window.search_results._empty_message == "Press Enter to search content"


def test_toggle_off_no_message_and_title_search_while_typing(
    window, tmp_path, make_task, qtbot
):
    make_task(tmp_path, "260918", "SocietyLaunch")
    window.navigate_to(tmp_path)

    _toggle(window).setChecked(True)
    _toggle(window).setChecked(False)
    assert window.search_results._empty_message == ""

    # live title search still returns hits while typing
    window.search_input.setText("launch")
    assert window.search_results.topLevelItemCount() == 1


def test_repaint_with_a_message_raises_nothing(window, tmp_path, make_task):
    make_task(tmp_path, "260918", "SocietyLaunch")
    window.navigate_to(tmp_path)

    _toggle(window).setChecked(True)
    assert window.search_results._empty_message == "Press Enter to search content"

    window.search_results.repaint()  # must not raise, no images or grabs
