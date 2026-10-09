"""The configuration of the task listing columns."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHeaderView

from mktsk.gui.tasklist import TaskListing, TaskPanel


def _panel(qtbot):
    """A panel of its own, with no tasks under it."""
    panel = TaskPanel(TaskListing())
    qtbot.addWidget(panel)
    return panel


def test_every_section_can_be_resized_by_hand(qtbot):
    panel = _panel(qtbot)
    header = panel.header

    for column in range(4):
        assert header.sectionResizeMode(column) == QHeaderView.ResizeMode.Interactive


def test_the_interventions_heading_is_centred(qtbot):
    panel = _panel(qtbot)
    header = panel.header

    alignment = header.model().headerData(
        2, Qt.Orientation.Horizontal, Qt.ItemDataRole.TextAlignmentRole
    )

    assert alignment == Qt.AlignmentFlag.AlignCenter
