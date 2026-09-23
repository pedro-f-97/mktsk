import pytest
from freezegun import freeze_time

from mktsk.workers import (
    build_folder_name,
    create_folder,
    create_md_file,
    sign_md_file,
    standardize_string,
)


def test_standardize_string():
    test_string = "migração óptica"
    standardized_string = standardize_string(test_string)

    assert standardized_string == "MigracaoOptica"

def test_standardize_string_spacing():
    test_string = "pIrâMide_à-VOLTA!!"
    standardized_string = standardize_string(test_string)

    assert standardized_string == "PiramideAVolta"

def test_build_folder_name():
    name = "CoolFolder"
    prefix = "260921"
    assert build_folder_name(name, prefix) == "260921 - CoolFolder"

def test_build_folder_name_default_prefix():
    with freeze_time("2026-09-21"):
        assert build_folder_name("FrozenFolder") == "260921 - FrozenFolder"

def test_create_folder(tmp_path):
    folder = (tmp_path / "my_folder")
    folder.mkdir()
    created_folder = (folder / "260921 - TargetFolder")

    assert created_folder == create_folder(folder, "260921 - TargetFolder")
    assert created_folder.exists()

def test_create_folder_create_parents(tmp_path):
    target = tmp_path / "a" / "b" / "c"
    create_folder(target, "child")
    assert (target / "child").is_dir()

def test_create_folder_existing(tmp_path):
    (tmp_path / "exists").mkdir()
    create_folder(tmp_path, "exists")
    assert (tmp_path / "exists").is_dir()

def test_create_folder_error(tmp_path):
    folder = (tmp_path / "my_folder")
    folder.mkdir()

    with pytest.raises(ValueError):
        create_folder(folder, "/etc")

def test_create_md_file(tmp_path):
    folder = (tmp_path / "my_folder")
    folder.mkdir()
    name = "EmDiFile"
    created = folder / f"{name}.md"

    assert create_md_file(folder, name) == created
    assert created.exists()

def test_create_md_file_path_error(tmp_path):
    folder = (tmp_path / "my_folder")
    folder.mkdir()
    name = "/etc"

    with pytest.raises(ValueError):
        create_md_file(folder, name)

def test_sign_md_file(tmp_path):
    folder = tmp_path / "260922 - ThisTest"
    folder.mkdir()

    file = folder / "ThisTest.md"
    file.touch()

    sign_md_file(file, "260922 - ThisTest")

    assert file.read_text(encoding="utf-8") == "# 260922 - ThisTest\n"

def test_sign_md_file_existing_ok(tmp_path):
    folder = tmp_path / "260922 - ThisTest"
    folder.mkdir()

    file = folder / "ThisTest.md"
    file.touch()

    file.write_text(f"# {folder.name}\n", encoding="utf-8")

    assert file.read_text(encoding="utf-8") == "# 260922 - ThisTest\n"

    sign_md_file(file, "260922 - ThisTest")

    assert file.read_text(encoding="utf-8") == "# 260922 - ThisTest\n"

def test_sign_md_file_existing_not_ok(tmp_path):
    folder = tmp_path / "260922 - ThisTest"
    folder.mkdir()

    file = folder / "ThisTest.md"
    file.touch()

    file.write_text("# This is some other text\n", encoding="utf-8")

    with pytest.raises(ValueError):
        sign_md_file(file, "260922 - ThisTest")

    assert file.read_text(encoding="utf-8") == "# This is some other text\n"

def test_sign_md_file_existing_space(tmp_path):
    folder = tmp_path / "260922 - ThisTest"
    folder.mkdir()

    file = folder / "ThisTest.md"

    file.write_text(" \n", encoding="utf-8")

    sign_md_file(file, "260922 - ThisTest")

    assert file.read_text(encoding="utf-8") == "# 260922 - ThisTest\n"