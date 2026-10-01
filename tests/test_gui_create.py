from freezegun import freeze_time
from PySide6.QtCore import Qt

from tests.gui_helpers import select_directory, select_tab, tab_labels


def test_open_failure_warns(window, tmp_path, monkeypatch, fake_messages):
    def raise_error(path):
        raise OSError("Could not open: /somewhere")

    monkeypatch.setattr("mktsk.helpers.open_file", raise_error)

    window.open_with_default_app(tmp_path / "a.md")

    # the window shows the error as it is, the helper already words it
    assert fake_messages["warning"] == ["Could not open: /somewhere"]


@freeze_time("2026-09-28")
def test_create_task(qtbot, window, tmp_path, fake_open):
    window.navigate_to(tmp_path)
    qtbot.keyClicks(window.title_input, "Test Task")
    qtbot.keyClick(window.title_input, Qt.Key.Key_Return)

    folder = tmp_path / "260928 - TestTask"
    file = folder / "TestTask.md"
    assert file.is_file()
    assert file.read_text(encoding="utf-8") == "# TestTask\n\n## 28/09/2026\n\n"
    assert fake_open == [file]
    assert window.title_input.text() == ""
    assert "28/09/2026  Test Task" in tab_labels(window, tmp_path.name)


def test_create_task_empty_title(window, tmp_path, fake_messages):
    window.navigate_to(tmp_path)
    window.create_task()

    assert fake_messages["critical"] == ["Invalid task description."]
    assert list(tmp_path.iterdir()) == []


def test_create_task_empty_standardized(window, tmp_path, fake_messages):
    window.navigate_to(tmp_path)
    window.title_input.setText("!!!")

    window.create_task()

    assert fake_messages["critical"] == ["invalid task description"]
    assert list(tmp_path.iterdir()) == []


def test_create_task_reserved_name(window, tmp_path, fake_messages):
    window.navigate_to(tmp_path)
    window.title_input.setText("con")

    window.create_task()

    assert fake_messages["critical"] == ["'Con' is a reserved name"]
    assert list(tmp_path.iterdir()) == []


@freeze_time("2026-09-28")
def test_create_task_resumes_existing_task(window, tmp_path, fake_open):
    existing_folder = tmp_path / "260928 - TestTask"
    existing_folder.mkdir()
    existing_file = existing_folder / "TestTask.md"
    # a heading from another task, so signing completes it at the start
    existing_file.write_text("# existing notes\n", encoding="utf-8")
    window.navigate_to(tmp_path)
    window.title_input.setText("Test Task")

    window.create_task()

    assert existing_file.read_text(encoding="utf-8") == (
        "# TestTask\n\n# existing notes\n\n## 28/09/2026\n\n"
    )
    assert fake_open == [existing_file]


@freeze_time("2026-09-30")
def test_create_task_finds_existing_task_by_title(window, tmp_path, fake_open):
    folder = tmp_path / "260918 - TestTask"
    folder.mkdir()
    file = folder / "TestTask.md"
    file.write_text("# TestTask\n\n## 18/09/2026\n\nnotes\n", encoding="utf-8")
    window.navigate_to(tmp_path)
    window.title_input.setText("Test Task")

    window.create_task()

    assert file.read_text(encoding="utf-8") == (
        "# TestTask\n\n## 18/09/2026\n\nnotes\n\n## 30/09/2026\n\n"
    )
    assert fake_open == [file]
    assert window.title_input.text() == ""
    assert not (tmp_path / "260930 - TestTask").exists()


@freeze_time("2026-09-30")
def test_create_task_creates_when_task_is_in_a_subdirectory(window, tmp_path, fake_open):
    subdirectory = tmp_path / "Veritas"
    subdirectory.mkdir()
    folder = subdirectory / "260918 - TestTask"
    folder.mkdir()
    existing = folder / "TestTask.md"
    existing.write_text("# TestTask\n\n## 18/09/2026\n\n", encoding="utf-8")
    window.navigate_to(tmp_path)
    window.title_input.setText("Test Task")

    window.create_task()

    created = tmp_path / "260930 - TestTask" / "TestTask.md"

    assert created.is_file()
    assert fake_open == [created]
    assert existing.read_text(encoding="utf-8") == "# TestTask\n\n## 18/09/2026\n\n"


