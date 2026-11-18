import pytest
from freezegun import freeze_time

from mktsk.main import main, parse_arguments
from mktsk.tasks import close_task


@freeze_time("2026-09-30T09:00")
def test_main_reopens_a_task_that_is_archived(
    monkeypatch, tmp_path, capsys, make_task
):
    with freeze_time("2026-09-18T10:30"):
        file = make_task(tmp_path, "260918", "Foo")
        close_task(file.parent, "Foo")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["mktsk", "Foo"])

    opened = []
    monkeypatch.setattr("mktsk.helpers.open_file", opened.append)

    result = main()

    assert result == 0
    assert capsys.readouterr().out == (
        "Reopened: 260918 - Foo (added # 30/09/2026) (state: in-progress)\n"
    )
    folder = tmp_path / "260918 - Foo"
    assert folder.is_dir()
    assert not (tmp_path / "260918 - Foo.zip").exists()
    assert opened == [folder / "Foo.md"]


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


def test_main_close(monkeypatch, tmp_path, capsys, make_task):
    make_task(tmp_path, "260918", "Foo")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["mktsk", "--close", "Foo"])

    opened = []
    monkeypatch.setattr("mktsk.helpers.open_file", opened.append)

    result = main()

    assert result == 0
    assert (tmp_path / "260918 - Foo.zip").is_file()
    assert not (tmp_path / "260918 - Foo").exists()
    # one line with the name of the archive, and nothing opened
    assert capsys.readouterr().out == "Closed: 260918 - Foo.zip\n"
    assert opened == []


def test_main_close_resolves_the_title_the_way_mktsk_does(
    monkeypatch, tmp_path, capsys, make_task
):
    make_task(tmp_path, "260918", "FSociety")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["mktsk", "--close", "f society"])

    result = main()

    assert result == 0
    assert (tmp_path / "260918 - FSociety.zip").is_file()


def test_main_close_refuses_a_title_that_is_not_there(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["mktsk", "--close", "Missing"])

    result = main()

    assert result == 1
    assert "'Missing' is not a task here" in capsys.readouterr().out
    assert list(tmp_path.iterdir()) == []


def test_main_close_reports_a_task_that_is_already_archived(
    monkeypatch, tmp_path, capsys, make_task
):
    make_task(tmp_path, "260918", "Foo")
    (tmp_path / "260918 - Foo.zip").write_bytes(b"zip")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["mktsk", "--close", "Foo"])

    result = main()

    assert result == 1
    assert "'Foo' is already archived" in capsys.readouterr().out
    assert (tmp_path / "260918 - Foo").is_dir()


def test_parse_arguments_for_close(monkeypatch):
    monkeypatch.setattr("sys.argv", ["mktsk", "--close", "Foo"])

    args = parse_arguments()

    assert args.close == "Foo"
    assert args.title == []


def test_parse_arguments_for_close_with_another_title(monkeypatch):
    monkeypatch.setattr("sys.argv", ["mktsk", "Foo", "--close", "Bar"])

    with pytest.raises(SystemExit) as failure:
        parse_arguments()

    assert failure.value.code == 2


@pytest.mark.parametrize(
    "extra",
    [
        ["--list"],
        ["--rename", "260918 - Foo", "Bar"],
        ["--state", "Foo", "open"],
        ["--new-category", "Veritas"],
    ],
)
def test_parse_arguments_close_goes_with_nothing_else(monkeypatch, extra):
    monkeypatch.setattr("sys.argv", ["mktsk", "--close", "Foo", *extra])

    with pytest.raises(SystemExit) as failure:
        parse_arguments()

    assert failure.value.code == 2


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


@freeze_time("2026-10-02 09:40")
def test_main_state_sets_state_for_existing_task(monkeypatch, tmp_path, capsys, make_task):
    file = make_task(tmp_path, "260918", "Foo")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["mktsk", "--state", "Foo", "in-progress"])

    result = main()

    assert result == 0
    # the heading is followed by two blank lines before the block, so a note
    # typed on the first one never runs into the events
    assert file.read_text(encoding="utf-8") == (
        "# 18/09/2026\n\n\n[mktsk:2026-10-02T09:40]: # \"in-progress\"\n"
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


def test_main_state_refuses_a_task_without_a_file(monkeypatch, tmp_path, capsys):
    # the folder is a task, the .md is not there, and the state cannot be read
    # from a file that does not exist
    (tmp_path / "260918 - Foo").mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["mktsk", "--state", "Foo", "open"])

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
