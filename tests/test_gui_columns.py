"""The configuration of the task listing columns."""

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QApplication, QHeaderView

from mktsk.gui.tasklist import (
    _COLUMN_PADDING,
    _SELECTION_INDICATOR_GAP,
    TaskListing,
    TaskPanel,
    _column_widths,
)


def _panel(qtbot):
    """A panel of its own, with no tasks under it."""
    panel = TaskPanel(TaskListing())
    qtbot.addWidget(panel)
    return panel


def test_the_header_has_five_sections_and_no_leading_one(qtbot):
    panel = _panel(qtbot)
    header = panel.header

    assert header.count() == 5
    assert header.sectionPosition(0) == 0


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


def test_the_date_column_starts_as_wide_as_a_date(qtbot):
    panel = _panel(qtbot)
    header = panel.header
    columns = _column_widths()
    text = QFontMetrics(QApplication.font()).horizontalAdvance("dd/mm/yyyy")

    assert header.sectionSize(0) == columns.date
    assert text <= header.sectionSize(0) <= text + 2 * _COLUMN_PADDING
    assert header.sectionSize(0) < 1.5 * text + _SELECTION_INDICATOR_GAP


def test_the_date_section_can_be_dragged_narrower_and_wider(qtbot):
    panel = _panel(qtbot)
    header = panel.header
    listing = panel.listing
    row = QRect(0, 0, header.length(), listing.delegate.min_height)
    default = header.sectionSize(0)

    header.resizeSection(0, default - 20)
    narrowed = [listing.column_rect(row, column) for column in range(5)]
    assert narrowed[0].width() < default
    assert narrowed[1].left() == narrowed[0].right() + 1

    header.resizeSection(0, default + 40)
    widened = [listing.column_rect(row, column) for column in range(5)]
    assert widened[0].width() == narrowed[0].width() + 60
    assert widened[1].left() == widened[0].right() + 1


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
