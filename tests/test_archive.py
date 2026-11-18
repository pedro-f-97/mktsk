import shutil
import zipfile

import pytest
from freezegun import freeze_time

import mktsk.main as cli
from mktsk import tasks
from mktsk.helpers import TaskError
from mktsk.listing import find_task_archive, read_archived_task
from mktsk.standards import is_task_archive
from mktsk.tasks import TaskInUseError, close_task
from tests.gui_helpers import action_bar


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


# Reading a closed task out of its archive.


def write_archive(path, members):
    """Writes a zip holding the given (name, bytes) members."""
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in members:
            archive.writestr(name, data)
    return path


@pytest.mark.parametrize("md_name", ["Foo.md", "260918 - Foo.md"])
def test_reads_a_nested_archive(tmp_path, md_name):
    archive = write_archive(
        tmp_path / "260918 - Foo.zip",
        [
            (f"260918 - Foo/{md_name}", b"# 18/09/2026\n\nThe body\n"),
            ("260918 - Foo/one.pdf", b"x"),
            ("260918 - Foo/Attachments/two.txt", b"y"),
        ],
    )

    text, attachments = read_archived_task(archive)

    assert text == "# 18/09/2026\n\nThe body\n"
    assert attachments == ["Attachments/", "one.pdf"]


def test_reads_a_flat_archive(tmp_path):
    archive = write_archive(
        tmp_path / "260918 - Foo.zip",
        [
            ("260918 - Foo.md", b"# 18/09/2026\n\nThe body\n"),
            ("one.pdf", b"x"),
            ("Attachments/two.txt", b"y"),
        ],
    )

    text, attachments = read_archived_task(archive)

    assert text == "# 18/09/2026\n\nThe body\n"
    assert attachments == ["Attachments/", "one.pdf"]


@pytest.mark.parametrize("explicit", [False, True])
def test_a_folder_inside_the_task_counts_as_one_attachment(tmp_path, explicit):
    members = [
        ("260918 - Foo/Foo.md", b"text"),
        ("260918 - Foo/Attachments/", b""),
        ("260918 - Foo/Attachments/one.txt", b"x"),
        ("260918 - Foo/Attachments/two.txt", b"y"),
    ]
    if not explicit:
        members.pop(1)
    archive = write_archive(tmp_path / "260918 - Foo.zip", members)

    _, attachments = read_archived_task(archive)

    assert attachments == ["Attachments/"]


def test_ignored_entries_are_not_listed(tmp_path):
    archive = write_archive(
        tmp_path / "260918 - Foo.zip",
        [
            ("260918 - Foo/Foo.md", b"text"),
            ("260918 - Foo/.hidden", b"x"),
            ("260918 - Foo/desktop.ini", b"x"),
            ("260918 - Foo/Thumbs.db", b"x"),
            ("260918 - Foo/~$x.docx", b"x"),
            ("260918 - Foo/kept.txt", b"x"),
        ],
    )

    _, attachments = read_archived_task(archive)

    assert attachments == ["kept.txt"]


def test_a_bom_and_stray_bytes_do_not_raise(tmp_path):
    archive = write_archive(
        tmp_path / "260918 - Foo.zip",
        [("260918 - Foo/Foo.md", b"\xef\xbb\xbf# 18/09/2026\n\nbody \xff\n")],
    )

    text, _ = read_archived_task(archive)

    assert text == "# 18/09/2026\n\nbody \ufffd\n"


def test_a_corrupt_zip_returns_nothing(tmp_path):
    archive = tmp_path / "260918 - Foo.zip"
    archive.write_bytes(b"not a zip")

    assert read_archived_task(archive) == ("", [])


def test_a_zip_without_the_task_md_returns_nothing(tmp_path):
    archive = write_archive(
        tmp_path / "260918 - Foo.zip",
        [("260918 - Foo/one.pdf", b"x")],
    )

    assert read_archived_task(archive) == ("", [])


def test_an_os_error_returns_nothing(tmp_path):
    assert read_archived_task(tmp_path / "260918 - Foo.zip") == ("", [])


