import pytest
from freezegun import freeze_time

from mktsk.main import main, parse_arguments


@freeze_time("2026-10-02 09:40")
def test_main_state_sets_state_for_existing_task(monkeypatch, tmp_path, capsys, make_task):
    file = make_task(tmp_path, "260918", "Foo")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["mktsk", "--state", "Foo", "in-progress"])

    result = main()

    assert result == 0
    assert file.read_text(encoding="utf-8") == (
        "# 18/09/2026\n\n[mktsk:2026-10-02T09:40]: # \"in-progress\"\n"
    )
    assert capsys.readouterr().out == "260918 - Foo: in-progress\n"


def test_main_state_refuses_unknown_title(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["mktsk", "--state", "Nope", "open"])

    result = main()

    assert result == 1
    assert "Error" in capsys.readouterr().out
    assert list(tmp_path.iterdir()) == []


def test_main_state_refuses_closed(monkeypatch, tmp_path, capsys, make_task):
    make_task(tmp_path, "260918", "Foo")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["mktsk", "--state", "Foo", "closed"])

    result = main()

    assert result == 1
    assert "Error" in capsys.readouterr().out


def test_parse_arguments_for_state(monkeypatch):
    monkeypatch.setattr("sys.argv", ["mktsk", "--state", "Foo", "waiting"])

    args = parse_arguments()

    assert args.state == ["Foo", "waiting"]
    assert args.title == []


def test_parse_arguments_for_state_without_state(monkeypatch):
    monkeypatch.setattr("sys.argv", ["mktsk", "--state", "Foo"])

    with pytest.raises(SystemExit) as failure:
        parse_arguments()

    assert failure.value.code == 2


def test_parse_arguments_for_state_with_a_title(monkeypatch):
    monkeypatch.setattr("sys.argv", ["mktsk", "--state", "Foo", "open", "Bar"])

    with pytest.raises(SystemExit) as failure:
        parse_arguments()

    assert failure.value.code == 2


def test_parse_arguments_for_state_with_list(monkeypatch):
    monkeypatch.setattr("sys.argv", ["mktsk", "--list", "--state", "Foo", "open"])

    with pytest.raises(SystemExit) as failure:
        parse_arguments()

    assert failure.value.code == 2
