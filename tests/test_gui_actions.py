from freezegun import freeze_time
from PySide6.QtCore import QRect, Qt

from tests.gui_helpers import (
    action_bar,
    find_task,
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
    assert len(bar.buttons()) == 3


def test_action_bar_sits_over_the_selected_row(window, tmp_path, make_task):
    file = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)

    listing = select_task(window, file)
    row = listing.visualItemRect(listing.currentItem())

    assert listing.action_bar.geometry() == QRect(
        row.left(), row.top(), listing.inset, row.height()
    )


def test_action_bar_shows_icons_and_not_labels(window, tmp_path, make_task):
    file = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)

    bar = action_bar(window, file)

    assert bar.buttons() == (
        bar.open_button,
        bar.resume_button,
        bar.rename_button,
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
    ]


def test_action_bar_is_left_aligned(window, tmp_path, make_task):
    file = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)

    listing = select_task(window, file)
    bar = listing.action_bar
    row = listing.visualItemRect(listing.currentItem())
    lefts = [button.geometry().left() for button in bar.buttons()]

    assert lefts == sorted(lefts)
    assert bar.geometry().left() == row.left()
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
        "# 18/09/2026\n\nnotes\n\n# 30/09/2026\n\n"
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
        "mktsk.gui.QInputDialog.getText", lambda *args: ("F Society Everbind", True)
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
        "mktsk.gui.QInputDialog.getText", lambda *args: ("F Society Everbind", True)
    )

    action_bar(window, file, "Veritas").rename_button.click()

    assert window.tabs.tabText(window.tabs.currentIndex()) == "Veritas"


def test_cancelling_the_rename_changes_nothing(
    window, tmp_path, make_task, monkeypatch
):
    file = make_task(tmp_path, "260918", "FSociety")
    window.navigate_to(tmp_path)
    monkeypatch.setattr("mktsk.gui.QInputDialog.getText", lambda *args: ("", False))

    action_bar(window, file).rename_button.click()

    assert file.is_file()
    assert tab_labels(window) == [tmp_path.name, "18/09/2026  F Society"]


def test_blank_rename_changes_nothing(window, tmp_path, make_task, monkeypatch):
    file = make_task(tmp_path, "260918", "FSociety")
    window.navigate_to(tmp_path)
    monkeypatch.setattr("mktsk.gui.QInputDialog.getText", lambda *args: ("  ", True))

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
        "mktsk.gui.QInputDialog.getText", lambda *args: ("F Society Everbind", True)
    )

    action_bar(window, file).rename_button.click()

    assert fake_messages["critical"] == ["'FSocietyEverbind' is already a task here"]
    assert file.is_file()
