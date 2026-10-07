import zipfile
from pathlib import Path

import pytest
from freezegun import freeze_time

from mktsk.helpers import TaskError
from mktsk.tasks import close_task, reopen_task, resume_task


def test_close_and_reopen_gives_back_the_files(tmp_path, make_task):
    with freeze_time("2026-09-18T10:30"):
        file = make_task(tmp_path, "260918", "Foo")
        (file.parent / "notes.txt").write_text("hello", encoding="utf-8")
        (file.parent / "sub").mkdir()
        (file.parent / "sub" / "data.bin").write_bytes(b"\x00\x01\x02")
        close_task(file.parent, "Foo")

    with freeze_time("2026-09-30T09:00"):
        result = reopen_task(tmp_path, "Foo")

    folder = tmp_path / "260918 - Foo"
    assert result.file == folder / "Foo.md"
    assert result.message == (
        "Reopened: 260918 - Foo (added # 30/09/2026) (state: in-progress)"
    )
    assert (folder / "notes.txt").read_text(encoding="utf-8") == "hello"
    assert (folder / "sub" / "data.bin").read_bytes() == b"\x00\x01\x02"
    # the .md comes back exactly as the archive holds it, with the new
    # section in front of the block and the state taken out of closed
    assert result.file.read_text(encoding="utf-8") == (
        "# 18/09/2026\n\n# 30/09/2026\n\n\n"
        '[mktsk:2026-09-18T10:30]: # "closed"\n'
        '[mktsk:2026-09-30T09:00]: # "in-progress"\n'
    )
    # the archive is gone only now, and nothing of the extraction is left
    assert [path.name for path in tmp_path.iterdir()] == ["260918 - Foo"]


def test_reopening_on_the_same_day_takes_the_task_out_of_closed(
    tmp_path, make_task
):
    with freeze_time("2026-09-18T10:30"):
        file = make_task(tmp_path, "260918", "Foo")
        close_task(file.parent, "Foo")
        result = reopen_task(tmp_path, "Foo")

    assert result.message == (
        "Reopened: 260918 - Foo (# 18/09/2026 already there) (state: in-progress)"
    )
    content = (tmp_path / "260918 - Foo" / "Foo.md").read_text(encoding="utf-8")
    assert '"closed"' in content
    assert content.endswith('[mktsk:2026-09-18T10:30]: # "in-progress"\n')


@pytest.mark.parametrize(
    "member",
    [
        "../evil.txt",
        "260918 - Foo/../../evil.txt",
    ],
)
def test_a_member_that_leaves_the_destination_is_refused(tmp_path, member):
    archive = tmp_path / "260918 - Foo.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("260918 - Foo/", "")
        handle.writestr("260918 - Foo/Foo.md", "# 18/09/2026\n\n")
        handle.writestr(member, "evil")

    with pytest.raises(TaskError, match="unsafe archive member"):
        reopen_task(tmp_path, "Foo")

    assert not (tmp_path / "evil.txt").exists()
    assert not (tmp_path.parent / "evil.txt").exists()
    assert [path.name for path in tmp_path.iterdir()] == ["260918 - Foo.zip"]


def test_a_member_with_an_absolute_path_is_refused(tmp_path):
    archive = tmp_path / "260918 - Foo.zip"
    outside = tmp_path / "evil.txt"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("260918 - Foo/Foo.md", "# 18/09/2026\n\n")
        handle.writestr(str(outside), "evil")

    with pytest.raises(TaskError, match="unsafe archive member"):
        reopen_task(tmp_path, "Foo")

    assert not outside.exists()
    assert [path.name for path in tmp_path.iterdir()] == ["260918 - Foo.zip"]


def test_a_corrupt_archive_leaves_the_zip_and_creates_no_folder(tmp_path):
    archive = tmp_path / "260918 - Foo.zip"
    archive.write_bytes(b"not really a zip")

    with pytest.raises(TaskError, match="cannot be read"):
        reopen_task(tmp_path, "Foo")

    assert [path.name for path in tmp_path.iterdir()] == ["260918 - Foo.zip"]


def test_reopening_takes_the_directory_entries_of_the_archive(tmp_path):
    archive = tmp_path / "260918 - Foo.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("260918 - Foo/", "")
        handle.writestr("260918 - Foo/Foo.md", "# 18/09/2026\n\n")

    with freeze_time("2026-09-30T09:00"):
        result = reopen_task(tmp_path, "Foo")

    assert result.message == (
        "Reopened: 260918 - Foo (added # 30/09/2026) (state: in-progress)"
    )
    assert (tmp_path / "260918 - Foo" / "Foo.md").is_file()
    assert [path.name for path in tmp_path.iterdir()] == ["260918 - Foo"]


def test_reopening_refuses_a_corrupt_member(
    tmp_path, make_task, monkeypatch
):
    with freeze_time("2026-09-18T10:30"):
        file = make_task(tmp_path, "260918", "Foo")
        close_task(file.parent, "Foo")

    monkeypatch.setattr(
        zipfile.ZipFile, "testzip", lambda self: "260918 - Foo/Foo.md"
    )

    with pytest.raises(TaskError, match="verification failed"):
        reopen_task(tmp_path, "Foo")

    assert [path.name for path in tmp_path.iterdir()] == ["260918 - Foo.zip"]


