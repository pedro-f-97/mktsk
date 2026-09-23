from freezegun import freeze_time

from mktsk.main import main


def test_main(monkeypatch, tmp_path):
    folder = tmp_path / "my_folder"
    folder.mkdir()
    monkeypatch.chdir(folder)
    monkeypatch.setattr("builtins.input", lambda _: "Test Main")

    opened_files = []

    def fake_open_file(file):
        opened_files.append(file)

    monkeypatch.setattr("mktsk.helpers.open_file", fake_open_file)

    with freeze_time("2026-09-22"):
        result = main()

    final_folder = folder / "260922 - TestMain"
    final_file = final_folder / "TestMain.md"

    assert result == 0
    assert final_file.is_file()
    assert final_file.read_text(encoding="utf-8") == "# 260922 - TestMain\n"
    assert opened_files == [final_file]

def test_main_empty_title(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("builtins.input", lambda _: "")

    main()

    assert list(tmp_path.iterdir()) == []

def test_main_invalid_title(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("builtins.input", lambda _: "!!!")

    main()

    assert list(tmp_path.iterdir()) == []

def test_main_error(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("builtins.input", lambda _: "Test Main Error")

    def raise_error(*args):
        raise OSError("test error")

    monkeypatch.setattr("mktsk.workers.create_folder", raise_error)

    result = main()

    assert result == 1
    assert "Error: test error" in capsys.readouterr().out