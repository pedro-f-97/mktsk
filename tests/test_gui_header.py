from freezegun import freeze_time
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from mktsk.gui.tree import _HEADER_BUTTON_MARGIN
from tests.gui_helpers import answer_dialog, directory_header, tree_child_labels


def _set_pane_width(window, width):
    """Sizes the left pane to the width, letting it go below its own minimum."""
    window.directory_tree.setMinimumWidth(0)
    QApplication.processEvents()
    window.splitter.setSizes([width, window.splitter.width() - width])
    QApplication.processEvents()


def test_the_header_label_shows_when_there_is_room(window):
    assert window.directory_tree.headerItem().text(0) == "Directory"


def test_the_header_label_hides_when_it_does_not_fit(window):
    _set_pane_width(window, 100)
    header = directory_header(window)

    assert window.directory_tree.headerItem().text(0) == ""
    for button in (
        window.choose_button,
        window.up_button,
        window.directory_tree.header_button,
    ):
        assert button.isVisible()
        assert button.x() >= 0
        assert button.x() + button.width() <= header.width()


def test_the_header_label_stays_clear_at_the_narrowest_pane(window):
    window.splitter.setSizes([1, window.splitter.width()])
    QApplication.processEvents()
    tree = window.directory_tree
    text = tree.headerItem().text(0)

    assert text == "Directory"
    text_right = tree.header_text_indent() + tree.header_view.fontMetrics().horizontalAdvance(
        text
    )
    leftmost = min(
        window.choose_button,
        window.up_button,
        tree.header_button,
        key=lambda button: button.x(),
    )
    assert text_right <= leftmost.x()


def test_the_header_label_returns_when_the_room_does(window):
    _set_pane_width(window, 100)
    assert window.directory_tree.headerItem().text(0) == ""

    _set_pane_width(window, 300)

    assert window.directory_tree.headerItem().text(0) == "Directory"


def test_the_header_button_is_a_child_of_the_header(window):
    assert window.directory_tree.header_button.parent() is directory_header(window)


def test_the_header_button_sits_at_the_right_end_of_the_header(window):
    header = directory_header(window)
    button = window.directory_tree.header_button

    assert button.x() + button.width() <= header.width()
    assert button.x() >= header.width() - button.width() - 2 * _HEADER_BUTTON_MARGIN


def test_the_header_button_is_centred_in_the_header(window):
    header = directory_header(window)
    button = window.directory_tree.header_button

    assert button.y() == (header.height() - button.height()) // 2


def test_the_header_button_never_overflows_the_header_height(window):
    header = directory_header(window)
    button = window.directory_tree.header_button

    assert button.height() <= header.height()


def test_the_header_button_follows_the_header_when_it_grows(window):
    button = window.directory_tree.header_button
    before = button.x()
    header = directory_header(window)
    header.resize(header.width() + 80, header.height())

    assert button.x() > before


def test_the_header_button_carries_an_icon_and_no_label(window):
    button = window.directory_tree.header_button

    assert button.text() == ""
    assert button.icon().isNull() is False


def test_the_header_button_is_named_for_its_action(window):
    assert window.directory_tree.header_button.toolTip() == "New category"
    assert window.directory_tree.header_button.objectName() == "NewCategoryButton"


def test_the_header_button_does_not_take_the_focus(window):
    assert window.directory_tree.header_button.focusPolicy() == Qt.FocusPolicy.NoFocus


def test_the_header_button_creates_a_category(window, tmp_path, monkeypatch):
    window.navigate_to(tmp_path)
    answer_dialog(monkeypatch, ("Veritas", True))

    window.directory_tree.header_button.click()

    assert (tmp_path / "Veritas").is_dir()
    assert tree_child_labels(window) == ["Veritas"]


def test_the_header_button_leaves_the_new_category_selected(window, tmp_path, monkeypatch):
    window.navigate_to(tmp_path)
    answer_dialog(monkeypatch, ("Veritas", True))

    window.directory_tree.header_button.click()

    category = (tmp_path / "Veritas").resolve()
    assert window.creation_directory() == category
    assert window.target_label.text() == "New tasks in Veritas"


