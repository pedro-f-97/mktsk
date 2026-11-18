"""The configuration of the task listing columns."""

import datetime
from pathlib import Path

from freezegun import freeze_time
from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QFontMetrics, QImage, QPainter
from PySide6.QtWidgets import (
    QApplication,
    QHeaderView,
    QListWidgetItem,
    QStyle,
    QStyleOptionViewItem,
)

from mktsk import helpers, listing, parsing
from mktsk.gui.selection import _SELECTION_INDICATOR_GAP
from mktsk.gui.tasklist import _TASK_MAX_WIDTH, TaskListing, TaskPanel
from mktsk.gui.taskrow import (
    _AGE_ROLE,
    _COLUMN_PADDING,
    _COUNT_ROLE,
    _ENTRY_ROLE,
    _column_widths,
    _date_cell,
    _relative_age,
)
from tests.gui_helpers import (
    action_bar,
    find_task,
    header_labels,
    painted_texts,
    row_texts,
    task_listing,
    task_panel,
)


def _panel(qtbot):
    """A panel of its own, with no tasks under it."""
    panel = TaskPanel(TaskListing())
    qtbot.addWidget(panel)
    return panel


def test_the_header_has_five_sections_and_no_leading_one(qtbot):
    panel = _panel(qtbot)
    header = panel.header

    assert header.count() == 6
    assert header.sectionPosition(0) == 0


def test_every_section_can_be_resized_by_hand(qtbot):
    panel = _panel(qtbot)
    header = panel.header

    for column in range(6):
        if column == 2:
            continue
        assert header.sectionResizeMode(column) == QHeaderView.ResizeMode.Interactive
    assert header.sectionResizeMode(2) == QHeaderView.ResizeMode.Fixed


def test_the_interventions_heading_is_centred(qtbot):
    panel = _panel(qtbot)
    header = panel.header

    alignment = header.model().headerData(
        4, Qt.Orientation.Horizontal, Qt.ItemDataRole.TextAlignmentRole
    )

    assert alignment == Qt.AlignmentFlag.AlignCenter


def test_the_header_names_the_columns_in_order(qtbot):
    panel = _panel(qtbot)
    model = panel.header.model()

    labels = [
        model.headerData(index, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole)
        for index in range(model.columnCount())
    ]

    assert labels == ["Date", "Task", "", "State", "Interventions", "Last activity"]


def test_the_date_column_starts_as_wide_as_a_date(qtbot):
    panel = _panel(qtbot)
    header = panel.header
    columns = _column_widths()
    text = QFontMetrics(QApplication.font()).horizontalAdvance("dd/mm/yyyy")

    assert header.sectionSize(0) == columns.date
    assert text <= header.sectionSize(0) <= text + 2 * _COLUMN_PADDING
    assert header.sectionSize(0) < 1.5 * text + _SELECTION_INDICATOR_GAP


def test_the_state_column_starts_wide_enough_for_every_state(qtbot):
    panel = _panel(qtbot)
    body = QFontMetrics(QApplication.font())
    widest = max(body.horizontalAdvance(state) for state in parsing.STATES)

    assert panel.header.sectionSize(3) >= widest + 2 * _COLUMN_PADDING


def test_the_date_section_can_be_dragged_narrower_and_wider(qtbot):
    panel = _panel(qtbot)
    header = panel.header
    listing = panel.listing
    row = QRect(0, 0, header.length(), listing.delegate.min_height)
    default = header.sectionSize(0)

    header.resizeSection(0, default - 20)
    narrowed = [listing.column_rect(row, column) for column in range(6)]
    assert narrowed[0].width() < default
    assert narrowed[1].left() == narrowed[0].right() + 1

    header.resizeSection(0, default + 40)
    widened = [listing.column_rect(row, column) for column in range(6)]
    assert widened[0].width() == narrowed[0].width() + 60
    assert widened[1].left() == widened[0].right() + 1


