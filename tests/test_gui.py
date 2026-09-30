import shutil
from pathlib import Path

import pytest
from freezegun import freeze_time
from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QMessageBox

from mktsk.gui import MainWindow
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
        if item.data(_PATH_ROLE) == str(path):
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

def test_double_click_opens_task(qtbot, window, tmp_path, fake_open, make_task):
    file = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)

    task_listing(window).itemDoubleClicked.emit(find_task(window, file))

    assert fake_open == [file]

def test_double_click_opens_task_from_a_category_tab(
    qtbot, window, tmp_path, fake_open, make_task
):
    file = make_task(tmp_path / "Veritas", "260925", "FSociety")
    window.navigate_to(tmp_path)
    select_tab(window, "Veritas")

    task_listing(window, "Veritas").itemDoubleClicked.emit(
        find_task(window, file, "Veritas")
    )

    assert fake_open == [file]

def test_double_click_leaves_the_opened_task_untouched(
    qtbot, window, tmp_path, fake_open, make_task
):
    file = make_task(tmp_path / "Veritas", "260918", "FSociety")
    file.write_text("# FSociety\n\n## 18/09/2026\n\n", encoding="utf-8")
    window.navigate_to(tmp_path)

    task_listing(window).itemDoubleClicked.emit(find_task(window, file))

    assert fake_open == [file]
    assert file.read_text(encoding="utf-8") == "# FSociety\n\n## 18/09/2026\n\n"

def test_open_failure_warns(window, tmp_path, monkeypatch, fake_messages):
    def raise_error(path):
        raise OSError("boom")

    monkeypatch.setattr("mktsk.helpers.open_file", raise_error)

    window.open_with_default_app(tmp_path / "a.md")

    assert len(fake_messages["warning"]) == 1
    assert "Could not open file" in fake_messages["warning"][0]

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