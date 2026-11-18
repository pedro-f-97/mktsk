import datetime
from pathlib import Path

from freezegun import freeze_time
from PySide6.QtCore import QRect, Qt
from PySide6.QtWidgets import QApplication, QListWidgetItem

from mktsk import listing
from mktsk.gui.reminders_scheduler import ReminderScheduler
from mktsk.gui.selection import _SELECTION_INDICATOR_GAP
from mktsk.gui.tasklist import TaskListing
from mktsk.gui.taskrow import _COUNT_ROLE, _ENTRY_ROLE
from mktsk.tasks import close_task
from tests.gui_helpers import (
    action_bar,
    find_task,
    painted_texts,
    row_texts,
    select_tab,
    select_task,
    tab_labels,
    task_listing,
)


def test_action_bar_stays_hidden_without_a_selection(window, tmp_path, make_task):
    make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)

    assert task_listing(window).action_bar.isVisible() is False


def test_action_bar_follows_the_selected_task(window, tmp_path, make_task):
    file = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)

    bar = action_bar(window, file)

    assert bar.isVisible() is True
    assert len(bar.buttons()) == 5


def test_action_bar_sits_over_the_selected_row(window, tmp_path, make_task):
    file = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)

    listing = select_task(window, file)
    row = listing.visualItemRect(listing.currentItem())

    band_top = row.top() + listing.delegate.min_height
    assert listing.action_bar.geometry() == QRect(
        row.left() + _SELECTION_INDICATOR_GAP,
        band_top,
        listing.inset,
        row.height() - listing.delegate.min_height,
    )


def test_action_bar_shows_icons_and_not_labels(window, tmp_path, make_task):
    file = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)

    bar = action_bar(window, file)

    assert bar.buttons() == (
        bar.open_button,
        bar.resume_button,
        bar.rename_button,
        bar.state_button,
        bar.close_button,
    )
    for button in bar.buttons():
        assert button.text() == ""
        assert button.icon().isNull() is False


def test_action_bar_tooltips_name_the_actions(window, tmp_path, make_task):
    file = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)

    bar = action_bar(window, file)

    assert [button.toolTip() for button in bar.buttons()] == [
        "Open the task folder",
        "Add a note for today",
        "Rename this task",
        "Change the state of this task",
        "Close this task",
    ]


def test_action_bar_is_left_aligned(window, tmp_path, make_task):
    file = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)

    listing = select_task(window, file)
    bar = listing.action_bar
    row = listing.visualItemRect(listing.currentItem())
    lefts = [button.geometry().left() for button in bar.buttons()]

    assert lefts == sorted(lefts)
    assert bar.geometry().left() == row.left() + _SELECTION_INDICATOR_GAP
    assert bar.width() < row.width() / 2
    assert bar.buttons()[-1].geometry().right() <= bar.width()


def test_only_the_selected_row_gets_room_for_the_buttons(window, tmp_path, make_task):
    make_task(tmp_path, "260918", "Foo")
    make_task(tmp_path, "260917", "Bar")
    window.navigate_to(tmp_path)
    listing = task_listing(window)

    listing.setCurrentItem(listing.item(0))

    assert listing.delegate.inset_row == 0
    assert listing.itemDelegate() is listing.delegate


def test_the_room_for_the_buttons_goes_away_with_the_selection(
    window, tmp_path, make_task
):
    make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    listing = select_task(window, tmp_path / "260918 - Foo" / "Foo.md")

    listing.setCurrentItem(None)

    assert listing.delegate.inset_row == -1


def test_action_bar_hides_again_when_the_selection_goes(window, tmp_path, make_task):
    file = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    listing = select_task(window, file)

    listing.setCurrentItem(None)

    assert listing.action_bar.isVisible() is False


def test_action_bar_never_appears_over_a_heading(window, tmp_path, make_task):
    make_task(tmp_path, "260918", "Foo")
    make_task(tmp_path / "Veritas", "260925", "Bar")
    window.navigate_to(tmp_path)
    listing = task_listing(window)
    heading = listing.item(0)

    assert heading.flags() == Qt.ItemFlag.NoItemFlags
    assert listing.selected_entry() is None

    # Qt lets a heading become the current item, and it still gets no bar
    listing.setCurrentItem(heading)

    assert listing.selected_entry() is None
    assert listing.action_bar.isVisible() is False


