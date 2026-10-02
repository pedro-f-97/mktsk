import pytest
from freezegun import freeze_time

from mktsk.standards import (
    build_folder_name,
    is_task_folder,
    standardize_string,
)


def test_standardize_string():
    test_string = "Sigur Rós"
    standardized_string = standardize_string(test_string)

    assert standardized_string == "SigurRos"


@pytest.mark.parametrize("apostrophe", ["'", "\u2019"])
def test_standardize_string_keeps_a_contraction_together(apostrophe):
    standardized_string = standardize_string(f"It{apostrophe}s Alive!")

    # the apostrophe joins the word, it does not make "s" start one
    assert standardized_string == "ItsAlive"


def test_standardize_string_spacing():
    test_string = "bJÖrk_naÏve-fAçAde!!"
    standardized_string = standardize_string(test_string)

    assert standardized_string == "BjorkNaiveFacade"


def test_build_folder_name():
    name = "CoolFolder"
    prefix = "260921"
    assert build_folder_name(name, prefix) == "260921 - CoolFolder"


def test_build_folder_name_default_prefix():
    with freeze_time("2026-09-21"):
        assert build_folder_name("FrozenFolder") == "260921 - FrozenFolder"


def test_is_task_folder():
    assert is_task_folder("260930 - ItsAlive")
    assert is_task_folder("260710 - BuildSearchResults")
    assert is_task_folder("260709 - Everbind")


def test_is_task_folder_numeric_title():
    assert is_task_folder("260930 - 2026")


def test_is_task_folder_invalid_calendar_date():
    assert not is_task_folder("999999 - ItsAlive")
    assert not is_task_folder("261301 - ItsAlive")
    assert not is_task_folder("260230 - ItsAlive")
    assert not is_task_folder("268231 - ItsAlive")


def test_is_task_folder_bad_date_prefix_length():
    assert not is_task_folder("26093 - ItsAlive")
    assert not is_task_folder("2609301 - ItsAlive")
    assert not is_task_folder("abcdef - ItsAlive")


def test_is_task_folder_missing_separator_or_title():
    assert not is_task_folder("260930ItsAlive")
    assert not is_task_folder("260930 - ")
    assert not is_task_folder("260930- ItsAlive")
    assert not is_task_folder("ItsAlive")
    assert not is_task_folder("")


@pytest.mark.parametrize(
    "name", ["261001 - CON", "261001 - Nul", "261001 - com1", "261001 - PRN"]
)
def test_is_task_folder_reserved_title(name):
    # the date prefix keeps the folder name itself out of the reserved set, but
    # the .md inside would be CON.md, which is as reserved as CON
    assert not is_task_folder(name)


@pytest.mark.parametrize(
    "name", ["261001 - CONtact", "261001 - Com", "261001 - Nulled", "261001 - CON1"]
)
def test_is_task_folder_title_merely_looks_reserved(name):
    # only the whole title is reserved, not a prefix or a stem of one
    assert is_task_folder(name)


def test_is_task_folder_title_not_standardized():
    assert not is_task_folder("260930 - Blá")
    assert not is_task_folder("260930 - Its Alive")
    assert not is_task_folder("260930 - itsAlive")
    assert not is_task_folder("260930 - Its_Alive")
    assert not is_task_folder("260930 - ItsAlive - Part2")
    assert not is_task_folder("260930 - ItsAlive ")
