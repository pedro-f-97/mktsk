from geta.workers import standardize_string


def test_standardize_string():
    test_string = "migração óptica"
    standardized_string = standardize_string(test_string)

    assert standardized_string == "MigracaoOptica"

def test_standardize_string_spacing():
    test_string = "pIrâMide_à-VOLTA"
    standardized_string = standardize_string(test_string)

    assert standardized_string == "PiramideAVolta"