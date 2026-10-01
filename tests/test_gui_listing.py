from pathlib import Path

from PySide6.QtCore import Qt

from tests.gui_helpers import (
    find_directory,
    find_task,
    tab_labels,
    tab_titles,
    task_listing,
    tree_child_labels,
    tree_root,
)


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

