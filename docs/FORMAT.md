## The new .md format

This is the format mktsk writes: `files.append_date_section` writes it and reads it
back with `mktsk/parsing.py`. The old format, a `# <StandardizedTitle>` heading and a
`## <dd/mm/YYYY>` heading per visit, is refused rather than read. The plan the steps
come from is in `PLAN.md`.

```markdown
# 18/09/2026

Customer request, see attachment.

## Problem

Free text, with levels 2 to 6 available.

# 02/10/2026

[mktsk:2026-09-18T10:02]: # "open"
[mktsk:2026-10-02T09:40]: # "in-progress"
```

- No `# <title>`: the folder and the `.md` name say which task it is
- `STATES` is `("open", "in-progress", "waiting", "closed")`
- An intervention is a level 1 heading: a single `#`, a space and up to three spaces of
  indentation, so `#hashtag` and `## 12/01/2026` are not one. Its line holds a date and
  may hold text after it (`# 29/09/2026 - reply`), and the first valid date of the line
  is the one that counts
- `dd/mm/yyyy` is the canonical form and `DATE_FORMAT` is what a writer uses; `dd-mm-yyyy`,
  `dd.mm.yyyy`, `dd/mm/yy` and `yyyy-mm-dd` are only tolerated when reading, and a two
  digit year means 2000 plus the year. A date glued to another number is not a date, which
  is what keeps `2026-10-02` from being read as the `26-10-02` inside it
- A date that never happened is not a date, so `# 31/02/2026` is a heading like any
  other and not an intervention
- A state event is a whole line `[mktsk:YYYY-MM-DDTHH:MM]: # "state"`, local time with no
  zone, anywhere in the file. mktsk writes them in a block at the end, after a blank line,
  or Markdown renders them as text. The last event in file order is the current state; an
  event that cannot be read is left out and never an error, because a hand edited file is
  still a task file
- With no events, `current_state` derives the state from the sections: `open` while the
  file holds one dated section or none, `in-progress` from the second one on
- `append_date_section` writes the new section in front of that final block, never after
  it, so the block stays the end of the file, and follows the heading with two blank lines
  when a block is there, so a note typed on the first blank line is never glued to the
  events; without a block the heading is followed by the usual one
- `with_state` keeps the whitespace in front of an existing block exactly as it is, so the
  two blank lines creation and `append_date_section` leave there survive the state write
  that follows them; when there is no block yet and the text ends with a section heading,
  the heading is followed by two blank lines before the block, for the same reason
- `last_activity` is the most recent date of the interventions, not the last one in the
  file, and `None` when there are none
- Code blocks (``` and `~~~`, closed with the same character) are ignored everywhere, so a
  date or an event written in an example is not one of the task. A fence that is never
  closed runs to the end of the file
- A file may start with a utf-8 byte order mark, which `utf-8` reads as U+FEFF rather than
  taking off, and a mark is not text: left in place it hides the first heading from
  `parse_task` and `is_legacy`. `parsing.without_bom` takes it off, and it is
  the one place that does, so every reader goes through it. Nothing that writes adds a mark
  or takes one away, so a file keeps the one it was written with
- `is_legacy` recognises the old format: the first non-empty line is a level 1 heading
  with no date on it, and the file has a level 2 heading with a date. It is never read as
  the new one, so the title is not mistaken for an intervention
- `parse_task` takes text, not a `Path`, so it never opens anything, and it accepts either
  line break. `line` is the line of the file, counting from 1, code blocks included