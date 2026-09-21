from pathlib import Path

from geta.workers import build_folder_name, create_folder, standardize_string


def test_standardize_string():
    test_string = "migração óptica"
    standardized_string = standardize_string(test_string)

    assert standardized_string == "MigracaoOptica"

def test_standardize_string_spacing():
    test_string = "pIrâMide_à-VOLTA"
    standardized_string = standardize_string(test_string)

    assert standardized_string == "PiramideAVolta"

def test_build_folder_name():
    name = "CoolFolder"
    prefix = "260921"
    assert build_folder_name(name, prefix) == "260921 - CoolFolder"

def test_create_folder(tmp_path):
    folder = (tmp_path / "my_folder")
    folder.mkdir()

    create_folder(folder, "260921 - TargetFolder")
    assert (folder / "260921 - TargetFolder").exists()