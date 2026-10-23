"""Reading a closed task out of its archive."""

import zipfile

import pytest

from mktsk.listing import read_archived_task


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
