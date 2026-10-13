"""Ordering the task rows by a column heading."""

import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidgetItem

from mktsk import listing
from mktsk.gui.tasklist import _COUNT_ROLE, _ENTRY_ROLE, TaskListing
from tests.gui_helpers import (
    click_heading,
    select_tab,
    select_task,
    tab_labels,
    task_listing,
    task_panel,
)


def _fill(file, activity, state, count):
    """Rewrites the .md of a task with a state, a count and an activity."""
    days = [activity - datetime.timedelta(days=step) for step in range(count)]
    body = "".join(f"# {day.strftime('%d/%m/%Y')}\n\n" for day in days)
    file.write_text(body + f'[mktsk:2026-09-30T10:00]: # "{state}"\n', encoding="utf-8")


def _three_tasks(tmp_path, make_task):
    """Three tasks whose five columns are each in a different order."""
    _fill(
        make_task(tmp_path, "260901", "Alpha"),
        datetime.date(2026, 9, 20),
        "waiting",
        2,
    )
    _fill(
        make_task(tmp_path, "260903", "Bravo"),
        datetime.date(2026, 9, 10),
        "open",
        1,
    )
    _fill(
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
        2: ["Bravo", "Charlie", "Alpha"],
        3: ["Bravo", "Alpha", "Charlie"],
        4: ["Bravo", "Alpha", "Charlie"],
    }

    for column, order in ascending.items():
        window.navigate_to(tmp_path)
        click_heading(window, column, title)
        assert _order(window, title) == order

        click_heading(window, column, title)
        assert _order(window, title) == list(reversed(order))


def test_ties_keep_the_default_order(window, tmp_path, make_task):
    _fill(
        make_task(tmp_path, "260910", "Alpha"),
        datetime.date(2026, 9, 30),
        "open",
        1,
    )
    _fill(
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
    _fill(make_task(tmp_path, "260901", "Ab"), datetime.date(2026, 9, 1), "open", 1)
    _fill(make_task(tmp_path, "260902", "AZ"), datetime.date(2026, 9, 2), "open", 1)
    window.navigate_to(tmp_path)
    title = tmp_path.name

    click_heading(window, 1, title)

    assert _order(window, title) == ["Ab", "AZ"]


def test_interventions_is_numeric(window, tmp_path, make_task):
    _fill(make_task(tmp_path, "260901", "Nine"), datetime.date(2026, 9, 1), "open", 9)
    _fill(make_task(tmp_path, "260902", "Ten"), datetime.date(2026, 9, 2), "open", 10)
    window.navigate_to(tmp_path)
    title = tmp_path.name

    click_heading(window, 3, title)

    assert _order(window, title) == ["Nine", "Ten"]


def test_normal_folders_keep_their_position(window, tmp_path, make_task):
    _fill(
        make_task(tmp_path, "260901", "Able"),
        datetime.date(2026, 9, 10),
        "open",
        1,
    )
    _fill(
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

    click_heading(window, 2, title)
    assert header.sortIndicatorSection() == 2
    assert header.sortIndicatorOrder() == Qt.SortOrder.AscendingOrder

    click_heading(window, 2, title)
    assert header.sortIndicatorSection() == 2
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
    _fill(make_task(tmp_path, "260901", "Zulu"), datetime.date(2026, 9, 1), "open", 1)
    _fill(make_task(tmp_path, "260902", "Alpha"), datetime.date(2026, 9, 2), "open", 1)
    make_task(tmp_path / "Veritas", "260903", "Charlie")
    make_task(tmp_path / "Veritas", "260904", "Delta")
    window.navigate_to(tmp_path)

    click_heading(window, 0, tmp_path.name)
    click_heading(window, 1, "Veritas")
    window.refresh()

    assert _order(window, tmp_path.name) == ["Zulu", "Alpha"]
    assert _order(window, "Veritas") == ["Charlie", "Delta"]
