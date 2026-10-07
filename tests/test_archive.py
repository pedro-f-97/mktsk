import shutil
import zipfile

import pytest
from freezegun import freeze_time

from mktsk.helpers import TaskError
from mktsk.listing import find_task_archive
from mktsk.standards import is_task_archive
from mktsk.tasks import close_task


def test_is_task_archive_accepts_a_task_archive():
    assert is_task_archive("260918 - Foo.zip")


@pytest.mark.parametrize(
    "name",
    [
        "260918 - Foo",
        "260918 - Foo.zip.part",
        ".260918 - Foo.zip.part",
        "260918 - Foo.txt",
        "Foo.zip",
        "260918 - foo.zip",
        "260918 - Foo.ZIP",
        "269999 - Foo.zip",
        ".zip",
        "zip",
        "",
    ],
)
def test_is_task_archive_refuses_other_names(name):
    assert not is_task_archive(name)


def test_find_task_archive_finds_ignoring_case(tmp_path):
    archive = tmp_path / "260918 - Foo.zip"
    archive.write_bytes(b"zip")

    assert find_task_archive(tmp_path, "foo") == archive
    assert find_task_archive(tmp_path, "Foo") == archive


def test_find_task_archive_prefers_the_most_recent(tmp_path):
    older = tmp_path / "260918 - Foo.zip"
    older.write_bytes(b"old")
    newer = tmp_path / "260930 - Foo.zip"
    newer.write_bytes(b"new")

    assert find_task_archive(tmp_path, "Foo") == newer


def test_find_task_archive_missing(tmp_path):
    assert find_task_archive(tmp_path, "Foo") is None
    assert find_task_archive(tmp_path / "Nowhere", "Foo") is None


def test_find_task_archive_ignores_other_names(tmp_path):
    folder = tmp_path / "260918 - Foo.zip"
    folder.mkdir()
    plain = tmp_path / "260918 - Foo"
    plain.mkdir()
    stray = tmp_path / "notes.zip"
    stray.write_bytes(b"zip")
    other = tmp_path / "260918 - Bar.zip"
    other.write_bytes(b"zip")

    assert find_task_archive(tmp_path, "Foo") is None


@freeze_time("2026-09-18T10:30")
def test_close_task_archives_the_folder_and_deletes_it(tmp_path, make_task):
    file = make_task(tmp_path, "260918", "Foo")
    folder = tmp_path / "260918 - Foo"
    archive_path = tmp_path / "260918 - Foo.zip"

    result = close_task(folder, "Foo")

    assert result.file == archive_path
    assert result.message == "Closed: 260918 - Foo.zip"
    assert archive_path.is_file()
    assert not folder.exists()

    with zipfile.ZipFile(archive_path) as archive:
        assert archive.namelist() == ["260918 - Foo/Foo.md"]
        assert archive.read("260918 - Foo/Foo.md") == (
            b'# 18/09/2026\n\n\n[mktsk:2026-09-18T10:30]: # "closed"\n'
        )
        assert not file.exists()


@freeze_time("2026-09-18T10:30")
def test_close_task_folder_md_is_not_touched_before_deleting(
    tmp_path, make_task, monkeypatch
):
    file = make_task(tmp_path, "260918", "Foo")
    original = file.read_text(encoding="utf-8")
    seen = {}
    real_rmtree = shutil.rmtree

    def spy(path, *args, **kwargs):
        # the last moment before the folder goes: the .md must be as it was
        seen["content"] = (path / "Foo.md").read_text(encoding="utf-8")
        real_rmtree(path, *args, **kwargs)

    monkeypatch.setattr("mktsk.tasks.shutil.rmtree", spy)

    close_task(tmp_path / "260918 - Foo", "Foo")

    assert seen["content"] == original
    assert "closed" not in original


def test_close_task_keeps_extra_files_and_subfolders(tmp_path, make_task):
    make_task(tmp_path, "260918", "Foo")
    folder = tmp_path / "260918 - Foo"
    (folder / "notes.txt").write_text("hello", encoding="utf-8")
    (folder / "sub").mkdir()
    (folder / "sub" / "data.bin").write_bytes(b"\x00\x01\x02")

    close_task(folder, "Foo")

    with zipfile.ZipFile(tmp_path / "260918 - Foo.zip") as archive:
        assert set(archive.namelist()) == {
            "260918 - Foo/Foo.md",
            "260918 - Foo/notes.txt",
            "260918 - Foo/sub/data.bin",
        }
        assert archive.read("260918 - Foo/notes.txt") == b"hello"
        assert archive.read("260918 - Foo/sub/data.bin") == b"\x00\x01\x02"
        assert all(
            info.compress_type == zipfile.ZIP_DEFLATED for info in archive.infolist()
        )


