import datetime

import pytest

from mktsk.parsing import ParsedTask, StateEvent, is_legacy, parse_task

NEW_FORMAT = """\
# 18/09/2026

Customer request, see attachment.

## Problem

Free text.

# 02/10/2026

Supplier replied.
"""


def test_parse_task_of_an_empty_file():
    assert parse_task("") == ParsedTask(interventions=[], events=[], last_activity=None)


def test_parse_task_reads_the_interventions():
    parsed = parse_task(NEW_FORMAT)

    assert [intervention.date for intervention in parsed.interventions] == [
        datetime.date(2026, 9, 18),
        datetime.date(2026, 10, 2),
    ]
    assert [intervention.line for intervention in parsed.interventions] == [1, 9]


def test_parse_task_keeps_the_text_of_the_heading():
    parsed = parse_task(NEW_FORMAT)

    assert [intervention.heading for intervention in parsed.interventions] == [
        "18/09/2026",
        "02/10/2026",
    ]


def test_parse_task_takes_the_last_activity_from_the_most_recent_date():
    parsed = parse_task("# 02/10/2026\n\n# 18/09/2026\n")

    assert parsed.last_activity == datetime.date(2026, 10, 2)


def test_parse_task_accepts_text_after_the_date():
    parsed = parse_task("# 29/09/2026 - supplier reply\n")

    assert parsed.interventions[0].date == datetime.date(2026, 9, 29)
    assert parsed.interventions[0].heading == "29/09/2026 - supplier reply"


def test_parse_task_refuses_an_impossible_date():
    parsed = parse_task("# 31/02/2026\n\n# 02/10/2026\n")

    assert [intervention.date for intervention in parsed.interventions] == [
        datetime.date(2026, 10, 2)
    ]


def test_parse_task_refuses_a_heading_without_a_date():
    assert parse_task("# Notes\n").interventions == []


def test_parse_task_refuses_a_hashtag():
    assert parse_task("#tag 12/01/2026\n").interventions == []


def test_parse_task_refuses_a_second_level_heading_with_a_date():
    assert parse_task("## 12/01/2026\n").interventions == []


def test_parse_task_takes_a_heading_indented_by_three_spaces():
    parsed = parse_task("   # 12/01/2026\n")

    assert parsed.interventions[0].date == datetime.date(2026, 1, 12)


def test_parse_task_refuses_a_heading_indented_by_four_spaces():
    assert parse_task("    # 12/01/2026\n").interventions == []


def test_parse_task_reads_the_first_valid_date_of_a_heading():
    parsed = parse_task("# 31/02/2026 12/01/2026\n")

    assert parsed.interventions[0].date == datetime.date(2026, 1, 12)


@pytest.mark.parametrize(
    ("heading", "expected"),
    [
        ("# 12/01/2026", datetime.date(2026, 1, 12)),
        ("# 12-01-2026", datetime.date(2026, 1, 12)),
        ("# 12.01.2026", datetime.date(2026, 1, 12)),
        ("# 12/01/26", datetime.date(2026, 1, 12)),
        ("# 2026-01-12", datetime.date(2026, 1, 12)),
    ],
)
def test_parse_task_tolerates_five_date_formats(heading, expected):
    parsed = parse_task(f"{heading}\n")

    assert parsed.interventions[0].date == expected


def test_parse_task_reads_an_iso_date_once():
    parsed = parse_task("# 2026-10-02\n")

    assert len(parsed.interventions) == 1
    assert parsed.interventions[0].date == datetime.date(2026, 10, 2)


def test_parse_task_refuses_a_date_glued_to_another_number():
    assert parse_task("# 119/01/2026\n").interventions == []


def test_parse_task_refuses_a_date_followed_by_another_digit():
    assert parse_task("# 12/01/20261\n").interventions == []


def test_parse_task_reads_a_state_event():
    parsed = parse_task('# 18/09/2026\n\n[mktsk:2026-09-18T10:02]: # "open"\n')

    assert parsed.events == [
        StateEvent(
            timestamp=datetime.datetime(2026, 9, 18, 10, 2),  # noqa: DTZ001
            state="open",
            line=3,
        )
    ]


