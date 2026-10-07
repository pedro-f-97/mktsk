from mktsk.main import main
from mktsk.tasks import close_task


def test_main_refuses_a_task_that_is_archived(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    archive = tmp_path / "260918 - Foo.zip"
    archive.write_bytes(b"zip")
    monkeypatch.setattr("sys.argv", ["mktsk", "Foo"])

    opened = []
    monkeypatch.setattr("mktsk.helpers.open_file", opened.append)

    result = main()

    assert result == 1
    assert "'Foo' is already archived" in capsys.readouterr().out
    assert list(tmp_path.iterdir()) == [archive]
    assert opened == []


def test_main_rename_refuses_an_archived_task(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    archive = tmp_path / "260918 - Foo.zip"
    archive.write_bytes(b"zip")
    monkeypatch.setattr("sys.argv", ["mktsk", "--rename", "260918 - Foo", "Bar"])

    result = main()

    assert result == 1
    assert "'Foo' is already archived" in capsys.readouterr().out
    assert list(tmp_path.iterdir()) == [archive]


def test_main_list_hides_closed_tasks_by_default(
    monkeypatch, tmp_path, capsys, make_task
):
    make_task(tmp_path, "260918", "Foo")
    make_task(tmp_path, "260919", "Bar")
    close_task(tmp_path / "260919 - Bar", "Bar")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["mktsk", "--list"])

    result = main()

    assert result == 0
    assert capsys.readouterr().out == (
        f"{tmp_path.name}/\n"
        "  18/09/2026  Foo  (open, 1 intervention, last activity 18/09/2026)\n"
    )


def test_main_list_only_closed_shows_the_archives(
    monkeypatch, tmp_path, capsys, make_task
):
    make_task(tmp_path, "260918", "Foo")
    make_task(tmp_path, "260919", "Bar")
    close_task(tmp_path / "260919 - Bar", "Bar")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["mktsk", "--list", "--only", "closed"])

    result = main()

    assert result == 0
    assert capsys.readouterr().out == (
        f"{tmp_path.name}/\n"
        "  19/09/2026  Bar  (closed, 1 intervention, last activity 19/09/2026)\n"
    )