def test_reopening_refuses_contents_the_archive_does_not_hold(
    tmp_path, make_task, monkeypatch
):
    with freeze_time("2026-09-18T10:30"):
        file = make_task(tmp_path, "260918", "Foo")
        (file.parent / "notes.txt").write_text("hello", encoding="utf-8")
        close_task(file.parent, "Foo")

    monkeypatch.setattr(
        zipfile.ZipFile, "namelist", lambda self: ["260918 - Foo/Foo.md"]
    )

    with pytest.raises(TaskError, match="unexpected contents"):
        reopen_task(tmp_path, "Foo")

    assert [path.name for path in tmp_path.iterdir()] == ["260918 - Foo.zip"]


def test_reopening_refuses_a_member_of_the_wrong_size(
    tmp_path, make_task, monkeypatch
):
    with freeze_time("2026-09-18T10:30"):
        file = make_task(tmp_path, "260918", "Foo")
        close_task(file.parent, "Foo")

    original_getinfo = zipfile.ZipFile.getinfo

    def wrong_size(self, name):
        info = original_getinfo(self, name)
        info.file_size += 1
        return info

    monkeypatch.setattr(zipfile.ZipFile, "getinfo", wrong_size)

    with pytest.raises(TaskError, match="wrong size"):
        reopen_task(tmp_path, "Foo")

    assert [path.name for path in tmp_path.iterdir()] == ["260918 - Foo.zip"]


def test_a_failure_resuming_removes_the_extracted_folder(
    tmp_path, make_task, monkeypatch
):
    with freeze_time("2026-09-18T10:30"):
        file = make_task(tmp_path, "260918", "Foo")
        close_task(file.parent, "Foo")

    def boom(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr("mktsk.files.append_date_section", boom)

    with pytest.raises(OSError, match="disk full"):
        reopen_task(tmp_path, "Foo")

    assert [path.name for path in tmp_path.iterdir()] == ["260918 - Foo.zip"]


def test_a_failure_deleting_the_archive_keeps_both(
    tmp_path, make_task, monkeypatch
):
    with freeze_time("2026-09-18T10:30"):
        file = make_task(tmp_path, "260918", "Foo")
        close_task(file.parent, "Foo")

    real_unlink = Path.unlink

    def boom(self, *args, **kwargs):
        if self.name == "260918 - Foo.zip":
            raise OSError("file in use")
        return real_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", boom)

    with (
        freeze_time("2026-09-30T09:00"),
        pytest.raises(TaskError, match="could not be removed"),
    ):
        reopen_task(tmp_path, "Foo")

    # the folder is back and dated, and the archive is left beside it
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "260918 - Foo",
        "260918 - Foo.zip",
    ]
    content = (tmp_path / "260918 - Foo" / "Foo.md").read_text(encoding="utf-8")
    assert "# 30/09/2026" in content
    assert content.endswith('[mktsk:2026-09-30T09:00]: # "in-progress"\n')
    assert zipfile.is_zipfile(tmp_path / "260918 - Foo.zip")


def test_a_failure_moving_the_folder_into_place_leaves_the_archive(
    tmp_path, make_task, monkeypatch
):
    with freeze_time("2026-09-18T10:30"):
        file = make_task(tmp_path, "260918", "Foo")
        close_task(file.parent, "Foo")

    real_rename = Path.rename

    def boom(self, target):
        if self.name == ".260918 - Foo.part":
            raise OSError("access denied")
        return real_rename(self, target)

    monkeypatch.setattr(Path, "rename", boom)

    with pytest.raises(OSError, match="access denied"):
        reopen_task(tmp_path, "Foo")

    # the archive stands and the half moved extraction is taken away
    assert [path.name for path in tmp_path.iterdir()] == ["260918 - Foo.zip"]


def test_reopening_refuses_when_the_folder_is_there_too(tmp_path, make_task):
    file = make_task(tmp_path, "260918", "Foo")
    archive = tmp_path / "260918 - Foo.zip"
    archive.write_bytes(b"zip")

    with pytest.raises(TaskError, match="already a task here"):
        reopen_task(tmp_path, "Foo")

    # the folder is the task that stands, and the situation does not fix itself
    assert file.parent.is_dir()
    assert archive.is_file()


def test_reopening_a_task_that_is_not_archived(tmp_path):
    with pytest.raises(TaskError, match="not archived"):
        reopen_task(tmp_path, "Foo")

    assert list(tmp_path.iterdir()) == []


def test_reopening_refuses_a_leftover_extraction_directory(tmp_path):
    archive = tmp_path / "260918 - Foo.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("260918 - Foo/Foo.md", "# 18/09/2026\n\n")

    part = tmp_path / ".260918 - Foo.part"
    part.mkdir()
    (part / "leftover.txt").write_text("old", encoding="utf-8")

    with pytest.raises(TaskError, match="extraction directory"):
        reopen_task(tmp_path, "Foo")

    # a directory a failed run left behind is never touched: only the hand
    # that put it there can take it away
    assert (part / "leftover.txt").read_text(encoding="utf-8") == "old"
    assert archive.is_file()


def test_resume_task_reopens_a_folder_that_stands_only_as_an_archive(
    tmp_path, make_task
):
    with freeze_time("2026-09-18T10:30"):
        file = make_task(tmp_path, "260918", "Foo")
        close_task(file.parent, "Foo")

    with freeze_time("2026-09-30T09:00"):
        result = resume_task(tmp_path / "260918 - Foo", "Foo")

    assert result.message == (
        "Reopened: 260918 - Foo (added # 30/09/2026) (state: in-progress)"
    )
    assert (tmp_path / "260918 - Foo").is_dir()
    assert not (tmp_path / "260918 - Foo.zip").exists()
