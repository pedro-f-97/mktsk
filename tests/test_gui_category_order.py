"""The order of the categories when a column heading is clicked."""

import datetime

from mktsk.gui.tasklist import _ENTRY_ROLE
from tests.gui_helpers import click_heading, fill_task, task_listing


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
        2: ["Alpha", "Zeta", base],
        3: ["Alpha", base, "Zeta"],
        4: [base, "Alpha", "Zeta"],
    }

    for column, order in ascending.items():
        window.navigate_to(tmp_path)
        click_heading(window, column)
        assert _headings(window) == order

        click_heading(window, column)
        assert _headings(window) == list(reversed(order))


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