def test_close_task_refuses_when_the_archive_is_already_there(tmp_path, make_task):
    file = make_task(tmp_path, "260918", "Foo")
    original = file.read_text(encoding="utf-8")
    existing = tmp_path / "260918 - Foo.zip"
    existing.write_bytes(b"old")

    with pytest.raises(TaskError, match="already archived"):
        close_task(tmp_path / "260918 - Foo", "Foo")

    assert existing.read_bytes() == b"old"
    assert file.read_text(encoding="utf-8") == original
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "260918 - Foo",
        "260918 - Foo.zip",
    ]


def test_close_task_refuses_a_folder_without_md(tmp_path):
    folder = tmp_path / "260918 - Foo"
    folder.mkdir()

    with pytest.raises(TaskError, match="no Markdown file"):
        close_task(folder, "Foo")

    assert list(tmp_path.iterdir()) == [folder]


def test_close_task_failure_writing_leaves_the_folder(tmp_path, make_task, monkeypatch):
    file = make_task(tmp_path, "260918", "Foo")
    original = file.read_text(encoding="utf-8")

    def boom(self, name, data, *args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(zipfile.ZipFile, "writestr", boom)

    with pytest.raises(OSError, match="disk full"):
        close_task(tmp_path / "260918 - Foo", "Foo")

    assert file.read_text(encoding="utf-8") == original
    assert list(tmp_path.iterdir()) == [tmp_path / "260918 - Foo"]


def test_close_task_failure_deleting_leaves_both(tmp_path, make_task, monkeypatch):
    file = make_task(tmp_path, "260918", "Foo")
    original = file.read_text(encoding="utf-8")
    archive_path = tmp_path / "260918 - Foo.zip"

    def boom(path, *args, **kwargs):
        raise OSError("file in use")

    monkeypatch.setattr("mktsk.tasks.shutil.rmtree", boom)

    with pytest.raises(TaskError, match=r"archived .* but the folder could not"):
        close_task(tmp_path / "260918 - Foo", "Foo")

    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "260918 - Foo",
        "260918 - Foo.zip",
    ]
    # nothing is lost: the folder still holds the untouched .md and the zip
    # carries the closed one
    assert file.read_text(encoding="utf-8") == original
    with zipfile.ZipFile(archive_path) as archive:
        assert b'"closed"' in archive.read("260918 - Foo/Foo.md")


def test_close_task_fails_verification_when_a_member_is_corrupt(
    tmp_path, make_task, monkeypatch
):
    make_task(tmp_path, "260918", "Foo")

    monkeypatch.setattr(
        zipfile.ZipFile, "testzip", lambda self: "260918 - Foo/Foo.md"
    )

    with pytest.raises(TaskError, match="verification failed"):
        close_task(tmp_path / "260918 - Foo", "Foo")

    assert list(tmp_path.iterdir()) == [tmp_path / "260918 - Foo"]


def test_close_task_fails_verification_on_unexpected_names(
    tmp_path, make_task, monkeypatch
):
    make_task(tmp_path, "260918", "Foo")

    monkeypatch.setattr(zipfile.ZipFile, "namelist", lambda self: ["nope"])

    with pytest.raises(TaskError, match="verification failed"):
        close_task(tmp_path / "260918 - Foo", "Foo")

    assert list(tmp_path.iterdir()) == [tmp_path / "260918 - Foo"]


def test_close_task_fails_verification_on_a_wrong_size(tmp_path, make_task, monkeypatch):
    make_task(tmp_path, "260918", "Foo")
    original_infolist = zipfile.ZipFile.infolist

    def wrong_sizes(self):
        infos = original_infolist(self)
        for info in infos:
            info.file_size += 1
        return infos

    monkeypatch.setattr(zipfile.ZipFile, "infolist", wrong_sizes)

    with pytest.raises(TaskError, match="verification failed"):
        close_task(tmp_path / "260918 - Foo", "Foo")

    assert list(tmp_path.iterdir()) == [tmp_path / "260918 - Foo"]