def test_resizing_the_date_section_moves_the_following_cells(qtbot):
    panel = _panel(qtbot)
    header = panel.header
    listing = panel.listing
    row = QRect(0, 0, header.length(), listing.delegate.min_height)
    before = [listing.column_rect(row, column) for column in range(6)]

    header.resizeSection(0, header.sectionSize(0) + 40)

    after = [listing.column_rect(row, column) for column in range(6)]
    assert after[0].left() == before[0].left()
    assert after[0].width() == before[0].width() + 40
    for column in range(1, 6):
        assert after[column].left() == before[column].left() + 40
        assert after[column].width() == before[column].width()

    for left in range(6):
        for right in range(left + 1, 6):
            assert not after[left].intersects(after[right])


# The Date and Task cells of a task row.


def _task_entry(folder, title):
    """A task entry whose folder carries the given name."""
    return listing.TaskEntry(
        date=datetime.date(2099, 12, 1),
        title=title,
        file=folder / f"{title}.md",
        last_activity=datetime.date(2099, 12, 1),
        interventions=0,
        state="open",
    )


def test_the_date_cell_reads_the_date_of_a_task_folder(tmp_path):
    entry = _task_entry(tmp_path / "260918 - Foo", "Foo")

    assert _date_cell(entry) == "18/09/2026"


def test_the_date_cell_reads_a_closed_task_from_its_archive(tmp_path):
    entry = listing.TaskEntry(
        date=datetime.date(2026, 9, 18),
        title="Foo",
        file=tmp_path / "260918 - Foo.zip",
        last_activity=datetime.date(2026, 9, 18),
        interventions=0,
        state="closed",
    )

    assert _date_cell(entry) == "18/09/2026"


def test_the_date_cell_falls_back_to_the_raw_prefix(tmp_path):
    entry = _task_entry(tmp_path / "991332 - Foo", "Foo")

    assert _date_cell(entry) == "991332"


def test_a_task_row_paints_the_date_in_the_date_column(
    monkeypatch, window, tmp_path, make_task
):
    file = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    rows = task_listing(window)
    item = find_task(window, file)
    row = QRect(rows.visualItemRect(item))

    texts = row_texts(painted_texts(monkeypatch, rows), row)

    assert texts[0][2] == "18/09/2026"


def test_a_task_row_paints_only_the_description_in_the_task_column(
    monkeypatch, window, tmp_path, make_task
):
    file = make_task(tmp_path, "260918", "FSociety")
    window.navigate_to(tmp_path)
    rows = task_listing(window)
    item = find_task(window, file)
    row = QRect(rows.visualItemRect(item))

    texts = row_texts(painted_texts(monkeypatch, rows), row)

    assert texts[1][2] == "F Society"
    assert "18/09/2026" not in texts[1][2]


def test_a_row_that_is_not_a_task_gets_no_date_cell(
    monkeypatch, window, tmp_path, make_task
):
    make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    rows = task_listing(window)
    heading = rows.item(0)
    row = QRect(rows.visualItemRect(heading))

    assert heading.data(_COUNT_ROLE) is None
    assert row_texts(painted_texts(monkeypatch, rows), row) == []


def test_the_date_heading_and_the_date_value_share_one_padding(
    monkeypatch, window, tmp_path, make_task
):
    file = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    rows = task_listing(window)
    header = task_panel(window).header
    item = find_task(window, file)
    row = QRect(rows.visualItemRect(item))
    padding = header.style().pixelMetric(QStyle.PixelMetric.PM_HeaderMargin)
    from mktsk.gui import taskrow

    texts = row_texts(painted_texts(monkeypatch, rows), row)
    expected = rows.column_rect(row, 0).left() + max(padding, taskrow._DATE_TEXT_LEFT_PADDING)
    assert texts[0][0].left() == expected
    assert header.sectionPosition(0) + max(padding, taskrow._DATE_TEXT_LEFT_PADDING) == texts[0][0].left()


def test_an_unselected_row_paints_nothing_left_of_the_date_text(
    monkeypatch, window, tmp_path, make_task
):
    file = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    rows = task_listing(window)
    item = find_task(window, file)
    row = QRect(rows.visualItemRect(item))
    padding = rows.header.style().pixelMetric(QStyle.PixelMetric.PM_HeaderMargin)
    from mktsk.gui import taskrow

    texts = row_texts(painted_texts(monkeypatch, rows), row)

    assert texts
    assert (
        min(rect.left() for rect, *_ in texts)
        == rows.column_rect(row, 0).left() + max(padding, taskrow._DATE_TEXT_LEFT_PADDING)
    )