def test_a_member_with_only_the_prefix_is_ignored(tmp_path):
    """A member whose relative path is empty (just the prefix) is not listed."""
    archive = write_archive(
        tmp_path / "260918 - Foo.zip",
        [
            ("260918 - Foo/Foo.md", b"text"),
            ("260918 - Foo/", b""),
        ],
    )

    _, attachments = read_archived_task(archive)

    assert attachments == []


def test_decoding_error_in_md_returns_empty_text(tmp_path):
    """If reading the .md member fails, text is empty but other entries are listed."""
    import zipfile
    from unittest.mock import patch

    archive = write_archive(
        tmp_path / "260918 - Foo.zip",
        [
            ("260918 - Foo/Foo.md", b"text"),
            ("260918 - Foo/one.pdf", b"x"),
        ],
    )

    # Patch ZipFile.read to raise for the .md member
    original_read = zipfile.ZipFile.read

    def failing_read(self, name):
        if name.endswith(".md"):
            raise RuntimeError("password protected")
        return original_read(self, name)

    with patch.object(zipfile.ZipFile, "read", failing_read):
        text, attachments = read_archived_task(archive)

    assert text == ""
    assert attachments == ["one.pdf"]


def test_probe_failing_leaves_the_task_untouched(tmp_path, make_task, monkeypatch):
    file = make_task(tmp_path, "260918", "Foo")
    folder = tmp_path / "260918 - Foo"
    archive_path = tmp_path / "260918 - Foo.zip"
    original = file.read_text(encoding="utf-8")

    def fail_rename(*args, **kwargs):
        raise PermissionError("the file is in use")

    monkeypatch.setattr("mktsk.tasks.os.rename", fail_rename)

    with pytest.raises(TaskInUseError, match="in use"):
        close_task(folder, "Foo")

    # nothing is created and nothing is touched
    assert not archive_path.exists()
    assert folder.is_dir()
    assert file.is_file()
    assert file.read_text(encoding="utf-8") == original


def test_folder_removal_failure_keeps_both(tmp_path, make_task, monkeypatch):
    file = make_task(tmp_path, "260918", "Foo")
    folder = tmp_path / "260918 - Foo"
    archive_path = tmp_path / "260918 - Foo.zip"
    original = file.read_text(encoding="utf-8")

    def boom(path, *args, **kwargs):
        raise OSError("file in use")

    monkeypatch.setattr("mktsk.tasks.shutil.rmtree", boom)

    with pytest.raises(TaskError, match=r"archived .* but the folder could not"):
        close_task(folder, "Foo")

    # both are kept and the zip is intact
    assert archive_path.is_file()
    assert folder.is_dir()
    assert file.read_text(encoding="utf-8") == original
    with zipfile.ZipFile(archive_path) as archive:
        assert b'"closed"' in archive.read("260918 - Foo/Foo.md")


def test_close_with_a_file_in_use_shows_a_warning_and_keeps_the_task(
    window, tmp_path, make_task, monkeypatch, fake_messages
):
    file = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)

    def raise_in_use(folder, title):
        raise tasks.TaskInUseError("some of its files are in use")

    monkeypatch.setattr("mktsk.tasks.close_task", raise_in_use)
    action_bar(window, file).close_button.click()

    assert fake_messages["warning"] == [
        (
            "Could not close the task: some of its files are in use. "
            "Close them and try again."
        )
    ]
    assert fake_messages["critical"] == []
    # the task stays open and unchanged
    assert file.parent.is_dir()
    assert not (tmp_path / "260918 - Foo.zip").exists()


def test_cli_close_with_a_task_in_use_exits_one_and_reports_it_on_stderr(
    monkeypatch, tmp_path, make_task, capsys
):
    make_task(tmp_path, "260918", "Foo")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "sys.argv", ["mktsk", "--folder", str(tmp_path), "--close", "Foo"]
    )

    def raise_in_use(folder, title):
        raise tasks.TaskInUseError(
            f"Could not close the task '{title}': some of its files are in use. "
            "Close them and try again."
        )

    monkeypatch.setattr("mktsk.tasks.close_task", raise_in_use)

    result = cli.main()

    assert result == 1
    captured = capsys.readouterr()
    assert "Foo" in captured.err
    assert "in use" in captured.err
    assert captured.out == ""
