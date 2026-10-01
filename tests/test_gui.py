import shutil
from pathlib import Path

import pytest
from freezegun import freeze_time
from PySide6.QtCore import QRect, QSettings, QSize, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QMessageBox

from mktsk import gui
from mktsk.gui import _ENTRY_ROLE, MainWindow
from mktsk.gui import main as gui_main

_PATH_ROLE = Qt.ItemDataRole.UserRole


def tab_index(window, title):
    for index in range(window.tabs.count()):
        if window.tabs.tabText(index) == title:
            return index
    raise AssertionError(f"there is no {title} tab")


def tab_titles(window):
    return [window.tabs.tabText(index) for index in range(window.tabs.count())]


def task_listing(window, title="All"):
    return window.tabs.widget(tab_index(window, title))


def tab_labels(window, title="All"):
    listing = task_listing(window, title)
    return [listing.item(index).text() for index in range(listing.count())]


def select_tab(window, title):
    window.tabs.setCurrentIndex(tab_index(window, title))


def find_task(window, path, title="All"):
    listing = task_listing(window, title)
    for index in range(listing.count()):
        item = listing.item(index)
        entry = item.data(_ENTRY_ROLE)
        if entry is not None and entry.file == path:
            return item
    raise AssertionError(f"{path} is not listed in the {title} tab")


def tree_root(window):
    return window.directory_tree.topLevelItem(0)


def tree_labels(window):
    root = tree_root(window)
    if root is None:
        return []

    return [root.text(0)] + [root.child(i).text(0) for i in range(root.childCount())]


def tree_child_labels(window):
    root = tree_root(window)
    if root is None:
        return []

    return [root.child(i).text(0) for i in range(root.childCount())]


def find_directory(window, path):
    root = tree_root(window)
    for index in range(root.childCount()):
        item = root.child(index)
        if item.data(0, _PATH_ROLE) == str(path):
            return item
    raise AssertionError(f"{path} is not listed")


@pytest.fixture
def window(qtbot, tmp_path):
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    win = MainWindow(settings=settings)
    win.show()
    qtbot.addWidget(win)
    return win

@pytest.fixture
def fake_open(monkeypatch):
    opened = []

    def fake_open_file(path):
        opened.append(path)

    monkeypatch.setattr("mktsk.helpers.open_file", fake_open_file)
    return opened

@pytest.fixture
def fake_messages(monkeypatch):
    messages = {"critical": [], "warning": []}
    monkeypatch.setattr(
        QMessageBox, "critical", lambda *args: messages["critical"].append(args[2])
    )
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *args: messages["warning"].append(args[2])
    )
    return messages


def test_initial_directory_defaults_to_cwd(window):
    assert window.current_directory == Path.cwd().resolve()

def test_navigate_to_without_tasks_leaves_one_empty_tab(window, tmp_path):
    (tmp_path / "Veritas").mkdir()
    (tmp_path / "a.md").touch()

    window.navigate_to(tmp_path)

    assert tab_titles(window) == ["All"]
    assert tab_labels(window) == []
    assert tree_child_labels(window) == ["Veritas"]

def test_navigate_to_lists_a_root_task_under_the_base_heading(window, tmp_path, make_task):
    make_task(tmp_path, "260918", "ItsAlive")

    window.navigate_to(tmp_path)

    assert tab_labels(window) == [tmp_path.name, "18/09/2026  Its Alive"]

def test_navigate_to_lists_a_subdirectory_task_under_a_heading(
    window, tmp_path, make_task
):
    make_task(tmp_path / "Veritas", "260925", "FSociety")

    window.navigate_to(tmp_path)

    assert tab_labels(window) == ["Veritas", "25/09/2026  F Society"]

def test_tabs_are_all_then_base_then_subdirectories(window, tmp_path, make_task):
    make_task(tmp_path, "260918", "Foo")
    make_task(tmp_path / "Veritas", "260925", "Bar")
    make_task(tmp_path / "Able", "260924", "Baz")

    window.navigate_to(tmp_path)

    assert tab_titles(window) == ["All", tmp_path.name, "Able", "Veritas"]

def test_base_folder_is_a_category_of_its_own(window, tmp_path, make_task):
    file = make_task(tmp_path, "260918", "ItsAlive")

    window.navigate_to(tmp_path)

    assert tab_labels(window, tmp_path.name) == ["18/09/2026  Its Alive"]
    assert find_task(window, file, tmp_path.name) is not None

