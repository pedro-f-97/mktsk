## GUI

- Entry point `mktsk-gui`; PySide6 comes in the optional `gui` extra; tests in
  `tests/test_gui_listing.py`, `tests/test_gui_target.py`, `tests/test_gui_header.py`,
  `tests/test_gui_actions.py`, `tests/test_gui_create.py`, `tests/test_gui_icons.py`,
  `tests/test_gui_activity.py`, `tests/test_gui_columns.py`, `tests/test_gui_row_text.py`,
  `tests/test_gui_date_column.py`, `tests/test_gui_state.py`, `tests/test_gui_close.py`,
  `tests/test_gui_reopen.py`
  and `tests/test_gui_window.py` with pytest-qt
- No Qt imports in the CLI or the business logic
- One module per responsibility, and a widget never takes over from its neighbour: the
  window imports the widgets it is built from, and a widget only reports what it was
  asked for, so new code goes in the module that matches what it does. No module of
  the package takes the name of one in `mktsk/`, which is why the widget that lists
  tasks is `tasklist.py` and not `listing.py`
- Two panes in a `QSplitter`: a `QTreeWidget` on the left holding the current directory
  and its immediate subdirectories, so it shows where new tasks are created; a
  `QTabWidget` on the right holding one `QListWidget` per task category
- The tree lists folders only, one level deep, and never task folders or hidden
  directories (`list_subdirectories`); double-clicking a subdirectory navigates to it
  and the root does nothing
- A directory that cannot be read holds nothing and is left out rather than raising, so
  `_tasks_in` and `list_subdirectories` both return nothing for one and `find_task_groups`
  lists the categories it can read; this is why `refresh` in the GUI needs no `try` around
  `_reload_tree`, and it is also why a locked directory disappears instead of complaining
- A `+` button sits at the right end of the `Directory` header row and creates a category
  in the current directory (`create_category`); the button is a child of the header widget
  and is placed by arithmetic against the header size, because
  `QHeaderView.sectionViewportGeometry` is missing from the PySide6 stubs
- The button is squared off to the header height, so it cannot overflow the row, and
  carries an icon and a tooltip like every other button in the window
- A new category is left selected, so it becomes the creation target at once; a category
  that is already there is not an error, it is just selected
- A subdirectory selected in the tree is where a new task is created
  (`creation_directory`), so a task lands in a category without entering it; the root,
  or nothing selected, makes the current directory the target; selecting does not
  navigate and does not change the active tab
- The tree selection survives a refresh, so a second task lands in the same category; a
  selected category that is no longer there is dropped and the current directory takes
  over
- Lookup for a title runs in the target directory, not in the current one, so the same
  title in another directory is still a different task
- A hint beside the title field reads `New tasks in <category>`, shown only when the
  target is not the current directory; it sits between the title field and the `Create`
  button, in the same font and only the colour tells it apart, so it adds no height, and
  the full path is its tooltip
- The task list comes from `find_task_groups`: one tab per category, the current
  directory being a category named after itself, plus an `All` tab first; only
  categories that hold tasks get a tab
- `All` lists every task under a heading per category, headings bold and not
  selectable; a category tab lists just its own tasks, with no heading. Neither shows a
  closed task: a category whose tasks are all closed gets no tab and no heading, and a
  `Closed` tab last holds every archive under a heading per category, appearing only
  when there is at least one
- The active tab survives a refresh or a new task; when its category is gone, `All`
  takes over again
- Within a category, by last activity, newest first, alphabetical for tasks of the same
  last activity. The date column shows the date of the folder and the last activity column
  says how long ago the last intervention was, so the date on a row and the order of the
  rows can disagree
- A task folder with no `.md` is not listed; a task two levels down is not found
- A task row is five columns, `Date`, `Task`, `State`, `Interventions` and `Last activity`.
  The date is `dd/mm/yyyy`, read from the folder name or, for a closed task, the archive
  name; the task is `readable_title`, with the full path as tooltip; the state is
  `entry.state`, spelled as the file spells it; the interventions are the count from the
  `.md`, `0` when there are none; the activity is `_relative_age`, which says `today`,
  `yesterday` or `N days ago`, and reads a date that has not come yet as `today`
- The date and the task come from the `TaskEntry` the row carries, the same entry the state,
  the count and the age come from, so the delegate reads the folder name without another
  import; `_date_cell` reads the date out of the name with `standards`, falling back to the
  raw prefix when the name is not a task folder
- `TaskPanel` is what a tab holds: `_ColumnHeader` over `TaskListing`. The header is the
  only source of column geometry: the delegate reads each column's position and size from it
  (`sectionPosition` and `sectionSize`), so a heading never sits over a value of another
  column and dragging a separator moves the cells with it. `_column_widths` measures the
  three right columns from the bold application font; the date column is a date wide, like
  any other column; the task takes the rest of the room it had
