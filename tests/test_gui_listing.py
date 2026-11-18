import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidgetItem

from mktsk import listing
from mktsk.gui.tasklist import TaskListing
from mktsk.gui.taskrow import _COUNT_ROLE, _ENTRY_ROLE
from mktsk.tasks import close_task
from tests.gui_helpers import (
    click_heading,
    fill_task,
    find_directory,
    find_task,
    select_tab,
    select_task,
    tab_labels,
    tab_titles,
    task_listing,
    task_panel,
    tree_child_labels,
    tree_root,
)


def test_initial_directory_defaults_to_cwd(window):
    assert window.current_directory == Path.cwd().resolve()


def test_navigate_to_without_tasks_leaves_one_tab(window, tmp_path):
    (tmp_path / "Veritas").mkdir()
    (tmp_path / "a.md").touch()

    window.navigate_to(tmp_path)

    assert tab_titles(window) == ["All"]
    # the category without tasks stands as a divider of its own
    assert tab_labels(window) == ["Veritas"]
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


def test_an_empty_category_stands_as_a_divider_in_the_all_tab(
    window, tmp_path, make_task
):
    make_task(tmp_path, "260918", "Foo")
    (tmp_path / "Veritas").mkdir()

    window.navigate_to(tmp_path)

    # the category stands as a divider in the All tab, and gets no tab of its
    # own and nothing in the Closed tab
    assert tab_labels(window) == [tmp_path.name, "18/09/2026  Foo", "Veritas"]
    assert tab_titles(window) == ["All", tmp_path.name]


def test_an_empty_category_stands_last_among_the_other_dividers(
    window, tmp_path, make_task
):
    make_task(tmp_path / "Able", "260925", "Foo")
    (tmp_path / "Bravo").mkdir()
    make_task(tmp_path / "monad", "260924", "Bar")

    window.navigate_to(tmp_path)

    # the divider of the empty category goes last, although its name comes
    # before the one of `monad`
    assert tab_labels(window) == [
        "Able",
        "25/09/2026  Foo",
        "monad",
        "24/09/2026  Bar",
        "Bravo",
    ]


def test_a_category_of_only_closed_tasks_stands_as_a_divider_in_the_all_tab(
    window, tmp_path, make_task
):
    file = make_task(tmp_path / "Veritas", "260925", "Foo")
    close_task(file.parent, "Foo")

    window.navigate_to(tmp_path)

    # the category stands as a divider in the All tab, and gets no tab of its
    # own; its archive is in the Closed tab
    assert tab_labels(window) == ["Veritas"]
    assert tab_titles(window) == ["All", "Closed"]
    assert tab_labels(window, "Closed") == ["Veritas", "25/09/2026  Foo"]


def test_a_category_with_an_open_task_and_a_closed_one_is_listed_once(
    window, tmp_path, make_task
):
    make_task(tmp_path / "Veritas", "260925", "Open")
    closed = make_task(tmp_path / "Veritas", "260926", "Foo")
    close_task(closed.parent, "Foo")

    window.navigate_to(tmp_path)

    # the category is listed once, under its heading with the task that still
    # stands, and it keeps a tab of its own
    assert tab_labels(window) == ["Veritas", "25/09/2026  Open"]
    assert tab_titles(window) == ["All", "Veritas", "Closed"]


def test_a_working_folder_of_only_closed_tasks_is_not_listed_in_the_all_tab(
    window, tmp_path, make_task
):
    file = make_task(tmp_path / "_scratch", "260925", "Foo")
    close_task(file.parent, "Foo")

    window.navigate_to(tmp_path)

    # a working folder is no category of its own, so it stands nowhere in the
    # All tab; its archive is still in the Closed tab
    assert tab_labels(window) == []
    assert tab_labels(window, "Closed") == ["_scratch", "25/09/2026  Foo"]


def test_navigate_to_sorts_tasks_newest_first(window, tmp_path, make_task):
    make_task(tmp_path, "260918", "Foo")
    make_task(tmp_path, "260930", "Bar")

    window.navigate_to(tmp_path)

    assert tab_labels(window, tmp_path.name) == ["30/09/2026  Bar", "18/09/2026  Foo"]