def test_category_tab_holds_only_its_own_tasks(window, tmp_path, make_task):
    make_task(tmp_path, "260918", "ItsAlive")
    make_task(tmp_path / "Veritas", "260925", "FSociety")

    window.navigate_to(tmp_path)

    assert tab_labels(window, "Veritas") == ["25/09/2026  F Society"]

def test_all_tab_holds_every_task_under_a_heading(window, tmp_path, make_task):
    make_task(tmp_path, "260918", "ItsAlive")
    make_task(tmp_path / "Veritas", "260925", "FSociety")

    window.navigate_to(tmp_path)

    assert tab_labels(window) == [
        tmp_path.name,
        "18/09/2026  Its Alive",
        "Veritas",
        "25/09/2026  F Society",
    ]

def test_subdirectory_without_tasks_gets_no_tab(window, tmp_path, make_task):
    make_task(tmp_path, "260918", "Foo")
    (tmp_path / "SteelMountain").mkdir()

    window.navigate_to(tmp_path)

    assert tab_titles(window) == ["All", tmp_path.name]

def test_navigate_to_sorts_tasks_newest_first(window, tmp_path, make_task):
    make_task(tmp_path, "260918", "Foo")
    make_task(tmp_path, "260930", "Bar")

    window.navigate_to(tmp_path)

    assert tab_labels(window, tmp_path.name) == ["30/09/2026  Bar", "18/09/2026  Foo"]

def test_navigate_to_invalid_date_prefix_is_not_a_task(window, tmp_path):
    (tmp_path / "999999 - ItsAlive").mkdir()

    window.navigate_to(tmp_path)

    assert tab_labels(window) == []
    assert tree_child_labels(window) == ["999999 - ItsAlive"]

def test_navigate_to_keeps_task_folders_out_of_the_tree(window, tmp_path, make_task):
    make_task(tmp_path, "260918", "Foo")
    (tmp_path / "Veritas").mkdir()

    window.navigate_to(tmp_path)

    assert tree_child_labels(window) == ["Veritas"]

def test_navigate_to_keeps_hidden_directories_out_of_the_tree(window, tmp_path):
    (tmp_path / ".hidden").mkdir()

    window.navigate_to(tmp_path)

    assert tree_child_labels(window) == []

def test_navigate_to_stops_one_level_down(window, tmp_path, make_task):
    make_task(tmp_path / "SteelMountain" / "nested", "260924", "Everbind")

    window.navigate_to(tmp_path)

    assert tab_labels(window) == []

def test_navigate_to_skips_task_folder_without_md(window, tmp_path):
    (tmp_path / "260918 - Foo").mkdir()

    window.navigate_to(tmp_path)

    assert tab_labels(window) == []

def test_task_label_splits_every_capital(window, tmp_path, make_task):
    make_task(tmp_path, "260918", "FSocietyEverbind")

    window.navigate_to(tmp_path)

    assert tab_labels(window, tmp_path.name) == ["18/09/2026  F Society Everbind"]

def test_task_label_splits_on_a_digit(window, tmp_path, make_task):
    make_task(tmp_path, "260918", "Task2")

    window.navigate_to(tmp_path)

    assert tab_labels(window, tmp_path.name) == ["18/09/2026  Task 2"]

def test_task_tooltip_is_the_full_path(window, tmp_path, make_task):
    file = make_task(tmp_path / "Veritas", "260925", "FSociety")

    window.navigate_to(tmp_path)

    assert find_task(window, file).toolTip() == str(file)

def test_section_headings_are_not_selectable(window, tmp_path, make_task):
    make_task(tmp_path / "Veritas", "260925", "FSociety")

    window.navigate_to(tmp_path)

    heading = task_listing(window).item(0)
    assert heading.text() == "Veritas"
    assert heading.flags() == Qt.ItemFlag.NoItemFlags

def test_base_title_falls_back_to_the_path(window, tmp_path):
    window.current_directory = Path(tmp_path.anchor)

    assert window._base_title() == str(window.current_directory)

def test_navigate_to_invalid_directory_falls_back(window, tmp_path):
    window.navigate_to(tmp_path / "missing")

    assert window.current_directory == Path.cwd().resolve()

