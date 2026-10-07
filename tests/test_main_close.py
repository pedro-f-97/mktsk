from mktsk.main import main


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
