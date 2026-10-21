from pathlib import Path

import pytest

from mktsk.helpers import TaskError
from mktsk.tasks import move_task


def test_move_task_moves_the_folder_with_what_it_carries(tmp_path, make_task):
    file = make_task(tmp_path, "260918", "Foo")
    (file.parent / "note.txt").write_text("a note", encoding="utf-8")
    content = file.read_text(encoding="utf-8")
    category = tmp_path / "Veritas"
    category.mkdir()

    moved = move_task(file.parent, category)

    assert moved == category / "260918 - Foo"
    assert moved.is_dir()
    assert (moved / "Foo.md").read_text(encoding="utf-8") == content
    assert (moved / "note.txt").read_text(encoding="utf-8") == "a note"
    assert not (tmp_path / "260918 - Foo").exists()


def test_move_task_in_the_category_it_already_stands_in_does_nothing(
    tmp_path, make_task
):
    file = make_task(tmp_path, "260918", "Foo")

    moved = move_task(file.parent, tmp_path)

    assert moved == file.parent
    assert file.is_file()


def test_move_task_refuses_a_name_the_category_already_holds(tmp_path, make_task):
    file = make_task(tmp_path, "260918", "Foo")
    category = tmp_path / "Veritas"
    category.mkdir()
    taken = category / "260918 - Foo"
    taken.mkdir()

    with pytest.raises(TaskError):
        move_task(file.parent, category)

    # nothing moved: the task stands where it was and the one of the category
    # is left alone
    assert file.is_file()
    assert list(taken.iterdir()) == []


def test_move_task_refuses_a_category_inside_the_task(tmp_path, make_task):
    file = make_task(tmp_path, "260918", "Foo")
    inside = file.parent / "inside"
    inside.mkdir()

    with pytest.raises(TaskError):
        move_task(file.parent, inside)

    assert file.is_file()
    assert inside.is_dir()


def test_move_task_wraps_a_failure_of_the_filesystem(tmp_path, make_task, monkeypatch):
    file = make_task(tmp_path, "260918", "Foo")
    category = tmp_path / "Veritas"
    category.mkdir()

    def fail(self, target):
        raise OSError("the disk said no")

    monkeypatch.setattr(Path, "rename", fail)

    with pytest.raises(TaskError, match="the disk said no"):
        move_task(file.parent, category)

    assert file.is_file()
