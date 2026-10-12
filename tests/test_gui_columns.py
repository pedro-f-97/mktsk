"""The configuration of the task listing columns."""

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtWidgets import QApplication, QHeaderView

from mktsk.gui.tasklist import TaskListing, TaskPanel, _column_widths


def _panel(qtbot):
    """A panel of its own, with no tasks under it."""
    panel = TaskPanel(TaskListing())
    qtbot.addWidget(panel)
    return panel


def test_every_section_can_be_resized_by_hand(qtbot):
    panel = _panel(qtbot)
    header = panel.header

    for column in range(5):
        assert header.sectionResizeMode(column) == QHeaderView.ResizeMode.Interactive


def test_the_interventions_heading_is_centred(qtbot):
    panel = _panel(qtbot)
    header = panel.header

    alignment = header.model().headerData(
        3, Qt.Orientation.Horizontal, Qt.ItemDataRole.TextAlignmentRole
    )

    assert alignment == Qt.AlignmentFlag.AlignCenter


def test_the_header_names_the_columns_in_order(qtbot):
    panel = _panel(qtbot)
    model = panel.header.model()

    labels = [
        model.headerData(index, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole)
        for index in range(model.columnCount())
    ]

    assert labels == ["Date", "Task", "State", "Interventions", "Last activity"]


def test_the_date_column_starts_as_wide_as_a_date_and_the_bar(qtbot):
    panel = _panel(qtbot)
    header = panel.header
    inset = panel.listing.inset
    columns = _column_widths(inset)

    assert header.sectionSize(0) == columns.date

    metrics = QFontMetrics(QFont(QApplication.font()))
    assert header.sectionSize(0) >= inset + metrics.horizontalAdvance("dd/mm/yyyy")


def test_the_date_section_is_held_as_wide_as_the_room_the_bar_needs(qtbot):
    panel = _panel(qtbot)
    header = panel.header
    inset = panel.listing.inset

    header.resizeSection(0, inset - 20)

    assert header.sectionSize(0) == inset


def test_resizing_the_date_section_moves_the_following_cells(qtbot):
    panel = _panel(qtbot)
    header = panel.header
    listing = panel.listing
    row = QRect(0, 0, header.length(), listing.delegate.min_height)
    before = [listing.column_rect(row, column) for column in range(5)]

    header.resizeSection(0, header.sectionSize(0) + 40)

    after = [listing.column_rect(row, column) for column in range(5)]
    assert after[0].left() == before[0].left()
    assert after[0].width() == before[0].width() + 40
    for column in range(1, 5):
        assert after[column].left() == before[column].left() + 40
        assert after[column].width() == before[column].width()

    for left in range(5):
        for right in range(left + 1, 5):
            assert not after[left].intersects(after[right])
