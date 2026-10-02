import pytest

from mktsk.migration import Migration, main, migrate_content

OLD_FORMAT = """\
# SupplierReply

## 18/09/2026

Customer request, see attachment.

### Problem

Free text.

## 02/10/2026

Supplier replied.
"""

NEW_FORMAT = """\
# 18/09/2026

Customer request, see attachment.

## Problem

Free text.

# 02/10/2026

Supplier replied.
"""


def test_migrate_content_removes_the_title():
    migration = migrate_content(OLD_FORMAT, "SupplierReply")

    assert migration.content == NEW_FORMAT
    assert migration.review == []


def test_migrate_content_keeps_a_title_naming_another_task():
    migration = migrate_content(OLD_FORMAT, "AnotherTask")

    # the heading stays, because it is content, but the visits under it are
    # still converted
    assert migration.content == (
        "# SupplierReply\n"
        "\n"
        "# 18/09/2026\n"
        "\n"
        "Customer request, see attachment.\n"
        "\n"
        "## Problem\n"
        "\n"
        "Free text.\n"
        "\n"
        "# 02/10/2026\n"
        "\n"
        "Supplier replied.\n"
    )
    assert migration.review == ["line 1: 'SupplierReply' is not the title, left as it is"]


def test_migrate_content_removes_a_title_that_only_differs_in_the_case():
    # a folder renamed by hand keeps the capitals of its own name, so the
    # heading and the folder can differ in the case alone
    migration = migrate_content("# Bigword\n\n## 18/09/2026\n", "BigWord")

    assert migration.content == "# 18/09/2026\n"
    assert migration.review == []


def test_migrate_content_of_a_file_starting_with_blank_lines():
    migration = migrate_content("\n\n# SupplierReply\n\n## 18/09/2026\n", "SupplierReply")

    assert migration.content == "# 18/09/2026\n"
    assert migration.review == []


def test_migrate_content_of_a_file_with_a_title_only():
    migration = migrate_content("# SupplierReply\n\n", "SupplierReply")

    assert migration.content == ""
    assert migration.review == []


def test_migrate_content_of_an_empty_file():
    migration = migrate_content("", "SupplierReply")

    assert migration.content == ""
    assert migration.review == []


def test_migrate_content_keeps_a_level_two_heading_without_a_date():
    migration = migrate_content(
        "# SupplierReply\n\n## 18/09/2026\n\n## Problem\n\nFree text.\n", "SupplierReply"
    )

    assert migration.content == "# 18/09/2026\n\n## Problem\n\nFree text.\n"
    assert migration.review == ["line 5: '## Problem' has no date, left as it is"]


def test_migrate_content_leaves_a_file_in_the_new_format_alone():
    migration = migrate_content(NEW_FORMAT, "SupplierReply")

    assert migration.content == NEW_FORMAT
    assert migration.review == []


def test_migrate_content_leaves_a_dated_level_one_heading_alone():
    content = "# 29/09/2026\n\nFree text.\n"

    assert migrate_content(content, "SupplierReply") == Migration(content, [])


@pytest.mark.parametrize(
    ("heading", "expected"),
    [
        ("### Notes", "## Notes"),
        ("#### Notes", "### Notes"),
        ("##### Notes", "#### Notes"),
        ("###### Notes", "##### Notes"),
        ("  ### Notes", "  ## Notes"),
    ],
)
def test_migrate_content_moves_a_heading_of_a_section_up_one_level(heading, expected):
    migration = migrate_content(f"# SupplierReply\n\n## 18/09/2026\n\n{heading}\n", "SupplierReply")

    assert migration.content == f"# 18/09/2026\n\n{expected}\n"
    assert migration.review == []


def test_migrate_content_leaves_a_level_two_heading_outside_a_section_alone():
    migration = migrate_content("# SupplierReply\n\n## Problem\n\nFree text.\n", "SupplierReply")

    assert migration.content == "## Problem\n\nFree text.\n"
    assert migration.review == []


def test_migrate_content_leaves_a_heading_before_any_section_alone():
    migration = migrate_content(
        "# SupplierReply\n\n### Notes\n\n## 18/09/2026\n", "SupplierReply"
    )

    assert migration.content == "### Notes\n\n# 18/09/2026\n"
    assert migration.review == []


