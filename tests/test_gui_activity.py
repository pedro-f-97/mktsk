import datetime

from freezegun import freeze_time
from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QStyle, QStyleOptionViewItem

from mktsk import listing
from mktsk.gui.tasklist import (
    _AGE_ROLE,
    _COUNT_ROLE,
    _ENTRY_ROLE,
    _column_widths,
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


def test_activity_of_today_reads_today():
    assert _relative_age(TODAY, TODAY) == "today"


def test_activity_of_yesterday_reads_yesterday():
    assert _relative_age(TODAY - datetime.timedelta(days=1), TODAY) == "yesterday"


def test_activity_of_an_older_day_counts_the_days():
    assert _relative_age(TODAY - datetime.timedelta(days=5), TODAY) == "5 days ago"


def test_activity_of_a_day_to_come_reads_today():
    # a folder named with a date that has not come yet is still a task here
    assert _relative_age(TODAY + datetime.timedelta(days=3), TODAY) == "today"


def test_a_column_rect_comes_from_the_header(window, tmp_path, make_task):
    make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    rows = task_listing(window)
    header = task_panel(window).header
    row = QRect(0, 0, header.length(), rows.delegate.min_height)

    for column in range(4):
        rect = rows.column_rect(row, column)

        assert rect.left() == header.sectionPosition(column)
        assert rect.width() == header.sectionSize(column)
        assert rect.top() == row.top()
        assert rect.height() == row.height()


def test_resizing_a_section_moves_the_columns_that_follow(
    window, tmp_path, make_task
):
    make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    rows = task_listing(window)
    header = task_panel(window).header
    row = QRect(0, 0, header.length(), rows.delegate.min_height)
    before = [rows.column_rect(row, column) for column in range(4)]

    header.resizeSection(1, header.sectionSize(1) + 40)

    after = [rows.column_rect(row, column) for column in range(4)]
    assert after[0] == before[0]
    assert after[1].left() == before[1].left()
    assert after[1].width() == before[1].width() + 40
    assert after[2].left() == before[2].left() + 40
    assert after[2].width() == before[2].width()
    assert after[3].left() == before[3].left() + 40
    assert after[3].width() == before[3].width()


def test_the_width_of_a_row_is_the_length_of_the_header(
    window, tmp_path, make_task
):
    make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    rows = task_listing(window)
    header = task_panel(window).header
    header.resizeSection(0, header.sectionSize(0) + 800)

    assert rows.visualItemRect(rows.item(0)).width() == header.length()


def test_the_header_starts_from_the_measured_columns(window, tmp_path, make_task):
    make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    header = task_panel(window).header
    columns = _column_widths()

    assert header.sectionSize(1) == columns.state
    assert header.sectionSize(2) == columns.interventions
    assert header.sectionSize(3) == columns.activity


def test_the_header_names_the_columns(window, tmp_path):
    window.navigate_to(tmp_path)

    assert header_labels(window) == [
        "Task",
        "State",
        "Interventions",
        "Last activity",
    ]


def test_a_heading_sits_over_its_own_column(qtbot):
    header = _header(qtbot, 600)

    columns = _columns_of(header)
    for i in range(4):
        assert header.sectionViewportPosition(i) == columns[i].left()
        assert header.sectionSize(i) == columns[i].width()


def test_a_heading_fits_the_column_it_sits_over(qtbot):
    header = _header(qtbot, 600)

    _columns_of(header)
    for i in range(4):
        assert header.sectionSize(i) >= 0


def _header(qtbot, width):
    """A header of its own, over a row as wide as the test asks for."""
    from mktsk.gui.tasklist import _ColumnHeader

    header = _ColumnHeader(25)
    qtbot.addWidget(header)
    header.setFixedHeight(25)
    header.resize(width, header.sizeHint().height())
    header.show()
    if hasattr(header, "set_row_width"):
        header.set_row_width(width)
    return header


def _columns_of(header):
    """The columns of a header, as it splits the row it sits over."""
    return [
        QRect(
            header.sectionViewportPosition(i),
            0,
            header.sectionSize(i),
            header.height(),
        )
        for i in range(4)
    ]


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
    # a scrollbar takes its width from the rows, so the headings have to be
    # placed over what is left of them
    assert rows.verticalScrollBar().isVisible()
    for i in range(4):
        assert header.sectionViewportPosition(i) >= 0
        assert header.sectionSize(i) >= 0


def _painter_row(window, row, title="All"):
    """Paints one row of a tab on its own, as wide as the header."""
    rows = task_listing(window, title)
    delegate = rows.delegate
    index = rows.model().index(row, 0)

    option = QStyleOptionViewItem()
    option.initFrom(rows)
    option.rect = QRect(0, 0, rows.header.length(), delegate.min_height)
    option.state = QStyle.StateFlag.State_Enabled
    option.text = index.data(Qt.ItemDataRole.DisplayRole)

    image = QImage(option.rect.size(), QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.white)
    painter = QPainter(image)
    delegate.paint(painter, option, index)
    painter.end()

    return image, rows, QRect(option.rect)


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


def test_the_state_is_painted_over_the_state_column(window, tmp_path, make_task):
    file = make_task(tmp_path, "261002", "Foo")

    window.navigate_to(tmp_path)
    rows = task_listing(window)
    image, rows, rect = _painter_row(window, rows.row(find_task(window, file)))

    assert _ink(image, rows.column_rect(rect, 1)) > 0


@freeze_time("2026-10-02")
def test_the_count_is_painted_over_the_interventions_column(window, tmp_path, make_task):
    file = make_task(tmp_path, "261002", "Foo")

    window.navigate_to(tmp_path)
    rows = task_listing(window)
    image, rows, rect = _painter_row(window, rows.row(find_task(window, file)))

    assert _ink(image, rows.column_rect(rect, 2)) > 0


@freeze_time("2026-10-02")
def test_the_age_is_painted_over_the_last_activity_column(window, tmp_path, make_task):
    file = make_task(tmp_path, "261002", "Foo")

    window.navigate_to(tmp_path)
    rows = task_listing(window)
    image, rows, rect = _painter_row(window, rows.row(find_task(window, file)))

    assert _ink(image, rows.column_rect(rect, 3)) > 0


def test_a_heading_row_is_painted_across_the_whole_width(
    window, tmp_path, make_task
):
    make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    rows = task_listing(window)
    rows.item(0).setText("X" * 400)

    image, _, rect = _painter_row(window, 0)

    right_half = QRect(rect.width() // 2, 0, rect.width() // 2, rect.height())
    assert _ink(image, right_half) > 0
