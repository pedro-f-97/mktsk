from PySide6.QtCore import QSize

from mktsk.gui.icons import _ICON_SIZE
from mktsk.gui.tasklist import _STATE_ROLE
from mktsk.tasks import close_task
from tests.gui_helpers import action_bar, select_tab, tab_titles, task_listing


def _rendered(button):
    """The pixels of the icon a button carries, for comparing two of them."""
    image = button.icon().pixmap(QSize(_ICON_SIZE, _ICON_SIZE)).toImage()
    step = image.width() / image.deviceIndependentSize().width()
    return [
        [
            image.pixelColor(round(x * step), round(y * step)).rgba()
            for x in range(_ICON_SIZE)
        ]
        for y in range(_ICON_SIZE)
    ]


def test_resuming_a_closed_task_reopens_it(window, tmp_path, make_task, fake_open):
    file = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    close_task(file.parent, "Foo")
    window.refresh()

    assert tab_titles(window) == ["All", "Closed"]

    select_tab(window, "Closed")
    bar = action_bar(window, tmp_path / "260918 - Foo.zip", "Closed")

    # the row of an archive offers resume alone: the other four actions all
    # speak to a folder, and only reopening makes the folder stand again
    assert bar.resume_button.isVisible() is True
    assert bar.open_button.isVisible() is False
    assert bar.rename_button.isVisible() is False
    assert bar.state_button.isVisible() is False
    assert bar.close_button.isVisible() is False

    bar.resume_button.click()

    folder = tmp_path / "260918 - Foo"
    assert folder.is_dir()
    assert not (tmp_path / "260918 - Foo.zip").exists()
    # the task is back among the open ones and its .md is opened
    assert tab_titles(window) == ["All", tmp_path.name]
    assert fake_open == [folder / "Foo.md"]
    row = task_listing(window, tmp_path.name).item(0)
    assert row.data(_STATE_ROLE) == "in-progress"


def test_resuming_a_closed_task_reports_a_failure(
    window, tmp_path, make_task, fake_messages, monkeypatch
):
    file = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    close_task(file.parent, "Foo")
    window.refresh()

    def boom(location, title):
        raise OSError("boom")

    monkeypatch.setattr("mktsk.tasks.reopen_task", boom)

    select_tab(window, "Closed")
    bar = action_bar(window, tmp_path / "260918 - Foo.zip", "Closed")
    bar.resume_button.click()

    assert fake_messages["critical"] == ["boom"]
    assert (tmp_path / "260918 - Foo.zip").exists()


def test_the_button_of_a_closed_row_has_the_reopen_tooltip(
    window, tmp_path, make_task
):
    file = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    close_task(file.parent, "Foo")
    window.refresh()

    select_tab(window, "Closed")
    bar = action_bar(window, tmp_path / "260918 - Foo.zip", "Closed")

    assert bar.resume_button.toolTip() == "Reopen this task"


def test_the_button_of_a_normal_row_keeps_the_resume_tooltip(
    window, tmp_path, make_task
):
    file = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)

    bar = action_bar(window, file)

    assert bar.resume_button.toolTip() == "Add a note for today"


def test_set_reopening_false_restores_the_resume_icon_and_tooltip(
    window, tmp_path, make_task
):
    file = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    bar = action_bar(window, file)
    icon = _rendered(bar.resume_button)
    tooltip = bar.resume_button.toolTip()

    bar.set_reopening(True)
    reopened = _rendered(bar.resume_button)

    bar.set_reopening(False)

    assert reopened != icon
    assert bar.resume_button.toolTip() == tooltip
    assert _rendered(bar.resume_button) == icon


def test_clicking_the_button_of_a_closed_row_emits_the_resume_signal(
    window, tmp_path, make_task, fake_open
):
    file = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    close_task(file.parent, "Foo")
    window.refresh()

    select_tab(window, "Closed")
    listing = task_listing(window, "Closed")
    bar = action_bar(window, tmp_path / "260918 - Foo.zip", "Closed")
    entries = []
    listing.resume_requested.connect(entries.append)

    bar.resume_button.click()

    assert [entry.file for entry in entries] == [tmp_path / "260918 - Foo.zip"]