def test_navigate_to_invalid_date_prefix_is_not_a_task(window, tmp_path):
    (tmp_path / "999999 - ItsAlive").mkdir()

    window.navigate_to(tmp_path)

    # it is not a task, so it stands as a category of its own
    assert tab_labels(window) == ["999999 - ItsAlive"]
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

    # the category stands empty and the task two levels down is not found
    assert tab_labels(window) == ["SteelMountain"]


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


# Ordering the task rows by a column heading.


def _three_tasks(tmp_path, make_task):
    """Three tasks whose five columns are each in a different order."""
    fill_task(
        make_task(tmp_path, "260901", "Alpha"),
        datetime.date(2026, 9, 20),
        "waiting",
        2,
    )
    fill_task(
        make_task(tmp_path, "260903", "Bravo"),
        datetime.date(2026, 9, 10),
        "open",
        1,
    )
    fill_task(
        make_task(tmp_path, "260902", "Charlie"),
        datetime.date(2026, 9, 30),
        "in-progress",
        3,
    )


def _order(window, title):
    """The standardized titles of the task rows of a tab, in order."""
    rows = task_listing(window, title)
    return [rows.item(index).data(_ENTRY_ROLE).title for index in range(rows.count())]


def test_clicking_each_heading_sorts_ascending_then_descending(
    window, tmp_path, make_task
):
    _three_tasks(tmp_path, make_task)
    window.navigate_to(tmp_path)
    title = tmp_path.name
    ascending = {
        0: ["Alpha", "Charlie", "Bravo"],
        1: ["Alpha", "Bravo", "Charlie"],
        3: ["Bravo", "Charlie", "Alpha"],
        4: ["Bravo", "Alpha", "Charlie"],
        5: ["Bravo", "Alpha", "Charlie"],
    }

    for column, order in ascending.items():
        window.navigate_to(tmp_path)
        click_heading(window, column, title)
        assert _order(window, title) == order

        click_heading(window, column, title)
        assert _order(window, title) == list(reversed(order))


def test_ties_keep_the_default_order(window, tmp_path, make_task):
    fill_task(
        make_task(tmp_path, "260910", "Alpha"),
        datetime.date(2026, 9, 30),
        "open",
        1,
    )
    fill_task(
        make_task(tmp_path, "260910", "Beta"),
        datetime.date(2026, 9, 20),
        "open",
        1,
    )
    window.navigate_to(tmp_path)
    title = tmp_path.name

    click_heading(window, 0, title)

    assert _order(window, title) == ["Alpha", "Beta"]


def test_date_with_an_invalid_prefix_sorts_last(qtbot, tmp_path):
    rows = TaskListing()
    qtbot.addWidget(rows)
    valid = listing.TaskEntry(
        date=datetime.date(2026, 9, 1),
        title="Foo",
        file=tmp_path / "260901 - Foo" / "Foo.md",
        last_activity=datetime.date(2026, 9, 1),
        interventions=1,
        state="open",
    )
    invalid = listing.TaskEntry(
        date=datetime.date(2026, 9, 2),
        title="Bar",
        file=tmp_path / "991332 - Bar" / "Bar.md",
        last_activity=datetime.date(2026, 9, 2),
        interventions=1,
        state="open",
    )
    for entry in (invalid, valid):
        item = QListWidgetItem()
        item.setData(_ENTRY_ROLE, entry)
        item.setData(_COUNT_ROLE, str(entry.interventions))
        rows.addItem(item)

    rows.set_sort(0, False)

    assert [rows.item(index).data(_ENTRY_ROLE).title for index in range(rows.count())] == [
        "Foo",
        "Bar",
    ]


def test_task_is_case_insensitive(window, tmp_path, make_task):
    fill_task(make_task(tmp_path, "260901", "Ab"), datetime.date(2026, 9, 1), "open", 1)
    fill_task(make_task(tmp_path, "260902", "AZ"), datetime.date(2026, 9, 2), "open", 1)
    window.navigate_to(tmp_path)
    title = tmp_path.name

    click_heading(window, 1, title)

    assert _order(window, title) == ["Ab", "AZ"]