def test_buttons_do_nothing_without_a_selection(
    window, tmp_path, fake_open, make_task
):
    file = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    listing = select_task(window, file)

    listing.setCurrentItem(None)
    for button in listing.action_bar.findChildren(type(listing.action_bar.open_button)):
        button.click()

    assert fake_open == []


def test_open_button_reveals_the_task_folder(window, tmp_path, fake_open, make_task):
    file = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)

    action_bar(window, file).open_button.click()

    assert fake_open == [file.parent]


def test_open_button_reveals_a_task_from_a_category_tab(
    window, tmp_path, fake_open, make_task
):
    file = make_task(tmp_path / "Veritas", "260925", "FSociety")
    window.navigate_to(tmp_path)
    select_tab(window, "Veritas")

    action_bar(window, file, "Veritas").open_button.click()

    assert fake_open == [file.parent]


def test_revealing_the_folder_leaves_the_task_untouched(
    window, tmp_path, fake_open, make_task
):
    file = make_task(tmp_path / "Veritas", "260918", "FSociety")
    file.write_text("# 18/09/2026\n\n", encoding="utf-8")
    window.navigate_to(tmp_path)

    action_bar(window, file).open_button.click()

    assert fake_open == [file.parent]
    assert file.read_text(encoding="utf-8") == "# 18/09/2026\n\n"


def test_double_click_on_a_task_does_nothing(qtbot, window, tmp_path, fake_open, make_task):
    file = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)

    task_listing(window).itemDoubleClicked.emit(find_task(window, file))

    assert fake_open == []


@freeze_time("2026-09-30")
def test_resume_button_adds_today_and_opens(window, tmp_path, fake_open, make_task):
    file = make_task(tmp_path / "Veritas", "260918", "FSociety")
    file.write_text("# 18/09/2026\n\nnotes\n", encoding="utf-8")
    window.navigate_to(tmp_path)

    action_bar(window, file).resume_button.click()

    assert file.read_text(encoding="utf-8") == (
        "# 18/09/2026\n\nnotes\n\n# 30/09/2026\n\n\n"
        '[mktsk:2026-09-30T00:00]: # "in-progress"\n'
    )
    assert fake_open == [file]


@freeze_time("2026-09-30")
def test_resume_button_resumes_a_task_outside_the_current_directory(
    window, tmp_path, fake_open, make_task
):
    file = make_task(tmp_path / "Veritas", "260918", "FSociety")
    window.navigate_to(tmp_path)
    listing = task_listing(window, "Veritas")

    listing.setCurrentItem(find_task(window, file, "Veritas"))
    listing.action_bar.resume_button.click()

    assert "# 30/09/2026" in file.read_text(encoding="utf-8")
    assert fake_open == [file]


def test_resume_button_reports_a_missing_file(
    window, tmp_path, monkeypatch, fake_messages, make_task
):
    file = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)

    def raise_error(folder, title):
        raise OSError("boom")

    monkeypatch.setattr("mktsk.tasks.resume_task", raise_error)
    action_bar(window, file).resume_button.click()

    assert fake_messages["critical"] == ["boom"]


def test_rename_button_keeps_the_date_and_updates_the_list(
    window, tmp_path, make_task, monkeypatch
):
    file = make_task(tmp_path, "260918", "FSociety")
    window.navigate_to(tmp_path)
    monkeypatch.setattr(
        "mktsk.gui.window.QInputDialog.getText", lambda *args: ("F Society Everbind", True)
    )

    action_bar(window, file).rename_button.click()

    renamed = tmp_path / "260918 - FSocietyEverbind" / "FSocietyEverbind.md"
    # the names move and the content is left as it was
    assert renamed.read_text(encoding="utf-8") == "# 18/09/2026\n\n"
    assert tab_labels(window) == [tmp_path.name, "18/09/2026  F Society Everbind"]