def test_go_up(window, tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    window.navigate_to(sub)

    window.go_up()

    assert window.current_directory == tmp_path.resolve()

def test_go_up_at_root_stays(window):
    root = Path(Path.cwd().anchor)
    window.navigate_to(root)

    window.go_up()

    assert window.current_directory == root

def test_double_click_enters_directory(qtbot, window, tmp_path):
    sub = tmp_path / "Veritas"
    sub.mkdir()
    window.navigate_to(tmp_path)

    window.directory_tree.itemDoubleClicked.emit(find_directory(window, sub), 0)

    assert window.current_directory == sub.resolve()

def test_double_click_on_the_tree_root_does_nothing(qtbot, window, tmp_path):
    window.navigate_to(tmp_path)

    window.directory_tree.itemDoubleClicked.emit(tree_root(window), 0)

    assert window.current_directory == tmp_path.resolve()

def select_task(window, path, title="All"):
    """Selects a task row, which is what brings its action bar up."""
    listing = task_listing(window, title)
    item = find_task(window, path, title)
    listing.setCurrentItem(item)
    return listing


def action_bar(window, path, title="All"):
    return select_task(window, path, title).action_bar


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
    file.write_text("# FSociety\n\n## 18/09/2026\n\n", encoding="utf-8")
    window.navigate_to(tmp_path)

    action_bar(window, file).open_button.click()

    assert fake_open == [file.parent]
    assert file.read_text(encoding="utf-8") == "# FSociety\n\n## 18/09/2026\n\n"

def test_double_click_on_a_task_does_nothing(qtbot, window, tmp_path, fake_open, make_task):
    file = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)

    task_listing(window).itemDoubleClicked.emit(find_task(window, file))

    assert fake_open == []

@freeze_time("2026-09-30")
def test_resume_button_adds_today_and_opens(window, tmp_path, fake_open, make_task):
    file = make_task(tmp_path / "Veritas", "260918", "FSociety")
    file.write_text("# FSociety\n\n## 18/09/2026\n\nnotes\n", encoding="utf-8")
    window.navigate_to(tmp_path)

    action_bar(window, file).resume_button.click()

    assert file.read_text(encoding="utf-8") == (
        "# FSociety\n\n## 18/09/2026\n\nnotes\n\n## 30/09/2026\n\n"
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

    assert "## 30/09/2026" in file.read_text(encoding="utf-8")
    assert fake_open == [file]

def test_resume_button_reports_a_missing_file(
    window, tmp_path, monkeypatch, fake_messages, make_task
):
    file = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)

    def raise_error(folder, title):
        raise OSError("boom")

    monkeypatch.setattr("mktsk.workers.resume_task", raise_error)
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
    assert renamed.read_text(encoding="utf-8") == "# FSocietyEverbind\n"
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

def test_open_failure_warns(window, tmp_path, monkeypatch, fake_messages):
    def raise_error(path):
        raise OSError("Could not open: /somewhere")

    monkeypatch.setattr("mktsk.helpers.open_file", raise_error)

    window.open_with_default_app(tmp_path / "a.md")

    # the window shows the error as it is, the helper already words it
    assert fake_messages["warning"] == ["Could not open: /somewhere"]

@freeze_time("2026-09-28")
def test_create_task(qtbot, window, tmp_path, fake_open):
    window.navigate_to(tmp_path)
    qtbot.keyClicks(window.title_input, "Test Task")
    qtbot.keyClick(window.title_input, Qt.Key.Key_Return)

    folder = tmp_path / "260928 - TestTask"
    file = folder / "TestTask.md"
    assert file.is_file()
    assert file.read_text(encoding="utf-8") == "# TestTask\n\n## 28/09/2026\n\n"
    assert fake_open == [file]
    assert window.title_input.text() == ""
    assert "28/09/2026  Test Task" in tab_labels(window, tmp_path.name)

def test_create_task_empty_title(window, tmp_path, fake_messages):
    window.navigate_to(tmp_path)
    window.create_task()

    assert fake_messages["critical"] == ["Invalid task description."]
    assert list(tmp_path.iterdir()) == []