def test_interventions_is_numeric(window, tmp_path, make_task):
    fill_task(make_task(tmp_path, "260901", "Nine"), datetime.date(2026, 9, 1), "open", 9)
    fill_task(make_task(tmp_path, "260902", "Ten"), datetime.date(2026, 9, 2), "open", 10)
    window.navigate_to(tmp_path)
    title = tmp_path.name

    click_heading(window, 4, title)

    assert _order(window, title) == ["Nine", "Ten"]


def test_normal_folders_keep_their_position(window, tmp_path, make_task):
    fill_task(
        make_task(tmp_path, "260901", "Able"),
        datetime.date(2026, 9, 10),
        "open",
        1,
    )
    fill_task(
        make_task(tmp_path, "260902", "Bravo"),
        datetime.date(2026, 9, 30),
        "open",
        1,
    )
    make_task(tmp_path / "Veritas", "260903", "Zulu")
    window.navigate_to(tmp_path)

    click_heading(window, 1)

    labels = tab_labels(window)
    assert labels[0] == tmp_path.name
    assert labels[1].endswith("Able")
    assert labels[2].endswith("Bravo")
    assert labels[3] == "Veritas"
    assert labels[4].endswith("Zulu")


def test_the_sort_indicator_follows_the_heading(window, tmp_path, make_task):
    make_task(tmp_path, "260901", "Foo")
    window.navigate_to(tmp_path)
    title = tmp_path.name
    header = task_panel(window, title).header

    click_heading(window, 0, title)
    assert header.isSortIndicatorShown() is True
    assert header.sortIndicatorSection() == 0
    assert header.sortIndicatorOrder() == Qt.SortOrder.AscendingOrder

    click_heading(window, 3, title)
    assert header.sortIndicatorSection() == 3
    assert header.sortIndicatorOrder() == Qt.SortOrder.AscendingOrder

    click_heading(window, 3, title)
    assert header.sortIndicatorSection() == 3
    assert header.sortIndicatorOrder() == Qt.SortOrder.DescendingOrder


def test_dragging_a_separator_resizes_without_sorting(window, tmp_path, make_task):
    _three_tasks(tmp_path, make_task)
    window.navigate_to(tmp_path)
    title = tmp_path.name
    click_heading(window, 0, title)
    before = _order(window, title)
    header = task_panel(window, title).header
    width = header.sectionSize(0)

    header.resizeSection(0, width + 30)

    assert header.sectionSize(0) == width + 30
    assert _order(window, title) == before


def test_refresh_keeps_the_order(window, tmp_path, make_task):
    _three_tasks(tmp_path, make_task)
    window.navigate_to(tmp_path)
    title = tmp_path.name
    click_heading(window, 1, title)
    before = _order(window, title)

    window.refresh()

    assert _order(window, title) == before


def test_the_selected_task_stays_selected_after_a_resort(window, tmp_path, make_task):
    _three_tasks(tmp_path, make_task)
    window.navigate_to(tmp_path)
    title = tmp_path.name
    select_tab(window, title)
    file = tmp_path / "260901 - Alpha" / "Alpha.md"
    listing_ = select_task(window, file, title)
    selected = listing_.currentItem()

    click_heading(window, 1, title)

    assert listing_.currentItem() is selected
    assert listing_.selected_entry().file == file
    assert listing_.action_bar.isVisible() is True


def test_two_tabs_keep_independent_sorting(window, tmp_path, make_task):
    fill_task(make_task(tmp_path, "260901", "Zulu"), datetime.date(2026, 9, 1), "open", 1)
    fill_task(make_task(tmp_path, "260902", "Alpha"), datetime.date(2026, 9, 2), "open", 1)
    make_task(tmp_path / "Veritas", "260903", "Charlie")
    make_task(tmp_path / "Veritas", "260904", "Delta")
    window.navigate_to(tmp_path)

    click_heading(window, 0, tmp_path.name)
    click_heading(window, 1, "Veritas")
    window.refresh()

    assert _order(window, tmp_path.name) == ["Zulu", "Alpha"]
    assert _order(window, "Veritas") == ["Charlie", "Delta"]


# The order of the categories when a column heading is clicked.