def test_rename_button_keeps_the_active_tab(
    window, tmp_path, make_task, monkeypatch
):
    file = make_task(tmp_path / "Veritas", "260918", "FSociety")
    window.navigate_to(tmp_path)
    select_tab(window, "Veritas")
    monkeypatch.setattr(
        "mktsk.gui.window.QInputDialog.getText", lambda *args: ("F Society Everbind", True)
    )

    action_bar(window, file, "Veritas").rename_button.click()

    assert window.tabs.tabText(window.tabs.currentIndex()) == "Veritas"


def test_cancelling_the_rename_changes_nothing(
    window, tmp_path, make_task, monkeypatch
):
    file = make_task(tmp_path, "260918", "FSociety")
    window.navigate_to(tmp_path)
    monkeypatch.setattr("mktsk.gui.window.QInputDialog.getText", lambda *args: ("", False))

    action_bar(window, file).rename_button.click()

    assert file.is_file()
    assert tab_labels(window) == [tmp_path.name, "18/09/2026  F Society"]


def test_blank_rename_changes_nothing(window, tmp_path, make_task, monkeypatch):
    file = make_task(tmp_path, "260918", "FSociety")
    window.navigate_to(tmp_path)
    monkeypatch.setattr("mktsk.gui.window.QInputDialog.getText", lambda *args: ("  ", True))

    action_bar(window, file).rename_button.click()

    assert file.is_file()
    assert tab_labels(window) == [tmp_path.name, "18/09/2026  F Society"]


def test_rename_button_reports_a_collision(
    window, tmp_path, fake_messages, make_task, monkeypatch
):
    make_task(tmp_path, "260917", "FSocietyEverbind")
    file = make_task(tmp_path, "260918", "FSociety")
    window.navigate_to(tmp_path)
    monkeypatch.setattr(
        "mktsk.gui.window.QInputDialog.getText", lambda *args: ("F Society Everbind", True)
    )

    action_bar(window, file).rename_button.click()

    assert fake_messages["critical"] == ["'FSocietyEverbind' is already a task here"]
    assert file.is_file()


# The archive button stands last in the action bar of a selected row.


class _FakeTray:
    """Records nothing: the tests never reach a notification."""

    def notify(self, title, message):
        pass


def _scheduler(tmp_path):
    return ReminderScheduler(_FakeTray(), tmp_path / "reminders.json")


def _bar_buttons(bar):
    """The widgets of the bar, in the order the layout lays them out."""
    layout = bar.layout()
    return [
        widget
        for index in range(layout.count())
        if (item := layout.itemAt(index)) is not None
        and (widget := item.widget()) is not None
    ]


def test_the_archive_button_is_last_with_a_scheduler(window, tmp_path, make_task):
    file = make_task(tmp_path, "261027", "Teste")
    window.navigate_to(tmp_path)
    window.reminder_scheduler = _scheduler(tmp_path)

    bar = action_bar(window, file)

    ordered = tuple(_bar_buttons(bar))
    assert ordered == (
        bar.open_button,
        bar.resume_button,
        bar.rename_button,
        bar.state_button,
        bar.reminders_button,
        bar.close_button,
    )
    positions = [button.geometry().x() for button in ordered]
    assert positions == sorted(positions)
    assert ordered[-1] is bar.close_button
    assert bar.close_button.geometry().x() == max(positions)


def test_the_archive_button_is_last_without_a_scheduler(window, tmp_path, make_task):
    file = make_task(tmp_path, "261027", "Teste")
    window.navigate_to(tmp_path)

    bar = action_bar(window, file)

    assert [button.isVisible() for button in bar.reminder_buttons()] == [False]
    ordered = tuple(
        button for button in _bar_buttons(bar) if button.isVisible()
    )
    assert ordered == (
        bar.open_button,
        bar.resume_button,
        bar.rename_button,
        bar.state_button,
        bar.close_button,
    )
    positions = [button.geometry().x() for button in ordered]
    assert positions == sorted(positions)
    assert ordered[-1] is bar.close_button


def test_the_other_buttons_keep_their_order(window, tmp_path, make_task):
    file = make_task(tmp_path, "261027", "Teste")
    window.navigate_to(tmp_path)
    window.reminder_scheduler = _scheduler(tmp_path)

    bar = action_bar(window, file)

    positions = {
        button: button.geometry().x()
        for button in (
            bar.open_button,
            bar.resume_button,
            bar.rename_button,
            bar.state_button,
            bar.reminders_button,
        )
    }
    assert positions[bar.open_button] < positions[bar.resume_button]
    assert positions[bar.resume_button] < positions[bar.rename_button]
    assert positions[bar.rename_button] < positions[bar.state_button]
    assert positions[bar.state_button] < positions[bar.reminders_button]