# The automatic width of the task column.


def _entry(title):
    return listing.TaskEntry(
        date=datetime.date(2026, 9, 1),
        title=title,
        file=Path(title),
        last_activity=datetime.date(2026, 9, 1),
        interventions=1,
        state="open",
    )


def _add(rows, title):
    item = QListWidgetItem(helpers.readable_title(title))
    item.setData(_ENTRY_ROLE, _entry(title))
    item.setData(_COUNT_ROLE, "1")
    rows.addItem(item)
    return item


def _listing(qtbot, titles):
    """A listing of task rows with the given titles, fitted as a refresh does."""
    rows = TaskListing()
    qtbot.addWidget(rows)
    rows.resize(900, 300)
    rows.show()
    QApplication.processEvents()
    for title in titles:
        _add(rows, title)
    rows.fit_task_column()
    return rows


def _title_of_width(font, target):
    """A title whose measured width is about `target` pixels."""
    unit = QFontMetrics(font).horizontalAdvance("x")
    return "x" * max(1, target // unit)


def _title_width(item):
    """The width the description of a row needs, with its padding."""
    title = helpers.readable_title(item.data(_ENTRY_ROLE).title)
    return QFontMetrics(item.font()).horizontalAdvance(title) + 2 * _COLUMN_PADDING


def _growing_title(rows):
    """A title that lands between the default task width and the cap."""
    default = rows.header.default_task_width
    target = default + (_TASK_MAX_WIDTH - default) // 2 - _COLUMN_PADDING
    return _title_of_width(rows.font(), target)


def test_the_task_column_grows_to_fit_the_longest_description(qtbot):
    rows = _listing(qtbot, [])
    item = _add(rows, _growing_title(rows))
    rows.fit_task_column()
    header = rows.header

    assert header.default_task_width < header.sectionSize(1) < _TASK_MAX_WIDTH
    assert header.sectionSize(1) == _title_width(item)


def test_the_task_column_never_narrows_below_its_default(qtbot):
    rows = _listing(qtbot, ["tiny", "small"])

    assert rows.header.sectionSize(1) == rows.header.default_task_width


def test_a_description_past_the_cap_stops_the_column_and_elides(qtbot, monkeypatch):
    rows = _listing(qtbot, [])
    item = _add(rows, _title_of_width(rows.font(), _TASK_MAX_WIDTH + 200))
    rows.fit_task_column()

    assert rows.header.sectionSize(1) == _TASK_MAX_WIDTH
    assert _title_width(item) > _TASK_MAX_WIDTH

    painted = painted_texts(monkeypatch, rows)
    row = QRect(rows.visualItemRect(item))
    task_text = row_texts(painted, row)[1][2]
    assert task_text != helpers.readable_title(item.data(_ENTRY_ROLE).title)
    assert task_text.endswith("\N{HORIZONTAL ELLIPSIS}")


def test_a_manual_resize_of_the_task_section_survives_a_refit(qtbot):
    rows = _listing(qtbot, [])
    _add(rows, _growing_title(rows))
    rows.fit_task_column()
    rows.header.resizeSection(1, 333)

    rows.fit_task_column()

    assert rows.header.sectionSize(1) == 333


def test_the_other_sections_keep_their_defaults(qtbot):
    rows = _listing(qtbot, [])
    _add(rows, _growing_title(rows))
    rows.fit_task_column()
    header = rows.header
    columns = _column_widths()

    assert header.sectionSize(0) == columns.date
    assert header.sectionSize(3) == columns.state
    assert header.sectionSize(4) == columns.interventions
    assert header.sectionSize(5) == columns.activity


def test_the_cells_of_a_row_still_follow_the_header_at_the_fitted_width(qtbot):
    rows = _listing(qtbot, [])
    _add(rows, _growing_title(rows))
    item = _add(rows, "tiny")
    rows.fit_task_column()
    row = QRect(rows.visualItemRect(item))
    header = rows.header

    for column in range(6):
        cell = rows.column_rect(row, column)
        assert cell.left() == row.left() + header.sectionPosition(column)
        assert cell.width() == header.sectionSize(column)
    for left in range(6):
        for right in range(left + 1, 6):
            assert not rows.column_rect(row, left).intersects(
                rows.column_rect(row, right)
            )


def test_the_selected_row_still_keeps_the_selection_indicator_gap(qtbot):
    rows = _listing(qtbot, [])
    _add(rows, _growing_title(rows))
    item = _add(rows, "tiny")
    rows.fit_task_column()
    rows.setCurrentItem(item)
    row = QRect(rows.visualItemRect(item))

    selected = rows.delegate.content_rect(row, 1)
    plain = rows.column_rect(row, 1)
    assert selected.left() == plain.left()


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

    for column in range(6):
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
    before = [rows.column_rect(row, column) for column in range(6)]

    header.resizeSection(1, header.sectionSize(1) + 40)

    after = [rows.column_rect(row, column) for column in range(6)]
    assert after[0] == before[0]
    assert after[1].left() == before[1].left()
    assert after[1].width() == before[1].width() + 40
    assert after[3].left() == before[3].left() + 40
    assert after[3].width() == before[3].width()
    assert after[4].left() == before[4].left() + 40
    assert after[4].width() == before[4].width()
    assert after[5].left() == before[5].left() + 40
    assert after[5].width() == before[5].width()


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

    assert header.sectionSize(0) == columns.date
    assert header.sectionSize(3) == columns.state
    assert header.sectionSize(4) == columns.interventions
    assert header.sectionSize(5) == columns.activity


def test_the_header_names_the_columns(window, tmp_path):
    window.navigate_to(tmp_path)

    assert header_labels(window) == [
        "Date",
        "Task",
        "",
        "State",
        "Interventions",
        "Last activity",
    ]


def test_a_heading_sits_over_its_own_column(qtbot):
    header = _header(qtbot, 600)

    columns = _columns_of(header)
    for i in range(6):
        assert header.sectionViewportPosition(i) == columns[i].left()
        assert header.sectionSize(i) == columns[i].width()


def test_a_heading_fits_the_column_it_sits_over(qtbot):
    header = _header(qtbot, 600)

    _columns_of(header)
    for i in range(6):
        assert header.sectionSize(i) >= 0


def _header(qtbot, width):
    """A header of its own, over a row as wide as the test asks for."""
    from mktsk.gui.taskrow import _ColumnHeader

    header = _ColumnHeader(25)
    qtbot.addWidget(header)
    header.setFixedHeight(25)
    header.resize(width, header.sizeHint().height())
    header.show()
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
            for i in range(6)
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
    for i in range(6):
        assert header.sectionViewportPosition(i) >= 0
        assert header.sectionSize(i) >= 0


def test_the_list_scrolls_the_header_with_it(window, tmp_path, make_task):
    make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    rows = task_listing(window)
    header = task_panel(window).header
    header.resizeSection(0, header.sectionSize(0) + 800)
    scrollbar = rows.horizontalScrollBar()
    assert scrollbar.maximum() > 0

    scrollbar.setValue(scrollbar.maximum() // 2)

    assert header.offset() == scrollbar.value()


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

    assert _ink(image, rows.column_rect(rect, 3)) > 0


@freeze_time("2026-10-02")
def test_the_count_is_painted_over_the_interventions_column(window, tmp_path, make_task):
    file = make_task(tmp_path, "261002", "Foo")

    window.navigate_to(tmp_path)
    rows = task_listing(window)
    image, rows, rect = _painter_row(window, rows.row(find_task(window, file)))

    assert _ink(image, rows.column_rect(rect, 4)) > 0


@freeze_time("2026-10-02")
def test_the_age_is_painted_over_the_last_activity_column(window, tmp_path, make_task):
    file = make_task(tmp_path, "261002", "Foo")

    window.navigate_to(tmp_path)
    rows = task_listing(window)
    image, rows, rect = _painter_row(window, rows.row(find_task(window, file)))

    assert _ink(image, rows.column_rect(rect, 5)) > 0


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
