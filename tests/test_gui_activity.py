import datetime

from freezegun import freeze_time
from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QStyle, QStyleOptionViewItem

from mktsk import listing
from mktsk.gui.tasklist import (
    _AGE_ROLE,
    _COLUMN_PADDING,
    _COUNT_ROLE,
    _ENTRY_ROLE,
    _column_rects,
    _column_widths,
    _ColumnHeader,
    _Columns,
    _relative_age,
)
from tests.gui_helpers import (
    action_bar,
    find_task,
    header_labels,
    task_listing,
    task_panel,
)

TODAY = datetime.date(2026, 10, 2)

COLUMNS = _Columns(120, 140)

ROW_WIDTH = 400


def test_activity_of_today_reads_today():
    assert _relative_age(TODAY, TODAY) == "today"


def test_activity_of_yesterday_reads_yesterday():
    assert _relative_age(TODAY - datetime.timedelta(days=1), TODAY) == "yesterday"


def test_activity_of_an_older_day_counts_the_days():
    assert _relative_age(TODAY - datetime.timedelta(days=5), TODAY) == "5 days ago"


def test_activity_of_a_day_to_come_reads_today():
    # a folder named with a date that has not come yet is still a task here
    assert _relative_age(TODAY + datetime.timedelta(days=3), TODAY) == "today"


def test_the_columns_run_from_the_task_to_the_last_activity():
    task, interventions, activity = _column_rects(QRect(0, 0, 400, 20), COLUMNS)

    assert task.left() < interventions.left() < activity.left()


def test_the_last_activity_column_ends_with_the_row():
    row = QRect(10, 30, 400, 20)

    assert _column_rects(row, COLUMNS)[2].right() == row.right() - _COLUMN_PADDING


def test_the_task_column_stops_where_the_interventions_begin():
    row = QRect(0, 0, 400, 20)
    task, interventions, activity = _column_rects(row, COLUMNS)

    assert task.right() <= interventions.left()
    assert interventions.right() <= activity.left()


def test_the_columns_follow_the_row_they_belong_to():
    task, interventions, activity = _column_rects(QRect(10, 30, 400, 20), COLUMNS)

    assert (task.top(), interventions.top(), activity.top()) == (30, 30, 30)
    assert (task.height(), interventions.height(), activity.height()) == (20, 20, 20)


def test_a_row_narrower_than_its_columns_keeps_them_inside():
    # the columns are measured from the font, so a window too narrow for them
    # shares what is left between them rather than reaching out of the row
    row = QRect(0, 0, 100, 20)
    _, interventions, activity = _column_rects(row, COLUMNS)

    assert (interventions.width(), activity.width()) == (27, 32)
    assert activity.right() == row.right() - _COLUMN_PADDING


def test_a_row_too_narrow_for_the_task_still_shows_it(qapp):
    # the columns share what is left with the task, so a narrow window never
    # shows the numbers of a task without the task itself
    task, _, _ = _column_rects(QRect(0, 0, 348, 20), _column_widths())

    assert task.width() > 0


def test_the_columns_stay_inside_a_row_of_any_width(qapp):
    columns = _column_widths()

    for width in range(800):
        row = QRect(0, 0, width, 20)
        task, interventions, activity = _column_rects(row, columns)

        for column in (task, interventions, activity):
            assert column.width() >= 0
        assert task.width() + interventions.width() + activity.width() <= max(
            0, width - 2 * _COLUMN_PADDING
        )
        assert activity.right() <= row.right()


def test_a_row_wider_than_its_columns_gives_the_rest_to_the_task():
    task, interventions, activity = _column_rects(QRect(0, 0, 500, 20), COLUMNS)

    assert (interventions.width(), activity.width()) == (120, 140)
    assert task.width() == 500 - 2 * _COLUMN_PADDING - 120 - 140


def test_the_header_names_the_columns(window, tmp_path):
    window.navigate_to(tmp_path)

    assert header_labels(window) == ["Task", "Interventions", "Last activity"]


def test_a_heading_sits_over_its_own_column(qtbot):
    header = _header(qtbot, 600)

    for label, column in zip(header.labels(), _columns_of(header), strict=True):
        assert label.geometry().left() == column.left()


def test_a_heading_fits_the_column_it_sits_over(qtbot):
    header = _header(qtbot, 600)

    for label, column in zip(header.labels(), _columns_of(header), strict=True):
        assert label.sizeHint().width() <= column.width()


def _header(qtbot, width):
    """A header of its own, over a row as wide as the test asks for."""
    header = _ColumnHeader(25)
    qtbot.addWidget(header)
    header.resize(width, 25)
    header.show()
    header.set_row_width(width)
    return header


def _columns_of(header):
    """The columns of a header, as it splits the row it sits over."""
    return _column_rects(
        QRect(0, 0, header.row_width, header.height()), header.columns
    )