def test_the_header_button_creates_in_the_current_directory(window, tmp_path, monkeypatch):
    (tmp_path / "Veritas").mkdir()
    window.navigate_to(tmp_path / "Veritas")
    answer_dialog(monkeypatch, ("SteelMountain", True))

    window.directory_tree.header_button.click()

    assert (tmp_path / "Veritas" / "SteelMountain").is_dir()
    assert not (tmp_path / "SteelMountain").exists()


def test_the_header_button_creates_the_category_cancelled(window, tmp_path, monkeypatch):
    window.navigate_to(tmp_path)
    answer_dialog(monkeypatch, ("Veritas", False))

    window.directory_tree.header_button.click()

    assert not (tmp_path / "Veritas").exists()


def test_the_header_button_creates_nothing_for_a_blank_name(window, tmp_path, monkeypatch):
    window.navigate_to(tmp_path)
    answer_dialog(monkeypatch, ("   ", True))

    window.directory_tree.header_button.click()

    assert list(tmp_path.iterdir()) == []


def test_the_header_button_reports_a_reserved_name(window, tmp_path, fake_messages, monkeypatch):
    window.navigate_to(tmp_path)
    answer_dialog(monkeypatch, ("con", True))

    window.directory_tree.header_button.click()

    assert fake_messages["critical"] == ["'con' is a reserved name"]
    assert list(tmp_path.iterdir()) == []


def test_the_header_button_reports_a_task_folder_name(window, tmp_path, fake_messages, monkeypatch):
    window.navigate_to(tmp_path)
    answer_dialog(monkeypatch, ("260918 - Foo", True))

    window.directory_tree.header_button.click()

    assert fake_messages["critical"] == ["invalid category name"]
    assert list(tmp_path.iterdir()) == []


def test_the_header_button_strips_the_accents(window, tmp_path, monkeypatch):
    window.navigate_to(tmp_path)
    answer_dialog(monkeypatch, ("Produção", True))

    window.directory_tree.header_button.click()

    assert (tmp_path / "Producao").is_dir()
    assert tree_child_labels(window) == ["Producao"]


def test_the_header_button_takes_the_folder_that_is_already_there(
    window, tmp_path, fake_messages, monkeypatch
):
    (tmp_path / "Veritas").mkdir()
    window.navigate_to(tmp_path)
    answer_dialog(monkeypatch, ("Veritas", True))

    window.directory_tree.header_button.click()

    # an existing category is not an error, it is simply selected
    assert fake_messages["critical"] == []
    assert window.creation_directory() == (tmp_path / "Veritas").resolve()


def test_the_header_button_reports_a_failure_to_create(window, tmp_path, fake_messages, monkeypatch):
    def raise_error(location, name):
        raise OSError("boom")

    monkeypatch.setattr("mktsk.files.create_category", raise_error)
    window.navigate_to(tmp_path)
    answer_dialog(monkeypatch, ("Veritas", True))

    window.directory_tree.header_button.click()

    assert fake_messages["critical"] == ["boom"]
    assert window.creation_directory() == tmp_path.resolve()


@freeze_time("2026-09-30")
def test_a_new_category_can_hold_a_task(window, tmp_path, fake_open, monkeypatch):
    window.navigate_to(tmp_path)
    answer_dialog(monkeypatch, ("Veritas", True))
    window.directory_tree.header_button.click()
    window.title_input.setText("Test Task")

    window.create_task()

    assert (tmp_path / "Veritas" / "260930 - TestTask" / "TestTask.md").is_file()
    assert not (tmp_path / "260930 - TestTask").exists()
    assert fake_open == [tmp_path / "Veritas" / "260930 - TestTask" / "TestTask.md"]


def test_the_category_button_appears_without_any_subdirectory(window, tmp_path):
    window.navigate_to(tmp_path)

    assert window.directory_tree.header_button.isVisible() is True
