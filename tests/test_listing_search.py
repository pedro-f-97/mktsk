"""search_tasks: the words a title has to hold for a task to match."""

import datetime
import zipfile
from pathlib import Path

from mktsk.listing import ContentHit, TaskEntry, search_task_contents, search_tasks


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


def test_content_match_in_an_open_tasks_md_is_found_and_title_match_alone_would_not_find_it(
    tmp_path,
):
    folder = tmp_path / "260918 - Alpha"
    folder.mkdir()
    md = folder / "Alpha.md"
    md.write_text("# 18/09/2026\n\nSpecial secret words inside\n\n", encoding="utf-8")

    hits = search_task_contents(tmp_path, "secret")

    assert len(hits) == 1
    assert hits[0].title == "Alpha"
    assert hits[0].task_path == md


def test_content_match_inside_a_closed_tasks_zip_is_found_and_nothing_is_extracted_to_disk(
    tmp_path,
):
    folder = tmp_path / "260918 - Alpha"
    folder.mkdir()
    md = folder / "Alpha.md"
    md.write_text("# 18/09/2026\n\nImportant hidden phrase\n\n", encoding="utf-8")
    zip_path = tmp_path / "260918 - Alpha.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.write(md, arcname="260918 - Alpha/Alpha.md")
    # remove folder to simulate closed
    for p in sorted(folder.rglob("*"), reverse=True):
        if p.is_file():
            p.unlink()
        else:
            p.rmdir()
    folder.rmdir()

    hits = search_task_contents(tmp_path, "hidden")

    assert len(hits) == 1
    assert hits[0].task_path == zip_path
    assert not folder.exists()


def test_all_words_in_any_order_case_and_accent_insensitive(tmp_path):
    folder = tmp_path / "260918 - Alpha"
    folder.mkdir()
    md = folder / "Alpha.md"
    md.write_text("# 18/09/2026\n\nBjörk sings nicely\n\n", encoding="utf-8")

    assert len(search_task_contents(tmp_path, "SINGS björk")) == 1
    assert len(search_task_contents(tmp_path, "björk SINGS")) == 1
    assert len(search_task_contents(tmp_path, "Björk")) == 1


def test_excerpt_has_at_most_six_words_on_each_side_preserves_original_and_ellipses_at_cuts(
    tmp_path,
):
    folder = tmp_path / "260918 - Alpha"
    folder.mkdir()
    md = folder / "Alpha.md"
    md.write_text(
        "# 18/09/2026\n\none two three four five six seven TARGET eight nine ten eleven twelve thirteen\n\n",
        encoding="utf-8",
    )

    hits = search_task_contents(tmp_path, "target")

    assert len(hits) == 1
    excerpt = hits[0].excerpt
    # up to 6 words before and after
    assert excerpt.startswith("…")
    # check it contains TARGET in original case
    assert "TARGET" in excerpt


def test_one_hit_per_task_even_with_several_occurrences(tmp_path):
    folder = tmp_path / "260918 - Alpha"
    folder.mkdir()
    md = folder / "Alpha.md"
    md.write_text("# 18/09/2026\n\nfoo foo foo\n\nfoo again\n\n", encoding="utf-8")

    hits = search_task_contents(tmp_path, "foo")

    assert len(hits) == 1


def test_a_corrupt_zip_is_skipped_and_other_results_still_come_back(tmp_path):
    folder = tmp_path / "260918 - Good"
    folder.mkdir()
    md = folder / "Good.md"
    md.write_text("# 18/09/2026\n\nmagic word\n\n", encoding="utf-8")

    bad_zip = tmp_path / "260917 - Bad.zip"
    bad_zip.write_text("not a zip", encoding="utf-8")

    hits = search_task_contents(tmp_path, "magic")

    assert len(hits) == 1
    assert hits[0].title == "Good"


def test_attachments_content_is_not_searched_only_the_tasks_md(tmp_path):
    folder = tmp_path / "260918 - Alpha"
    folder.mkdir()
    md = folder / "Alpha.md"
    md.write_text("# 18/09/2026\n\nreal content\n\n", encoding="utf-8")
    (folder / "note.txt").write_text("secretphrase", encoding="utf-8")

    hits = search_task_contents(tmp_path, "secretphrase")

    assert hits == []


def test_content_hit_carries_same_fields_as_title_search_plus_excerpt(tmp_path):
    folder = tmp_path / "Veritas" / "260918 - Alpha"
    folder.mkdir(parents=True)
    md = folder / "Alpha.md"
    md.write_text("# 18/09/2026\n\nfindme here\n\n", encoding="utf-8")

    hits = search_task_contents(tmp_path, "findme")

    assert len(hits) == 1
    assert isinstance(hits[0], ContentHit)
    assert hits[0].date.strftime("%y%m%d") == "260918"
    assert hits[0].title == "Alpha"
    assert hits[0].category == folder.parent
    assert hits[0].task_path == md
    assert isinstance(hits[0].excerpt, str)


def test_search_tasks_returns_a_closed_entry():
    closed = _entry("FSocietyEverbind", state="closed")

    assert search_tasks([closed], "everbind") == [closed]


def test_search_tasks_matches_the_text_of_the_task_column():
    everbind = _entry("FSocietyEverbind")

    # the column reads "F Society Everbind", so the joined spelling is not a word of it
    assert search_tasks([everbind], "FSociety") == []
    assert search_tasks([everbind], "society") == [everbind]