def test_the_closed_tab_still_offers_only_reopen(window, tmp_path, make_task):
    file = make_task(tmp_path, "260918", "Foo")
    close_task(file.parent, "Foo")
    window.navigate_to(tmp_path)
    select_tab(window, "Closed")

    bar = action_bar(window, tmp_path / "260918 - Foo.zip", "Closed")

    visible = [
        button
        for button in (
            bar.open_button,
            bar.resume_button,
            bar.rename_button,
            bar.state_button,
            bar.close_button,
            bar.reminders_button,
        )
        if button.isVisible()
    ]
    assert visible == [bar.resume_button]


# The auxiliary row that opens below the selected task.


def _cells(monkeypatch, rows, item):
    """Where every cell of a row was painted, in the order they are drawn."""
    painted = painted_texts(monkeypatch, rows)
    row = QRect(rows.visualItemRect(item))
    return [
        (rect.left(), rect.top(), rect.height(), text)
        for rect, _flags, text, _font in row_texts(painted, row)
    ]


def _listing_of(qtbot, count):
    """A listing short enough to scroll, holding plain task rows."""
    rows = TaskListing()
    qtbot.addWidget(rows)
    rows.resize(400, 60)
    rows.show()
    entry = listing.TaskEntry(
        date=datetime.date(2026, 9, 1),
        title="Task",
        file=Path("260901 - Task"),
        last_activity=datetime.date(2026, 9, 1),
        interventions=1,
        state="open",
    )
    for index in range(count):
        item = QListWidgetItem(f"18/09/2026  Task {index}")
        item.setData(_ENTRY_ROLE, entry)
        item.setData(_COUNT_ROLE, "1")
        rows.addItem(item)
    QApplication.processEvents()
    return rows


def test_selecting_a_task_paints_its_cells_where_they_were(
    monkeypatch, window, tmp_path, make_task
):
    file = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    rows = task_listing(window)
    item = find_task(window, file)
    plain = _cells(monkeypatch, rows, item)

    rows.setCurrentItem(item)
    selected = _cells(monkeypatch, rows, item)

    assert len(plain) == 6
    assert selected == plain


def test_an_auxiliary_row_opens_below_the_selected_task(window, tmp_path, make_task):
    file = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    rows = task_listing(window)
    item = find_task(window, file)
    plain = QRect(rows.visualItemRect(item)).height()

    rows.setCurrentItem(item)
    row = QRect(rows.visualItemRect(item))
    band_top = row.top() + rows.delegate.min_height

    assert rows.delegate.inset_row == rows.row(item)
    assert row.height() == plain + rows.delegate.accordion_height
    assert rows.action_bar.isVisible() is True
    assert rows.action_bar.geometry() == QRect(
        row.left() + _SELECTION_INDICATOR_GAP,
        band_top,
        rows.inset,
        row.bottom() - band_top + 1,
    )


def test_the_auxiliary_row_carries_the_action_icons(window, tmp_path, make_task):
    file = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    rows = select_task(window, file)
    bar = rows.action_bar

    assert len(bar.buttons()) == 5
    for button in bar.buttons():
        assert button.isVisible()
        assert button.icon().isNull() is False


def test_the_auxiliary_row_closes_when_the_selection_goes(
    window, tmp_path, make_task
):
    file = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    rows = task_listing(window)
    item = find_task(window, file)
    plain = QRect(rows.visualItemRect(item)).height()
    rows.setCurrentItem(item)

    rows.setCurrentItem(None)

    assert rows.delegate.inset_row == -1
    assert rows.action_bar.isVisible() is False
    assert QRect(rows.visualItemRect(item)).height() == plain


def test_the_auxiliary_row_is_counted_by_the_content_height(qtbot):
    rows = _listing_of(qtbot, 30)
    plain = rows.contentsSize().height()

    rows.setCurrentRow(15)

    assert plain > 0
    assert rows.contentsSize().height() == plain + rows.delegate.accordion_height
