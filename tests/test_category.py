import pytest

from mktsk.files import create_category
from mktsk.helpers import TaskError
from mktsk.listing import list_subdirectories


def test_create_category_creates_the_folder(tmp_path):
    category = create_category(tmp_path, "Veritas")

    assert category == tmp_path / "Veritas"
    assert category.is_dir()


def test_create_category_strips_the_accents(tmp_path):
    assert create_category(tmp_path, "Produção") == tmp_path / "Producao"
    assert (tmp_path / "Producao").is_dir()


def test_create_category_keeps_the_case_and_the_spaces(tmp_path):
    assert create_category(tmp_path, "my tasks") == tmp_path / "my tasks"


def test_create_category_returns_the_folder_that_is_already_there(tmp_path):
    existing = tmp_path / "Veritas"
    existing.mkdir()

    assert create_category(tmp_path, "Veritas") == existing


def test_create_category_leaves_the_folder_that_is_already_there_alone(tmp_path):
    existing = tmp_path / "Veritas"
    existing.mkdir()
    (existing / "notes.md").write_text("notes\n", encoding="utf-8")

    create_category(tmp_path, "Veritas")

    assert (existing / "notes.md").read_text(encoding="utf-8") == "notes\n"


def test_create_category_rejects_an_empty_name(tmp_path):
    with pytest.raises(TaskError, match="invalid category name"):
        create_category(tmp_path, "")


def test_create_category_rejects_a_blank_name(tmp_path):
    with pytest.raises(TaskError, match="invalid category name"):
        create_category(tmp_path, "   ")


def test_create_category_rejects_a_name_with_a_separator(tmp_path):
    with pytest.raises(TaskError, match="single path component"):
        create_category(tmp_path, "a/b")


def test_create_category_rejects_a_reserved_name(tmp_path):
    with pytest.raises(TaskError, match="reserved name"):
        create_category(tmp_path, "con")


@pytest.mark.parametrize(
    "name",
    ["foo:bar", "foo?", "foo*", "foo|", "foo.", "foo ", r"C:\foo", "con.txt"],
)
def test_create_category_reports_a_name_windows_would_refuse(tmp_path, name):
    # a domain error, not the raw OSError of whichever machine we are on
    with pytest.raises(TaskError):
        create_category(tmp_path, name)

    assert list(tmp_path.iterdir()) == []


def test_create_category_rejects_a_hidden_name(tmp_path):
    with pytest.raises(TaskError, match="invalid category name"):
        create_category(tmp_path, ".hidden")


def test_create_category_rejects_a_task_folder_name(tmp_path):
    with pytest.raises(TaskError, match="invalid category name"):
        create_category(tmp_path, "260918 - Foo")


def test_create_category_rejects_a_reserved_task_title(tmp_path):
    # is_task_folder refuses the name as a task, and a category must not take
    # the name a task folder would have had, which cannot be opened either
    with pytest.raises(TaskError, match="invalid category name"):
        create_category(tmp_path, "261001 - CON")


def test_create_category_rejects_a_name_it_cannot_make_ascii(tmp_path):
    with pytest.raises(TaskError, match="invalid category name"):
        create_category(tmp_path, "日本語")


def test_create_category_rejects_a_task_folder_name_with_accents(tmp_path):
    # folding the accents is what turns this into a valid task folder name
    with pytest.raises(TaskError, match="invalid category name"):
        create_category(tmp_path, "260918 - FooÇo")


def test_create_category_is_listed_as_a_category(tmp_path):
    create_category(tmp_path, "Veritas")

    assert list_subdirectories(tmp_path) == [tmp_path / "Veritas"]
