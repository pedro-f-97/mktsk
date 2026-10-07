import pytest

from mktsk.main import main, parse_arguments


def test_main_list_shows_the_state_of_each_task(monkeypatch, tmp_path, capsys, make_task):
    waiting = make_task(tmp_path, "260918", "Foo")
    waiting.write_text(
        '# 18/09/2026\n\n\n[mktsk:2026-09-18T10:02]: # "waiting"\n',
        encoding="utf-8",
    )
    make_task(tmp_path, "260925", "Bar")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["mktsk", "--list"])

    main()

    # the state comes from the .md, in front of what it says about the work
    assert capsys.readouterr().out == (
        f"{tmp_path.name}/\n"
        "  25/09/2026  Bar  (open, 1 intervention, last activity 25/09/2026)\n"
        "  18/09/2026  Foo  (waiting, 1 intervention, last activity 18/09/2026)\n"
    )


def test_main_list_only_shows_the_tasks_in_that_state(
    monkeypatch, tmp_path, capsys, make_task
):
    waiting = make_task(tmp_path, "260918", "Foo")
    waiting.write_text(
        '# 18/09/2026\n\n\n[mktsk:2026-09-18T10:02]: # "waiting"\n',
        encoding="utf-8",
    )
    make_task(tmp_path, "260925", "Bar")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["mktsk", "--list", "--only", "waiting"])

    result = main()

    assert result == 0
    assert capsys.readouterr().out == (
        f"{tmp_path.name}/\n"
        "  18/09/2026  Foo  (waiting, 1 intervention, last activity 18/09/2026)\n"
    )


def test_main_list_only_leaves_out_a_category_without_a_match(
    monkeypatch, tmp_path, capsys, make_task
):
    make_task(tmp_path, "260918", "Foo")
    waiting = make_task(tmp_path / "Veritas", "260925", "Bar")
    waiting.write_text(
        '# 25/09/2026\n\n\n[mktsk:2026-09-25T10:02]: # "waiting"\n',
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["mktsk", "--list", "--only", "waiting"])

    main()

    # a heading over no tasks says nothing, the same as a directory with none
    assert capsys.readouterr().out == (
        "Veritas/\n"
        "  25/09/2026  Bar  (waiting, 1 intervention, last activity 25/09/2026)\n"
    )


def test_main_list_only_accepts_a_state_no_task_can_be_in(
    monkeypatch, tmp_path, capsys
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["mktsk", "--list", "--only", "closed"])

    result = main()

    # closed is a state, so the filter is not what refuses it
    assert result == 0
    assert capsys.readouterr().out == ""


def test_main_list_only_with_an_unknown_state(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["mktsk", "--list", "--only", "nope"])

    result = main()

    assert result == 1
    assert "Error: invalid state: nope" in capsys.readouterr().out


def test_only_without_list_is_refused(monkeypatch):
    monkeypatch.setattr("sys.argv", ["mktsk", "--only", "open"])

    with pytest.raises(SystemExit) as failure:
        parse_arguments()

    assert failure.value.code == 2


def test_parse_arguments_for_only(monkeypatch):
    monkeypatch.setattr("sys.argv", ["mktsk", "--list", "--only", "waiting"])

    args = parse_arguments()

    assert args.list is True
    assert args.only == "waiting"


def test_parse_arguments_for_only_without_a_state(monkeypatch):
    monkeypatch.setattr("sys.argv", ["mktsk", "--list", "--only"])

    with pytest.raises(SystemExit) as failure:
        parse_arguments()

    assert failure.value.code == 2
