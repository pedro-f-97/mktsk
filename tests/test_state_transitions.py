from freezegun import freeze_time

from mktsk.tasks import open_or_create_task, resume_task


@freeze_time("2026-09-30")
def test_a_new_day_records_in_progress_from_open(tmp_path):
    folder = tmp_path / "260918 - Foo"
    folder.mkdir()
    file = folder / "Foo.md"
    file.write_text(
        '# 18/09/2026\n\nnotes\n\n[mktsk:2026-09-18T10:00]: # "open"\n',
        encoding="utf-8",
    )

    result = open_or_create_task(tmp_path, "Foo")

    assert result.message == (
        "Opened: 260918 - Foo (added # 30/09/2026) (state: in-progress)"
    )
    # the new section stands in front of the block, with two blank lines under
    # its heading, and the block stays at the end of the file
    assert file.read_text(encoding="utf-8") == (
        "# 18/09/2026\n\nnotes\n\n# 30/09/2026\n\n\n"
        '[mktsk:2026-09-18T10:00]: # "open"\n'
        '[mktsk:2026-09-30T00:00]: # "in-progress"\n'
    )


@freeze_time("2026-09-30")
def test_a_new_day_records_in_progress_from_waiting(tmp_path):
    folder = tmp_path / "260918 - Foo"
    folder.mkdir()
    file = folder / "Foo.md"
    file.write_text(
        '# 18/09/2026\n\n[mktsk:2026-09-18T10:00]: # "waiting"\n',
        encoding="utf-8",
    )

    result = open_or_create_task(tmp_path, "Foo")

    assert result.message == (
        "Opened: 260918 - Foo (added # 30/09/2026) (state: in-progress)"
    )
    assert file.read_text(encoding="utf-8") == (
        "# 18/09/2026\n\n# 30/09/2026\n\n\n"
        '[mktsk:2026-09-18T10:00]: # "waiting"\n'
        '[mktsk:2026-09-30T00:00]: # "in-progress"\n'
    )


@freeze_time("2026-09-30")
def test_a_new_day_records_in_progress_from_closed(tmp_path):
    folder = tmp_path / "260918 - Foo"
    folder.mkdir()
    file = folder / "Foo.md"
    file.write_text(
        '# 18/09/2026\n\n[mktsk:2026-09-18T10:00]: # "closed"\n',
        encoding="utf-8",
    )

    result = open_or_create_task(tmp_path, "Foo")

    assert result.message == (
        "Opened: 260918 - Foo (added # 30/09/2026) (state: in-progress)"
    )
    assert file.read_text(encoding="utf-8").endswith(
        '[mktsk:2026-09-30T00:00]: # "in-progress"\n'
    )


@freeze_time("2026-09-30")
def test_the_same_day_never_changes_the_state(tmp_path):
    folder = tmp_path / "260918 - Foo"
    folder.mkdir()
    file = folder / "Foo.md"
    content = (
        '# 18/09/2026\n\n# 30/09/2026\n\n[mktsk:2026-09-30T09:00]: # "waiting"\n'
    )
    file.write_text(content, encoding="utf-8")

    result = open_or_create_task(tmp_path, "Foo")

    assert file.read_text(encoding="utf-8") == content
    assert result.message == "Opened: 260918 - Foo (# 30/09/2026 already there)"


@freeze_time("2026-09-30")
def test_a_task_already_in_progress_writes_no_event(tmp_path):
    folder = tmp_path / "260918 - Foo"
    folder.mkdir()
    file = folder / "Foo.md"
    file.write_text(
        '# 18/09/2026\n\n[mktsk:2026-09-18T10:00]: # "in-progress"\n',
        encoding="utf-8",
    )

    result = open_or_create_task(tmp_path, "Foo")

    assert result.message == "Opened: 260918 - Foo (added # 30/09/2026)"
    assert file.read_text(encoding="utf-8") == (
        "# 18/09/2026\n\n# 30/09/2026\n\n\n"
        '[mktsk:2026-09-18T10:00]: # "in-progress"\n'
    )


@freeze_time("2026-09-30")
def test_a_new_day_uses_the_derived_state(tmp_path):
    # no events in the file, so the state comes from its sections: one is
    # still open, and the new day takes it to in-progress
    folder = tmp_path / "260918 - Foo"
    folder.mkdir()
    file = folder / "Foo.md"
    file.write_text("# 18/09/2026\n\nnotes\n", encoding="utf-8")

    result = open_or_create_task(tmp_path, "Foo")

    assert result.message == (
        "Opened: 260918 - Foo (added # 30/09/2026) (state: in-progress)"
    )
    assert file.read_text(encoding="utf-8").endswith(
        '[mktsk:2026-09-30T00:00]: # "in-progress"\n'
    )


@freeze_time("2026-09-30")
def test_a_new_day_leaves_a_derived_in_progress_alone(tmp_path):
    # two sections and no events is already in-progress, so nothing is written
    folder = tmp_path / "260918 - Foo"
    folder.mkdir()
    file = folder / "Foo.md"
    file.write_text("# 18/09/2026\n\n# 19/09/2026\n", encoding="utf-8")

    result = open_or_create_task(tmp_path, "Foo")

    assert result.message == "Opened: 260918 - Foo (added # 30/09/2026)"
    assert "[mktsk:" not in file.read_text(encoding="utf-8")


@freeze_time("2026-09-30")
def test_a_state_that_cannot_be_written_still_creates(tmp_path, monkeypatch):
    # the folder does not exist yet, so the write cannot be broken from the
    # outside the way a resumed task can be: the failure is forced instead
    def fail(_file, _state):
        raise OSError("cannot write")

    monkeypatch.setattr("mktsk.state.set_state", fail)

    result = open_or_create_task(tmp_path, "Its Alive!")

    assert result.message == "Created: 260930 - ItsAlive (state not recorded)"
    assert result.file == tmp_path / "260930 - ItsAlive" / "ItsAlive.md"
    assert result.file.read_text(encoding="utf-8") == "# 30/09/2026\n\n"


@freeze_time("2026-09-30")
def test_a_state_that_cannot_be_written_still_resumes(tmp_path):
    folder = tmp_path / "260918 - Foo"
    folder.mkdir()
    file = folder / "Foo.md"
    file.write_text("# 18/09/2026\n\nnotes\n", encoding="utf-8")
    # a directory where the temporary file of the write goes makes the write
    # fail, and the visit itself is already in the file by then
    (folder / "Foo.md.tmp").mkdir()

    result = resume_task(folder, "Foo")

    assert result.message == (
        "Opened: 260918 - Foo (added # 30/09/2026) (state not recorded)"
    )
    assert result.file == file
    assert file.read_text(encoding="utf-8") == "# 18/09/2026\n\nnotes\n\n# 30/09/2026\n\n"