def _categories(window, title="All"):
    """The heading and the standardized task titles of every category, in order."""
    rows = task_listing(window, title)
    result = []
    for index in range(rows.count()):
        item = rows.item(index)
        entry = item.data(_ENTRY_ROLE)
        if entry is None:
            result.append((item.text(), []))
        else:
            result[-1][1].append(entry.title)
    return result


def _headings(window, title="All"):
    """The heading of every category of a tab, in order."""
    return [heading for heading, _ in _categories(window, title)]


def _three_categories(tmp_path, make_task):
    """Three categories whose columns are each in a different order.

    The base category holds Mango, `Alpha` holds Zebra and `Zeta` holds Apple,
    with dates, states, counts and activities chosen so that every column puts
    the three categories in a different order.
    """
    fill_task(
        make_task(tmp_path, "260905", "Mango"),
        datetime.date(2026, 9, 10),
        "waiting",
        2,
    )
    fill_task(
        make_task(tmp_path / "Alpha", "260902", "Zebra"),
        datetime.date(2026, 9, 20),
        "open",
        1,
    )
    fill_task(
        make_task(tmp_path / "Zeta", "260910", "Apple"),
        datetime.date(2026, 9, 30),
        "in-progress",
        3,
    )


def _categories_and_empty_ones(tmp_path, make_task):
    """The three categories of `_three_categories` and two empty ones.

    `Delta` and `Omega` hold no task at all, so they stand as dividers of
    their own, and they come before the other categories in alphabetical
    order, so a divider that goes last is told apart from one that keeps its
    place among the others.
    """
    _three_categories(tmp_path, make_task)
    (tmp_path / "Delta").mkdir()
    (tmp_path / "Omega").mkdir()


def test_categories_keep_their_place_until_a_heading_is_clicked(
    window, tmp_path, make_task
):
    _three_categories(tmp_path, make_task)
    window.navigate_to(tmp_path)

    assert _headings(window) == [tmp_path.name, "Alpha", "Zeta"]


def test_categories_follow_the_column_being_sorted(window, tmp_path, make_task):
    _three_categories(tmp_path, make_task)
    window.navigate_to(tmp_path)
    base = tmp_path.name
    ascending = {
        0: ["Alpha", base, "Zeta"],
        1: ["Zeta", base, "Alpha"],
        3: ["Alpha", "Zeta", base],
        4: ["Alpha", base, "Zeta"],
        5: [base, "Alpha", "Zeta"],
    }

    for column, order in ascending.items():
        window.navigate_to(tmp_path)
        click_heading(window, column)
        assert _headings(window) == order

        click_heading(window, column)
        assert _headings(window) == list(reversed(order))


def test_empty_categories_go_last_without_a_sort(window, tmp_path, make_task):
    _categories_and_empty_ones(tmp_path, make_task)
    window.navigate_to(tmp_path)

    # the categories that hold tasks come first, and the empty ones follow,
    # in alphabetical order between themselves
    assert _headings(window) == [tmp_path.name, "Alpha", "Zeta", "Delta", "Omega"]


def test_empty_categories_go_last_whatever_the_sort(window, tmp_path, make_task):
    _categories_and_empty_ones(tmp_path, make_task)
    window.navigate_to(tmp_path)
    base = tmp_path.name
    ascending = {
        0: ["Alpha", base, "Zeta"],
        1: ["Zeta", base, "Alpha"],
        3: ["Alpha", "Zeta", base],
        4: ["Alpha", base, "Zeta"],
        5: [base, "Alpha", "Zeta"],
    }

    for column, order in ascending.items():
        window.navigate_to(tmp_path)
        click_heading(window, column)
        assert _headings(window) == order + ["Delta", "Omega"]

        click_heading(window, column)
        assert _headings(window) == list(reversed(order)) + ["Delta", "Omega"]


def test_the_tasks_inside_a_category_are_ordered_too(window, tmp_path, make_task):
    make_task(tmp_path, "260902", "Foo")
    make_task(tmp_path, "260901", "Bar")
    make_task(tmp_path / "Alpha", "260904", "Baz")
    make_task(tmp_path / "Alpha", "260903", "Qux")
    window.navigate_to(tmp_path)

    click_heading(window, 0)

    assert _categories(window) == [
        (tmp_path.name, ["Bar", "Foo"]),
        ("Alpha", ["Qux", "Baz"]),
    ]


