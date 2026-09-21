from geta.workers import create_folder, standardize_string
from pathlib import Path


def test_standardize_string():
    test_string = "migração óptica"
    standardized_string = standardize_string(test_string)

    assert standardized_string == "MigracaoOptica"

def test_standardize_string_spacing():
    test_string = "pIrâMide_à-VOLTA"
    standardized_string = standardize_string(test_string)

    assert standardized_string == "PiramideAVolta"

def test_create_folder(tmp_path):
    folder = (tmp_path / "my_folder")
    folder.mkdir()

    create_folder(folder, "TargetFolder", "260921")
    assert (folder / "260921 - TargetFolder").exists()