@freeze_time("2026-09-30")
def test_create_task_lands_in_the_base_folder_tab(window, tmp_path, fake_open, make_task):
    make_task(tmp_path / "Veritas", "260918", "Other")
    window.navigate_to(tmp_path)
    window.title_input.setText("Test Task")

    window.create_task()

    assert (tmp_path / "260930 - TestTask" / "TestTask.md").is_file()
    assert not (tmp_path / "Veritas" / "260930 - TestTask").exists()
    assert tab_labels(window, tmp_path.name) == ["30/09/2026  Test Task"]


@freeze_time("2026-09-28")
def test_create_task_open_failure_warns(window, tmp_path, monkeypatch, fake_messages):
    def raise_error(path):
        raise OSError("boom")

    monkeypatch.setattr("mktsk.helpers.open_file", raise_error)
    window.navigate_to(tmp_path)
    window.title_input.setText("Test Task")

    window.create_task()

    assert fake_messages["critical"] == []
    assert len(fake_messages["warning"]) == 1
    assert (tmp_path / "260928 - TestTask" / "TestTask.md").is_file()
    assert window.title_input.text() == ""


@freeze_time("2026-09-30")
def test_create_task_lands_in_the_selected_category(window, tmp_path, fake_open):
    category = tmp_path / "Veritas"
    category.mkdir()
    window.navigate_to(tmp_path)
    select_directory(window, category.resolve())
    window.title_input.setText("Test Task")

    window.create_task()

    created = category / "260930 - TestTask" / "TestTask.md"
    assert created.is_file()
    assert fake_open == [created]
    assert not (tmp_path / "260930 - TestTask").exists()
    assert window.title_input.text() == ""
    assert window.current_directory == tmp_path.resolve()


@freeze_time("2026-09-30")
def test_create_task_twice_keeps_the_selected_category(window, tmp_path, fake_open):
    category = tmp_path / "Veritas"
    category.mkdir()
    window.navigate_to(tmp_path)
    select_directory(window, category.resolve())

    window.title_input.setText("Test Task")
    window.create_task()
    window.title_input.setText("Other Task")
    window.create_task()

    assert (category / "260930 - TestTask" / "TestTask.md").is_file()
    assert (category / "260930 - OtherTask" / "OtherTask.md").is_file()
    assert window.creation_directory() == category.resolve()


@freeze_time("2026-09-30")
def test_create_task_looks_the_title_up_inside_the_selected_category(
    window, tmp_path, fake_open
):
    category = tmp_path / "Veritas"
    category.mkdir()
    folder = tmp_path / "260918 - TestTask"
    folder.mkdir()
    outside = folder / "TestTask.md"
    outside.write_text("# TestTask\n\n## 18/09/2026\n\nnotes\n", encoding="utf-8")
    window.navigate_to(tmp_path)
    select_directory(window, category.resolve())
    window.title_input.setText("Test Task")

    window.create_task()

    created = category / "260930 - TestTask" / "TestTask.md"
    assert created.is_file()
    assert fake_open == [created]
    assert outside.read_text(encoding="utf-8") == (
        "# TestTask\n\n## 18/09/2026\n\nnotes\n"
    )


@freeze_time("2026-09-30")
def test_create_task_in_a_category_keeps_the_active_tab(window, tmp_path, fake_open, make_task):
    make_task(tmp_path / "Veritas", "260918", "Other")
    make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    select_tab(window, tmp_path.name)
    select_directory(window, (tmp_path / "Veritas").resolve())
    window.title_input.setText("Test Task")

    window.create_task()

    assert window.tabs.tabText(window.tabs.currentIndex()) == tmp_path.name
    assert tab_labels(window, tmp_path.name) == ["18/09/2026  Foo"]