def test_create_task_empty_standardized(window, tmp_path, fake_messages):
    window.navigate_to(tmp_path)
    window.title_input.setText("!!!")

    window.create_task()

    assert fake_messages["critical"] == ["invalid task description"]
    assert list(tmp_path.iterdir()) == []

def test_create_task_reserved_name(window, tmp_path, fake_messages):
    window.navigate_to(tmp_path)
    window.title_input.setText("con")

    window.create_task()

    assert fake_messages["critical"] == ["'Con' is a reserved name"]
    assert list(tmp_path.iterdir()) == []

@freeze_time("2026-09-28")
def test_create_task_resumes_existing_task(window, tmp_path, fake_open):
    existing_folder = tmp_path / "260928 - TestTask"
    existing_folder.mkdir()
    existing_file = existing_folder / "TestTask.md"
    existing_file.write_text("# existing notes\n", encoding="utf-8")
    window.navigate_to(tmp_path)
    window.title_input.setText("Test Task")

    window.create_task()

    assert existing_file.read_text(encoding="utf-8") == (
        "# existing notes\n\n## 28/09/2026\n\n"
    )
    assert fake_open == [existing_file]

@freeze_time("2026-09-30")
def test_create_task_finds_existing_task_by_title(window, tmp_path, fake_open):
    folder = tmp_path / "260918 - TestTask"
    folder.mkdir()
    file = folder / "TestTask.md"
    file.write_text("# TestTask\n\n## 18/09/2026\n\nnotes\n", encoding="utf-8")
    window.navigate_to(tmp_path)
    window.title_input.setText("Test Task")

    window.create_task()

    assert file.read_text(encoding="utf-8") == (
        "# TestTask\n\n## 18/09/2026\n\nnotes\n\n## 30/09/2026\n\n"
    )
    assert fake_open == [file]
    assert window.title_input.text() == ""
    assert not (tmp_path / "260930 - TestTask").exists()

@freeze_time("2026-09-30")
def test_create_task_creates_when_task_is_in_a_subdirectory(window, tmp_path, fake_open):
    subdirectory = tmp_path / "Veritas"
    subdirectory.mkdir()
    folder = subdirectory / "260918 - TestTask"
    folder.mkdir()
    existing = folder / "TestTask.md"
    existing.write_text("# TestTask\n\n## 18/09/2026\n\n", encoding="utf-8")
    window.navigate_to(tmp_path)
    window.title_input.setText("Test Task")

    window.create_task()

    created = tmp_path / "260930 - TestTask" / "TestTask.md"

    assert created.is_file()
    assert fake_open == [created]
    assert existing.read_text(encoding="utf-8") == "# TestTask\n\n## 18/09/2026\n\n"

@freeze_time("2026-09-30")
def test_create_task_lands_in_the_base_folder_tab(window, tmp_path, fake_open, make_task):
    make_task(tmp_path / "Veritas", "260918", "Other")
    window.navigate_to(tmp_path)
    window.title_input.setText("Test Task")

    window.create_task()

    assert (tmp_path / "260930 - TestTask" / "TestTask.md").is_file()
    assert not (tmp_path / "Veritas" / "260930 - TestTask").exists()
    assert tab_labels(window, tmp_path.name) == ["30/09/2026  Test Task"]

@freeze_time("2026-09-28")
def test_create_task_open_failure_warns(window, tmp_path, monkeypatch, fake_messages):
    def raise_error(path):
        raise OSError("boom")

    monkeypatch.setattr("mktsk.helpers.open_file", raise_error)
    window.navigate_to(tmp_path)
    window.title_input.setText("Test Task")

    window.create_task()

    assert fake_messages["critical"] == []
    assert len(fake_messages["warning"]) == 1
    assert (tmp_path / "260928 - TestTask" / "TestTask.md").is_file()
    assert window.title_input.text() == ""

def test_choose_directory(window, tmp_path, monkeypatch, qtbot):
    monkeypatch.setattr(
        "PySide6.QtWidgets.QFileDialog.getExistingDirectory",
        lambda *args, **kwargs: str(tmp_path),
    )
    qtbot.mouseClick(window.choose_button, Qt.MouseButton.LeftButton)

    assert window.current_directory == tmp_path.resolve()