def test_tied_categories_keep_the_order_they_had(window, tmp_path, make_task):
    fill_task(
        make_task(tmp_path / "Alpha", "260901", "Able"),
        datetime.date(2026, 9, 9),
        "open",
        1,
    )
    fill_task(
        make_task(tmp_path / "Beta", "260901", "Bravo"),
        datetime.date(2026, 9, 9),
        "open",
        1,
    )
    window.navigate_to(tmp_path)

    click_heading(window, 0)
    assert _headings(window) == ["Alpha", "Beta"]

    click_heading(window, 0)
    assert _headings(window) == ["Alpha", "Beta"]


def _visible_labels(window, title="All"):
    listing = task_listing(window, title)
    return [
        listing.item(index).text()
        for index in range(listing.count())
        if not listing.item(index).isHidden()
    ]


def _states_fixture(tmp_path, make_task):
    """A waiting task in the base folder and an open one in a category."""
    day = datetime.date(2026, 9, 30)
    fill_task(make_task(tmp_path, "260918", "Foo"), day, "waiting", 1)
    (tmp_path / "Infra").mkdir()
    fill_task(make_task(tmp_path / "Infra", "260919", "Bar"), day, "open", 1)


def test_the_state_filter_hides_other_states_and_empty_headings(
    window, tmp_path, make_task
):
    _states_fixture(tmp_path, make_task)
    window.navigate_to(tmp_path)

    window.set_state_filter("waiting")

    assert _visible_labels(window) == [tmp_path.name, "18/09/2026  Foo"]
    assert window.state_filter_button.isChecked() is True
    assert window.state_filter_button.toolTip() == "Filter by state: waiting"


def test_all_states_shows_every_task_again(window, tmp_path, make_task):
    _states_fixture(tmp_path, make_task)
    window.navigate_to(tmp_path)
    before = _visible_labels(window)
    window.set_state_filter("waiting")

    window.set_state_filter(None)

    assert _visible_labels(window) == before
    assert window.state_filter_button.isChecked() is False


def test_the_state_filter_survives_a_refresh_and_a_sort(window, tmp_path, make_task):
    _states_fixture(tmp_path, make_task)
    window.navigate_to(tmp_path)
    window.set_state_filter("open")

    window.refresh()
    click_heading(window, 1)

    assert _visible_labels(window) == ["Infra", "19/09/2026  Bar"]


def test_the_state_filter_leaves_the_closed_tab_alone(window, tmp_path, make_task):
    file = make_task(tmp_path, "260918", "Foo")
    close_task(file.parent, "Foo")
    window.navigate_to(tmp_path)

    window.set_state_filter("waiting")

    assert "18/09/2026  Foo" in _visible_labels(window, "Closed")


def test_the_state_filter_deselects_a_task_it_hides(window, tmp_path, make_task):
    _states_fixture(tmp_path, make_task)
    window.navigate_to(tmp_path)
    listing = select_task(window, tmp_path / "260918 - Foo" / "Foo.md")

    window.set_state_filter("open")

    assert listing.currentItem() is None
    assert window.preview_area.isHidden() is True


def test_the_state_filter_menu_offers_every_state_it_can_set(window):
    texts = [action.text() for action in window.state_filter_menu.actions()]

    assert texts == ["All states", "open", "in-progress", "waiting"]


def test_picking_a_state_in_the_menu_filters_by_it(window, tmp_path, make_task):
    _states_fixture(tmp_path, make_task)
    window.navigate_to(tmp_path)

    window.state_filter_menu.actions()[3].trigger()

    assert _visible_labels(window) == [tmp_path.name, "18/09/2026  Foo"]


def test_the_state_filter_sits_in_the_tab_bar_corner(window):
    assert window.tabs.cornerWidget(Qt.Corner.TopRightCorner) is window.state_filter_button


def test_clicking_the_filter_opens_its_menu_and_keeps_the_check_honest(window):
    window.state_filter_button.click()

    assert window.state_filter_menu.isVisible() is True
    assert window.state_filter_button.isChecked() is False
    window.state_filter_menu.close()