def test_parse_task_reads_events_wherever_they_are():
    content = (
        '[mktsk:2026-09-18T10:02]: # "open"\n'  # line 1
        "\n"
        "# 18/09/2026\n"  # line 3
        "\n"
        '[mktsk:2026-10-02T09:40]: # "in-progress"\n'  # line 5
        "\n"
        "# 02/10/2026\n"  # line 7
        "\n"
        "Notes.\n"
        "\n"
        '[mktsk:2026-10-02T18:15]: # "waiting"\n'  # line 11
    )

    parsed = parse_task(content)

    assert [(event.state, event.line) for event in parsed.events] == [
        ("open", 1),
        ("in-progress", 5),
        ("waiting", 11),
    ]
    assert [intervention.line for intervention in parsed.interventions] == [3, 7]


def test_parse_task_ignores_a_state_outside_the_states():
    parsed = parse_task('[mktsk:2026-09-18T10:02]: # "done"\n')

    assert parsed.events == []


def test_parse_task_ignores_a_timestamp_that_is_not_one():
    parsed = parse_task('[mktsk:2026-13-01T10:02]: # "open"\n')

    assert parsed.events == []


def test_parse_task_ignores_a_line_that_is_not_a_whole_event():
    parsed = parse_task(
        'before [mktsk:2026-09-18T10:02]: # "open"\n'
        '[mktsk:2026-09-18T10:02]: # "open" after\n'
        "[mktsk:2026-09-18T10:02] # open\n"
    )

    assert parsed.events == []


def test_parse_task_keeps_the_valid_events_of_a_block():
    parsed = parse_task(
        '[mktsk:2026-09-18T10:02]: # "open"\n'
        '[mktsk:2026-09-18T10:02]: # "paused"\n'
        '\n[mktsk:2026-10-02T09:40]: # "waiting"\n'
    )

    assert [event.state for event in parsed.events] == ["open", "waiting"]


def test_parse_task_ignores_a_date_inside_a_code_block():
    parsed = parse_task(
        "# 18/09/2026\n"
        "\n"
        "```markdown\n"
        "# 12/01/2026\n"
        '\n[mktsk:2026-10-02T09:40]: # "waiting"\n'
        "```\n"
        "\n"
        "# 02/10/2026\n"
    )

    assert [intervention.line for intervention in parsed.interventions] == [1, 9]
    assert parsed.events == []


def test_parse_task_ignores_a_date_inside_a_tilde_code_block():
    parsed = parse_task("~~~\n# 12/01/2026\n~~~\n")

    assert parsed.interventions == []


def test_parse_task_only_closes_a_code_block_with_its_own_character():
    parsed = parse_task("```\n~~~\n# 12/01/2026\n```\n# 02/10/2026\n")

    assert [intervention.date for intervention in parsed.interventions] == [
        datetime.date(2026, 10, 2)
    ]


def test_parse_task_ignores_everything_after_a_code_block_that_never_closes():
    parsed = parse_task("# 18/09/2026\n\n```\n# 12/01/2026\n")

    assert [intervention.line for intervention in parsed.interventions] == [1]


def test_parse_task_reads_windows_line_breaks():
    parsed = parse_task(
        "# 18/09/2026\r\n"
        "\r\n"
        '[mktsk:2026-09-18T10:02]: # "open"\r\n'
        "\r\n"
        "# 02/10/2026\r\n"
    )

    assert [intervention.line for intervention in parsed.interventions] == [1, 5]
    assert [event.line for event in parsed.events] == [3]
    assert parsed.last_activity == datetime.date(2026, 10, 2)


OLD_FORMAT = """\
# SupplierReply

## 18/09/2026

Customer request, see attachment.

### Problem

Free text.

## 02/10/2026

Supplier replied.
"""


def test_is_legacy_of_an_old_file():
    assert is_legacy(OLD_FORMAT)


def test_is_legacy_of_an_old_file_starting_with_blank_lines():
    assert is_legacy(f"\n\n{OLD_FORMAT}")


def test_is_legacy_of_a_new_file():
    assert not is_legacy(NEW_FORMAT)


def test_is_legacy_of_an_empty_file():
    assert not is_legacy("")


def test_is_legacy_of_a_new_file_with_a_dated_note():
    assert not is_legacy("# 02/10/2026\n\n## Deadline 05/10/2026\n")


def test_is_legacy_needs_a_dated_level_two_heading():
    assert not is_legacy("# SupplierReply\n\n## Notes\n\nFree text.\n")


def test_is_legacy_needs_the_heading_to_be_the_first_one():
    assert not is_legacy("Free text.\n\n# SupplierReply\n\n## 18/09/2026\n")


def test_is_legacy_ignores_a_dated_heading_inside_a_code_block():
    assert not is_legacy("# SupplierReply\n\n```\n## 18/09/2026\n```\n")
