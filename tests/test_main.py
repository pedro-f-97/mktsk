from freezegun import freeze_time

from mktsk.main import main


def test_main(monkeypatch, tmp_path):
    folder = (tmp_path / "my_folder")
    folder.mkdir()
    monkeypatch.chdir(folder)
    monkeypatch.setattr("builtins.input", lambda _: "Test Main")

    with freeze_time("2026-09-22"):
        main()
    
    final_folder = folder / "260922 - TestMain"
    final_file = final_folder / "TestMain.md"

    assert final_folder.is_dir()
    assert final_file.is_file()
    assert final_file.read_text(encoding="utf-8") == "# 260922 - TestMain\n"

def test_main_empty_title(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("builtins.input", lambda _: "")

    main()

    assert list(tmp_path.iterdir()) == []
