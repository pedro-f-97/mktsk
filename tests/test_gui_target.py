import shutil

from tests.gui_helpers import select_directory, select_tab, tab_titles, tree_root


def test_creation_directory_without_a_selection(window, tmp_path):
    (tmp_path / "Veritas").mkdir()
    window.navigate_to(tmp_path)

    assert window.creation_directory() == tmp_path.resolve()


def test_creation_directory_with_the_root_selected(window, tmp_path):
    (tmp_path / "Veritas").mkdir()
    window.navigate_to(tmp_path)

    window.directory_tree.setCurrentItem(tree_root(window))

    assert window.creation_directory() == tmp_path.resolve()


def test_creation_directory_with_a_category_selected(window, tmp_path):
    (tmp_path / "Veritas").mkdir()
    window.navigate_to(tmp_path)

    select_directory(window, (tmp_path / "Veritas").resolve())

    assert window.creation_directory() == (tmp_path / "Veritas").resolve()
    assert window.current_directory == tmp_path.resolve()


def test_target_line_is_hidden_without_a_category(window, tmp_path):
    (tmp_path / "Veritas").mkdir()
    window.navigate_to(tmp_path)

    assert window.target_label.isVisible() is False


def test_target_line_is_hidden_on_the_root(window, tmp_path):
    (tmp_path / "Veritas").mkdir()
    window.navigate_to(tmp_path)

    window.directory_tree.setCurrentItem(tree_root(window))

    assert window.target_label.isVisible() is False


def test_target_line_names_the_selected_category(window, tmp_path):
    (tmp_path / "Veritas").mkdir()
    window.navigate_to(tmp_path)
    category = (tmp_path / "Veritas").resolve()

    select_directory(window, category)

    # the path label above already names the base directory
    assert window.target_label.text() == "New tasks in Veritas"
    assert window.target_label.toolTip() == str(category)
    assert window.target_label.isVisible() is True


def test_target_line_stays_on_one_line(window, tmp_path):
    (tmp_path / "Veritas").mkdir()
    window.navigate_to(tmp_path)

    select_directory(window, (tmp_path / "Veritas").resolve())

    assert window.target_label.wordWrap() is False


def test_target_line_shares_the_row_of_the_title_field(window, tmp_path):
    (tmp_path / "Veritas").mkdir()
    window.navigate_to(tmp_path)

    select_directory(window, (tmp_path / "Veritas").resolve())

    assert window.target_label.y() == window.title_input.y()
    assert window.target_label.height() == window.title_input.height()
    assert window.target_label.fontMetrics().height() == (
        window.path_label.fontMetrics().height()
    )


def test_target_line_sits_between_the_title_field_and_create(window, tmp_path):
    (tmp_path / "Veritas").mkdir()
    window.navigate_to(tmp_path)

    select_directory(window, (tmp_path / "Veritas").resolve())

    assert window.target_label.x() >= window.title_input.x() + window.title_input.width()
    assert (
        window.target_label.x() + window.target_label.width()
        <= window.create_button.x()
    )


def test_target_line_hides_again_after_navigating_into_the_category(window, tmp_path):
    (tmp_path / "Veritas").mkdir()
    window.navigate_to(tmp_path)
    select_directory(window, (tmp_path / "Veritas").resolve())

    window.navigate_to(tmp_path / "Veritas")

    assert window.creation_directory() == (tmp_path / "Veritas").resolve()
    assert window.target_label.isVisible() is False


def test_target_line_hides_again_after_navigating_away(window, tmp_path):
    (tmp_path / "Veritas").mkdir()
    (tmp_path / "SteelMountain").mkdir()
    window.navigate_to(tmp_path)
    select_directory(window, (tmp_path / "Veritas").resolve())

    window.navigate_to(tmp_path / "SteelMountain")

    assert window.creation_directory() == (tmp_path / "SteelMountain").resolve()
    assert window.target_label.isVisible() is False


def test_selecting_a_category_does_not_change_the_active_tab(window, tmp_path, make_task):
    make_task(tmp_path / "Veritas", "260925", "Bar")
    make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    select_tab(window, tmp_path.name)

    select_directory(window, (tmp_path / "Veritas").resolve())

    assert window.tabs.tabText(window.tabs.currentIndex()) == tmp_path.name


def test_selecting_a_category_does_not_reload_the_tabs(window, tmp_path, make_task):
    make_task(tmp_path / "Veritas", "260925", "Bar")
    window.navigate_to(tmp_path)
    before = tab_titles(window)

    select_directory(window, (tmp_path / "Veritas").resolve())

    assert tab_titles(window) == before


def test_the_tree_selection_survives_a_refresh(window, tmp_path):
    (tmp_path / "Veritas").mkdir()
    window.navigate_to(tmp_path)
    category = (tmp_path / "Veritas").resolve()
    select_directory(window, category)

    window.refresh()

    assert window.creation_directory() == category
    assert window.target_label.isVisible() is True


def test_the_tree_selection_is_dropped_when_the_category_is_deleted(window, tmp_path):
    category = tmp_path / "Veritas"
    category.mkdir()
    window.navigate_to(tmp_path)
    select_directory(window, category.resolve())

    shutil.rmtree(category)
    window.refresh()

    assert window.creation_directory() == tmp_path.resolve()
    assert window.target_label.isVisible() is False