def test_migrate_content_leaves_the_notes_of_a_dated_level_one_heading_alone():
    migration = migrate_content(
        "# 18/09/2026\n\n### Notes\n\n## 02/10/2026\n\n### Notes\n",
        "SupplierReply",
    )

    assert migration.content == (
        "# 18/09/2026\n\n### Notes\n\n# 02/10/2026\n\n## Notes\n"
    )
    assert migration.review == []


def test_migrate_content_leaves_a_code_block_alone():
    migration = migrate_content(
        "# SupplierReply\n"
        "\n"
        "## 18/09/2026\n"
        "\n"
        "```markdown\n"
        "## 12/01/2026\n"
        "### Example\n"
        "```\n",
        "SupplierReply",
    )

    assert migration.content == (
        "# 18/09/2026\n"
        "\n"
        "```markdown\n"
        "## 12/01/2026\n"
        "### Example\n"
        "```\n"
    )
    assert migration.review == []


def test_migrate_content_keeps_the_line_break_of_the_file():
    migration = migrate_content(
        "# SupplierReply\r\n\r\n## 18/09/2026\r\n\r\nFree text.\r\n", "SupplierReply"
    )

    assert migration.content == "# 18/09/2026\r\n\r\nFree text.\r\n"


def test_migrate_content_ends_with_a_single_line_break():
    migration = migrate_content(
        "# SupplierReply\n\n## 18/09/2026\n\nFree text.\n\n\n", "SupplierReply"
    )

    assert migration.content == "# 18/09/2026\n\nFree text.\n"


def test_migrate_content_of_an_already_migrated_file_changes_nothing():
    migration = migrate_content(NEW_FORMAT, "SupplierReply")

    assert migrate_content(migration.content, "SupplierReply") == migration


def write_task(directory, date, title, content=OLD_FORMAT):
    """Writes a task folder with its .md, as mktsk would.

    The title of the task is written into the content as well, so the folder and
    its `.md` name the same task, which is what the migration expects to find.
    """
    folder = directory / f"{date} - {title}"
    folder.mkdir(parents=True)
    file = folder / f"{title}.md"
    file.write_text(content.replace("SupplierReply", title), encoding="utf-8")

    return file


def run_migration(monkeypatch, folder, apply=False):
    """Runs the migration over a folder, as the command line would."""
    argv = ["mktsk.migration", str(folder)]

    if apply:
        argv.append("--apply")

    monkeypatch.setattr("sys.argv", argv)

    return main()


def test_main_simulation_writes_nothing(monkeypatch, tmp_path, capsys):
    file = write_task(tmp_path, "260918", "SupplierReply")

    assert run_migration(monkeypatch, tmp_path) == 0

    assert file.read_text(encoding="utf-8") == OLD_FORMAT

    output = capsys.readouterr().out
    assert "260918 - SupplierReply/SupplierReply.md: migrated" in output
    assert "-## 18/09/2026" in output
    assert "+# 18/09/2026" in output
    assert "-### Problem" in output
    assert "+## Problem" in output


def test_main_simulation_says_a_file_in_the_new_format_is_already_new(
    monkeypatch, tmp_path, capsys
):
    write_task(tmp_path, "260918", "SupplierReply", NEW_FORMAT)

    assert run_migration(monkeypatch, tmp_path) == 0

    output = capsys.readouterr().out
    assert "260918 - SupplierReply/SupplierReply.md: already new" in output
    assert "@@" not in output


def test_main_simulation_reports_what_is_to_review(monkeypatch, tmp_path, capsys):
    write_task(
        tmp_path, "260918", "SupplierReply", "# SupplierReply\n\n## 18/09/2026\n\n## Problem\n"
    )

    assert run_migration(monkeypatch, tmp_path) == 0

    output = capsys.readouterr().out
    assert "260918 - SupplierReply/SupplierReply.md: review" in output
    assert "line 5: '## Problem' has no date, left as it is" in output