- The width of every item is the header's `length()`, so a header wider than the viewport
  makes the list scroll horizontally, and the horizontal scrollbar's `valueChanged` moves
  the header's offset with it; `sectionResized` lays the cells out again and repaints the
  viewport, and a row without a count is a heading painted across the whole item width
- The state, the count and the age reach the delegate in the item roles `_STATE_ROLE`,
  `_COUNT_ROLE` and `_AGE_ROLE`, so painting reads no file and holds no date of its own.
  The window takes one day per reload and hands it to every row, so a refresh that runs as
  the date turns does not date half of the tasks to yesterday
- A row without those roles is a heading, which has no activity of its own and is painted
  where it stands, across the row
- A task row empties `option.text` in `initStyleOption`, not in `paint`, because the base
  class refills it from the display role on every paint; the style then draws only the row
  background, and the five cells are the whole text of the row, each inside its own column.
  The date is the first text after the room the bar reserves on every row, so the date never
  moves when a row is selected; only the selected row hands the style a rect narrowed from the
  left, so the space for the buttons appears when the row is clicked and is given back when the
  selection goes. Every row keeps the height the bar needs, or the list would shift as the
  selection moves. The date section is held at least as wide as the bar, so a separator cannot
  drag it under the bar and over the start of the task
- The pen of a cell is always paired with the background it is drawn on, and never a colour
  written down. The style paints the selection of a row, because the selection of a view is
  the style's, and the delegate only picks the text colour: a selected row asks the style
  to paint the panel item over an image of the row, reads back the fill, and takes the
  `HighlightedText` or the `Text` of the palette group its state belongs to, whichever
  holds better against exactly that fill. The fill of a real platform style is not always
  in the palette, so the pen comes from what the style paints rather than from a palette
  the row is not made of, and a style that paints no selection leaves the base colour,
  which is then what the text is measured against. The pen is remembered per style, group
  and selection, because the style does not change what it paints while the application
  runs. Only the selected row is handed to the style with its rect narrowed from the left
  by the width of the bar, so the fill and the indicator start between the bar and the date
  text and the bar sits over the plain room in front of the date. An unselected row reads
  `Text` of the group, which is what keeps tasks and folders apart as they were
- Selecting a task shows an action bar over that row, aligned to the left, with the
  `Open`, `Resume` and `Rename` buttons, the change-state one and `Close`; it moves with
  the selection and disappears with it
- The buttons carry an icon and a tooltip, never a text label; the icons are a folder for
  `Open`, a plus for `Resume`, a pencil for `Rename`, a ring with a dot for the state and
  an archive box for `Close`, all drawn with `QPainter` in `gui/icons.py`, so no image
  file has to be collected for a frozen build
- The bar only ever sits on a task row; a heading is not selectable, and `TaskListing`
  checks the item holds a `TaskEntry` before showing or placing the bar. A row in the
  `Closed` tab gets a bar with only the reopen button, and room for it, because reopening
  is the one action that reaches an archive; `set_reopening` takes the other four buttons
  out until the folder stands again, and gives the resume button the reopen icon and
  tooltip while it stands for one, putting them back afterwards
- The date cell is drawn after the room the bar reserves on every row, so the date never
  moves when a row is selected; only the selected row hands the style a rect narrowed from
  the left, so the space for the buttons appears when the row is clicked and is given back
  when the selection goes. Every row keeps the height the bar needs, or the list would shift
  as the selection moves. The date section is held at least as wide as the bar, so a
  separator cannot drag it under the bar and over the start of the task
- `Open` replaces the double click on a task; `Open` reveals the task folder in the file
  manager and touches nothing, `Resume` opens the `.md`, `Rename` does not open it, it
  just refreshes the list
- The change-state button carries a menu of `_OFFERED_STATES`, the states of
  `parsing.STATES` without `closed`, which only arrives by closing the task; the list of
  the three is never written down a second time. Picking one emits `state_requested` with
  the entry and the state, the window calls `set_state` on the `.md` of that task and
  refreshes the list, and a failure is shown in a `QMessageBox` like every other action,
  never left to crash the window. Nothing is opened, and with no selection nothing
  changes. The menu opens from `clicked` rather than from the press, because a menu that
  opens while the button is down makes the click wait for it to close
- `Resume` is the only browse action that appends a date, and it appends it to the task
  it was asked for, not to one looked up in the current directory. On a row that holds an
  archive the window reopens it instead, through `reopen_task`, and refreshes the listing
  as well, because the row carries the count and the age that the new intervention has
  changed
- `Close` emits `close_requested` with the entry, and the window calls `close_task` on
  the folder the entry points at, showing a failure in a `QMessageBox.critical` like every
  other action and refreshing the list on success, so the task moves to the `Closed` tab.
  Nothing is opened either way, and with no selection nothing changes
- Remember the last path with `QSettings`
- Show `TaskError` in a `QMessageBox`; if opening the file fails, warn but never delete
  what was created; the warning carries the error as it is, `helpers.open_file` already
  words it, so the path is never hidden behind a duplicated prefix
- Keep the window open and clear the title field after creating