def test_choose_directory_cancelled(window, monkeypatch, qtbot):
    monkeypatch.setattr(
        "PySide6.QtWidgets.QFileDialog.getExistingDirectory",
        lambda *args, **kwargs: "",
    )
    before = window.current_directory
    qtbot.mouseClick(window.choose_button, Qt.MouseButton.LeftButton)

    assert window.current_directory == before

def test_up_button_navigates_up(window, tmp_path, qtbot):
    sub = tmp_path / "sub"
    sub.mkdir()
    window.navigate_to(sub)

    qtbot.mouseClick(window.up_button, Qt.MouseButton.LeftButton)

    assert window.current_directory == tmp_path.resolve()

def test_refresh_button_reloads(window, tmp_path, qtbot, make_task):
    window.navigate_to(tmp_path)
    make_task(tmp_path, "260918", "Foo")

    qtbot.mouseClick(window.refresh_button, Qt.MouseButton.LeftButton)

    assert tab_labels(window, tmp_path.name) == ["18/09/2026  Foo"]

def test_refresh_keeps_the_active_tab(window, tmp_path, make_task):
    make_task(tmp_path / "Veritas", "260925", "Foo")
    window.navigate_to(tmp_path)
    select_tab(window, "Veritas")

    window.refresh()

    assert window.tabs.tabText(window.tabs.currentIndex()) == "Veritas"

def test_refresh_falls_back_to_all_when_the_tab_is_gone(window, tmp_path, make_task):
    make_task(tmp_path / "Veritas", "260925", "Foo")
    window.navigate_to(tmp_path)
    select_tab(window, "Veritas")
    shutil.rmtree(tmp_path / "Veritas")

    window.refresh()

    assert window.tabs.tabText(window.tabs.currentIndex()) == "All"

def test_refresh_missing_directory(window, tmp_path):
    window.current_directory = tmp_path / "a.md"

    window.refresh()

    assert window.tabs.count() == 0
    assert window.directory_tree.topLevelItemCount() == 0

def test_close_saves_last_path(window, tmp_path):
    window.navigate_to(tmp_path)
    window.close()

    assert window.settings.value("last_path") == str(tmp_path.resolve())

def test_module_entry_point_uses_gui_main():
    from mktsk import __main__ as module

    assert module.main is gui_main
def test_rows_are_tall_enough_for_the_action_bar(window, tmp_path, make_task):
    make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    listing = task_listing(window)
    listing.setCurrentItem(listing.item(0))

    assert listing.visualItemRect(listing.item(0)).height() >= (
        listing.action_bar.sizeHint().height()
    )


def _ink(draw):
    """Renders an icon and returns its ink, one cell per logical pixel."""
    icon = gui._stroked_icon(QColor("#000000"), draw)
    image = icon.pixmap(QSize(gui._ICON_SIZE, gui._ICON_SIZE)).toImage()
    step = image.width() / image.deviceIndependentSize().width()
    return [
        [
            image.pixelColor(round(x * step), round(y * step)).alpha() > 0
            for x in range(gui._ICON_SIZE)
        ]
        for y in range(gui._ICON_SIZE)
    ]


def _painted(ink, along, at):
    """Whether a line of the icon has ink, across a row or a column."""
    if along == "column":
        return any(ink[y][at] for y in range(gui._ICON_SIZE))
    return any(ink[at])


def test_the_folder_outline_is_closed(qapp):
    ink = _ink(gui._draw_folder)

    # every side of a closed folder is drawn, the left one like the right one
    assert _painted(ink, "column", 1) is True
    assert _painted(ink, "column", 16) is True
    assert _painted(ink, "row", 15) is True

    # and it is an outline, not a filled block
    assert ink[11][8] is False


def test_the_folder_has_a_tab_and_not_just_a_box(qapp):
    ink = _ink(gui._draw_folder)

    # the tab stands above the body, so the top is inked on the left only
    assert ink[4][5] is True
    assert ink[4][12] is False
    assert ink[6][12] is True


def test_the_plus_is_symmetric_about_its_centre(qapp):
    ink = _ink(gui._draw_plus)
    last = gui._ICON_SIZE - 1
    centre = gui._ICON_SIZE // 2

    # the bars cross at the middle of the icon, and reach as far either side
    assert ink[centre][centre] is True
    for offset in range(gui._ICON_SIZE):
        assert ink[centre][offset] == ink[centre][last - offset]
        assert ink[offset][centre] == ink[last - offset][centre]