def test_main_walks_the_categories_one_level_down(monkeypatch, tmp_path, capsys):
    file = write_task(tmp_path / "Veritas", "260925", "FSociety")

    assert run_migration(monkeypatch, tmp_path, apply=True) == 0

    assert file.read_text(encoding="utf-8") == NEW_FORMAT
    assert "Veritas/260925 - FSociety/FSociety.md: migrated" in capsys.readouterr().out


def test_main_leaves_a_task_two_levels_down_alone(monkeypatch, tmp_path):
    file = write_task(tmp_path / "Veritas" / "SteelMountain", "260925", "FSociety")

    assert run_migration(monkeypatch, tmp_path, apply=True) == 0

    assert file.read_text(encoding="utf-8") == OLD_FORMAT.replace("SupplierReply", "FSociety")


def test_main_apply_writes_the_file(monkeypatch, tmp_path, capsys):
    file = write_task(tmp_path, "260918", "SupplierReply")

    assert run_migration(monkeypatch, tmp_path, apply=True) == 0

    assert file.read_text(encoding="utf-8") == NEW_FORMAT

    # the change is already written, so there is no diff left to show
    assert "@@" not in capsys.readouterr().out


def test_main_apply_leaves_a_file_already_migrated_alone(monkeypatch, tmp_path):
    file = write_task(tmp_path, "260918", "SupplierReply", NEW_FORMAT)

    assert run_migration(monkeypatch, tmp_path, apply=True) == 0

    assert file.read_text(encoding="utf-8") == NEW_FORMAT


def test_main_apply_reminds_of_a_backup(monkeypatch, tmp_path, capsys):
    write_task(tmp_path, "260918", "SupplierReply")

    run_migration(monkeypatch, tmp_path, apply=True)

    assert "Keep a backup" in capsys.readouterr().out


def test_main_keeps_the_line_break_of_the_file(monkeypatch, tmp_path):
    folder = tmp_path / "260918 - SupplierReply"
    folder.mkdir()
    file = folder / "SupplierReply.md"
    file.write_bytes(OLD_FORMAT.replace("\n", "\r\n").encode())

    assert run_migration(monkeypatch, tmp_path, apply=True) == 0

    assert file.read_bytes() == NEW_FORMAT.replace("\n", "\r\n").encode()


def test_main_reports_a_file_it_cannot_read_and_carries_on(monkeypatch, tmp_path, capsys):
    broken = write_task(tmp_path, "260918", "Broken")
    broken.write_bytes(b"\xff\xfe")

    file = write_task(tmp_path, "260918", "SupplierReply")

    assert run_migration(monkeypatch, tmp_path, apply=True) == 1

    output = capsys.readouterr().out
    assert "260918 - Broken/Broken.md: error" in output
    assert "260918 - SupplierReply/SupplierReply.md: migrated" in output
    assert file.read_text(encoding="utf-8") == NEW_FORMAT


def test_main_reports_a_file_it_cannot_write(monkeypatch, tmp_path, capsys):
    file = write_task(tmp_path, "260918", "SupplierReply")

    def refuse_to_replace(source, target):
        raise PermissionError("in use")

    # the failure comes after the temporary file was written, which is the one
    # that has to be cleaned up
    monkeypatch.setattr("mktsk.migration.os.replace", refuse_to_replace)

    assert run_migration(monkeypatch, tmp_path, apply=True) == 1

    assert "260918 - SupplierReply/SupplierReply.md: error" in capsys.readouterr().out
    assert file.read_text(encoding="utf-8") == OLD_FORMAT
    assert list(file.parent.iterdir()) == [file]


def test_main_of_a_folder_that_is_not_there(monkeypatch, tmp_path, capsys):
    assert run_migration(monkeypatch, tmp_path / "missing") == 1

    assert "is not a folder" in capsys.readouterr().out


def test_main_summarises_the_run(monkeypatch, tmp_path, capsys):
    write_task(tmp_path, "260918", "SupplierReply")
    write_task(tmp_path, "260919", "AlreadyNew", NEW_FORMAT)
    write_task(
        tmp_path,
        "260920",
        "ToReview",
        "# ToReview\n\n## 18/09/2026\n\n## Problem\n",
    )

    run_migration(monkeypatch, tmp_path)

    assert (
        "Summary: 1 migrated, 1 already new, 1 to review, 0 failed"
        in capsys.readouterr().out
    )