def test_the_headings_sit_over_the_columns_when_the_list_scrolls(
    window, tmp_path, make_task, qtbot
):
    for index in range(40):
        make_task(tmp_path, "260918", f"Task{index}")
    window.navigate_to(tmp_path)
    window.resize(420, 200)
    qtbot.wait(1)

    rows = task_listing(window)
    header = task_panel(window).header
    columns = _column_rects(
        QRect(0, 0, rows.viewport().width(), header.height()), rows.delegate.columns
    )

    # a scrollbar takes its width from the rows, so the headings have to be
    # placed over what is left of them
    assert rows.verticalScrollBar().isVisible()
    for label, column in zip(header.labels(), columns, strict=True):
        assert label.geometry().left() == column.left()


def _painter_row(window, row, title="All"):
    """Paints one row of a tab on its own and returns the image of it."""
    rows = task_listing(window, title)
    delegate = rows.delegate

    option = QStyleOptionViewItem()
    option.initFrom(rows)
    option.rect = QRect(0, 0, ROW_WIDTH, delegate.min_height)
    option.state = QStyle.StateFlag.State_Enabled

    image = QImage(option.rect.size(), QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.white)
    painter = QPainter(image)
    delegate.paint(painter, option, rows.model().index(row, 0))
    painter.end()

    return image, _column_rects(option.rect, delegate.columns)


def _ink(image, column):
    """Counts the marks painted in a column of the row."""
    marks = 0
    for x in range(column.left(), column.right() + 1):
        for y in range(image.height()):
            if image.pixelColor(x, y).lightness() < 128:
                marks += 1
    return marks


@freeze_time("2026-10-02")
def test_a_row_carries_the_number_of_interventions_of_the_task(
    window, tmp_path, make_task
):
    file = make_task(tmp_path, "260918", "Foo")
    file.write_text("# 18/09/2026\n\nnotes\n\n# 30/09/2026\n\n", encoding="utf-8")

    window.navigate_to(tmp_path)

    assert find_task(window, file).data(_COUNT_ROLE) == "2"


@freeze_time("2026-10-02")
def test_a_task_without_interventions_carries_none(window, tmp_path, make_task):
    file = make_task(tmp_path, "260918", "Foo")
    file.write_text("notes\n", encoding="utf-8")

    window.navigate_to(tmp_path)

    assert find_task(window, file).data(_COUNT_ROLE) == "0"


@freeze_time("2026-10-02")
def test_a_row_carries_the_age_of_the_last_activity(window, tmp_path, make_task):
    file = make_task(tmp_path, "260918", "Foo")

    window.navigate_to(tmp_path)

    assert find_task(window, file).data(_AGE_ROLE) == "14 days ago"


@freeze_time("2026-10-02")
def test_a_task_worked_on_today_reads_today(window, tmp_path, make_task):
    file = make_task(tmp_path, "261002", "Foo")

    window.navigate_to(tmp_path)

    assert find_task(window, file).data(_AGE_ROLE) == "today"


@freeze_time("2026-10-02")
def test_a_heading_carries_no_activity(window, tmp_path, make_task):
    make_task(tmp_path, "260918", "Foo")

    window.navigate_to(tmp_path)
    heading = task_listing(window).item(0)

    assert heading.data(_COUNT_ROLE) is None
    assert heading.data(_AGE_ROLE) is None


@freeze_time("2026-10-02")
def test_the_tasks_keep_the_order_the_listing_gives(window, tmp_path, make_task):
    older = make_task(tmp_path, "260918", "Foo")
    newer = make_task(tmp_path, "260918", "Bar")
    older.write_text("# 18/09/2026\n\n", encoding="utf-8")
    newer.write_text("# 02/10/2026\n\n", encoding="utf-8")

    window.navigate_to(tmp_path)

    listed = [
        entry.file
        for group in listing.find_task_groups(tmp_path)
        for entry in group.entries
    ]
    rows = task_listing(window)
    shown = [
        rows.item(index).data(_ENTRY_ROLE).file
        for index in range(rows.count())
        if rows.item(index).data(_ENTRY_ROLE) is not None
    ]

    assert shown == listed


@freeze_time("2026-10-02")
def test_resuming_a_task_shows_the_intervention_it_added(
    window, tmp_path, fake_open, make_task
):
    file = make_task(tmp_path, "260918", "Foo")
    file.write_text("# 18/09/2026\n\nnotes\n", encoding="utf-8")
    window.navigate_to(tmp_path)

    action_bar(window, file).resume_button.click()

    assert find_task(window, file).data(_COUNT_ROLE) == "2"
    assert find_task(window, file).data(_AGE_ROLE) == "today"


@freeze_time("2026-10-02")
def test_the_count_is_painted_over_the_interventions_column(window, tmp_path, make_task):
    file = make_task(tmp_path, "261002", "Foo")

    window.navigate_to(tmp_path)
    image, (_, interventions, _) = _painter_row(
        window, task_listing(window).row(find_task(window, file))
    )

    assert _ink(image, interventions) > 0


@freeze_time("2026-10-02")
def test_the_age_is_painted_over_the_last_activity_column(window, tmp_path, make_task):
    file = make_task(tmp_path, "261002", "Foo")

    window.navigate_to(tmp_path)
    image, (_, _, activity) = _painter_row(
        window, task_listing(window).row(find_task(window, file))
    )

    assert _ink(image, activity) > 0
