"""search_tasks: the words a title has to hold for a task to match."""

import datetime
from pathlib import Path

from mktsk.listing import TaskEntry, search_tasks


def _entry(title, state="open"):
    """A task entry named after a placeholder directory."""
    return TaskEntry(
        datetime.date(2026, 9, 18),
        title,
        Path("tasks") / f"260918 - {title}" / f"{title}.md",
        datetime.date(2026, 9, 18),
        1,
        state,
    )


def test_search_tasks_matches_every_word_in_any_order():
    everbind = _entry("FSocietyEverbind")
    naive = _entry("BjorkNaive")

    assert search_tasks([everbind, naive], "society everbind") == [everbind]
    assert search_tasks([everbind, naive], "everbind society") == [everbind]


def test_search_tasks_ignores_case_and_accents_of_the_query():
    naive = _entry("BjorkNaive")

    assert search_tasks([naive], "BJÖRK NAIVE") == [naive]
    assert search_tasks([naive], "björk") == [naive]


def test_search_tasks_leaves_out_a_title_missing_one_word():
    everbind = _entry("FSocietyEverbind")

    assert search_tasks([everbind], "society missing") == []


def test_search_tasks_without_a_word_matches_nothing():
    everbind = _entry("FSocietyEverbind")

    assert search_tasks([everbind], "") == []
    assert search_tasks([everbind], "   ") == []


def test_search_tasks_without_a_match_returns_an_empty_list():
    naive = _entry("BjorkNaive")

    assert search_tasks([naive], "everbind") == []


def test_search_tasks_keeps_the_order_of_the_entries():
    first = _entry("AlphaOne")
    second = _entry("BetaTwo")

    assert search_tasks([second, first], "o") == [second, first]
    assert search_tasks([first, second], "o") == [first, second]


def test_search_tasks_returns_a_closed_entry():
    closed = _entry("FSocietyEverbind", state="closed")

    assert search_tasks([closed], "everbind") == [closed]


def test_search_tasks_matches_the_text_of_the_task_column():
    everbind = _entry("FSocietyEverbind")

    # the column reads "F Society Everbind", so the joined spelling is not a word of it
    assert search_tasks([everbind], "FSociety") == []
    assert search_tasks([everbind], "society") == [everbind]
