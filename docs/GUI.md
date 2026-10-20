## GUI

- Entry point `mktsk-gui`; PySide6 comes in the optional `gui` extra; tests in
  `tests/test_gui_listing.py`, `tests/test_gui_target.py`, `tests/test_gui_header.py`,
  `tests/test_gui_actions.py`, `tests/test_gui_create.py`,
  `tests/test_gui_destination.py`, `tests/test_gui_icons.py`,
  `tests/test_gui_activity.py`, `tests/test_gui_columns.py`, `tests/test_gui_attachments.py`,
  `tests/test_gui_row_text.py`,
  `tests/test_gui_date_column.py`,   `tests/test_gui_state.py`, `tests/test_gui_close.py`,
  `tests/test_gui_reopen.py`, `tests/test_gui_layout.py`,
  `tests/test_gui_search_panel.py`
  and `tests/test_gui_window.py` with pytest-qt
- No Qt imports in the CLI or the business logic
- No Qt GUI objects at module level or in caches, so none outlives the `QApplication`
- A QProxyStyle must wrap a style of its own (QStyleFactory.create), never widget.style() or QApplication.style()
- One module per responsibility, and a widget never takes over from its neighbour: the
  window imports the widgets it is built from, and a widget only reports what it was
  asked for, so new code goes in the module that matches what it does. No module of
  the package takes the name of one in `mktsk/`, which is why the widget that lists
  tasks is `tasklist.py` and not `listing.py`
- Two panes in a `QSplitter`: a `QTreeWidget` on the left holding the current directory
  and its immediate subdirectories, so it shows where new tasks are created; a
  `QTabWidget` on the right holding one `QListWidget` per task category
- The left pane is a unit of its own, top to bottom: the `Directory` header, the path
  label, then the tree and, below it, the search panel. The header is a standalone
  `QHeaderView` above the path, so it
  keeps the native header look rather than a hand-painted row, and the tree's own header
  is hidden. It shares the tree's single section, so it carries the same `Directory`
  title and stays in step with `set_header_label`
- The path sits directly under the header, full width of the pane, elided in the middle
  to the room it has, and indented by the same padding the header gives its title, so the
  path and the title line up as one column
- The path label uses the `Base` background, like the tree, so the two share one fill
- `Choose...` and `Up` sit in the `Directory` header, to the left of `+` and in the same
  size: `Choose...` opens the native dialog (`choose_directory`) and `Up` walks to the
  parent directory (`go_up`). The three share the header, so the tree's minimum width is
  the label plus the room they need, and the label never runs under them
- The header title starts at the left padding the path is indented by, and the tree drops
  the title when the header is too narrow to hold it before the buttons, restoring it as
  soon as there is room again, so the buttons never sit over it
- A vertical splitter inside the left pane holds the Directory block (header, path row,
  and tree) in one container and the Search panel in the other, with stretch factors 3
  and 2 keeping the initial split and window-resize behaviour 3:2; `setChildrenCollapsible`
  is false, each child has a sane minimum height so neither can be dragged to nothing,
  and the search panel keeps at least its header and the field. Persistence follows the
  same mechanism as the other splitters when present. Under the tree the left pane holds
  a `Search` panel: its own header titled `Search`, a line edit with the `Search tasks`
  placeholder and a clear button, and a results list below. The header is a standalone
  `QHeaderView` over the results' model, the way the `Directory` header sits over the
  tree's, with the other two sections hidden; both headers take the height of the tab
  bar, so they read as one set. The panel sits inside the pane and it collapses with the pane
- The results hold the tasks the listings hold, closed ones included, and the query runs
  again over them on every reload, so a task created or closed since is reached the way
  the table now lists it; the result that was highlighted is highlighted again when it
  still matches. The query comes from `search_tasks`, so it matches the text the `Task`
  column shows, and an empty or whitespace-only query shows no results and no hint
- A result row carries the date in the `Date` column format, the title as the `Task`
  column spells it, and the category in the palette's `PlaceholderText`, so it is dimmed
  with no colour written down; the full path is its tooltip
- Only a click on a result or an activation on it (double click or `Enter` on a
  highlighted row) reaches the table, through `select_task`, so typing and a refill of
  the results never move the selection; `Return` in the field activates the first
  result, and `Esc` in the field clears it, which empties the results with it. Selecting
  a result never picks a category, so the destination a new task lands in stays where it
  was
- The right pane is a side rail beside the creation bar and the tabs: the rail is the
  first column, spans the full height of the pane and is as wide as the `Refresh` button
  it carries at its top, so the button no longer sits in the tab bar corner, which is
  left empty. The title field, the hint and `Create` sit above the task table, in the
  pane and not across the window, to the right of the rail. The field takes the rest of
  the row and `Create` sits at its right end
- Below `Refresh` the rail carries the pane toggle, a flat `QToolButton` that fills the
  rest of the rail and is not in the tab order. Clicking it while the pane is visible
  remembers the width the pane had and collapses it through the same splitter sizes a
  drag of the handle would set (`setSizes([0, total])`); clicking it while the pane is
  collapsed restores that remembered width, or the split the splitter opened with when
  the collapse came from a drag. Its tooltip is `Hide panel` while the pane is visible
  and `Show panel` while it is collapsed, and follows a drag through the splitter's
  `splitterMoved`
- The bar draws a thin vertical line down its centre, broken by a chevron in its middle:
  `<` while the pane is visible and `>` while it is collapsed, turned by the same state
  that words the tooltip. The line is the palette's `Mid` while idle and takes the
  chevron's `ButtonText` colour when the mouse is over the bar, and the chevron is always
  drawn in that colour, the one the Directory header icon buttons carry
- The Directory header shares its top edge with the creation bar; the tab bar and the task
  table sit below the bar. Each pane keeps the window margin (`_MARGIN`) on its outer edge,
  so the two are separated by the splitter handle alone rather than by stacked margins
- The tree lists folders only, one level deep, and never task folders or hidden
  directories (`list_subdirectories`); double-clicking a subdirectory navigates to it
  and the root does nothing
- A directory that cannot be read holds nothing and is left out rather than raising, so
  `_tasks_in` and `list_subdirectories` both return nothing for one and `find_task_groups`
  lists the categories it can read; this is why `refresh` in the GUI needs no `try` around
  `_reload_tree`, and it is also why a locked directory disappears instead of complaining
- A `+` button sits at the right end of the `Directory` header row and creates a category
  in the current directory (`create_category`); `Choose...` and `Up` sit beside it to the
  left, and the tree places all three from the right end of the header by arithmetic
  against the header size, because `QHeaderView.sectionViewportGeometry` is missing from
  the PySide6 stubs
- Every header button is squared off to the header height, so none overflows the row, and
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
- The label carries a small flat `x` button at its right, shown exactly while
  the label is and hidden with it: clicking it clears the tree selection through
  the same path a selection change takes, so the line and the `x` go with it and
  the next task is created in the base folder. The `x` is two crossing strokes
  drawn like the other icons, in the colour the Directory header buttons carry,
  smaller than their icons, out of the tab order and top-aligned in the row, so
  the bar keeps its height and its line with the Directory header
- Clicking a category heading in `All` picks that folder as the destination just as
  clicking it in the tree does, so the label names it and the next task lands there; the
  heading drops the selected task first, through the same path `Esc` takes. A task row
  never changes the destination, and a `Closed` heading stands for no folder a task could
  land in, so clicking one does nothing. The heading of the current destination carries a
  small dot at its right end, drawn by the delegate in the colour the Directory header
  buttons carry, which follows the tree however the selection moves and goes with it; a
  category with no heading to carry it, because it is empty or its tasks are closed, shows
  no marker
- Clicking the heading of the base folder clears the destination, like the `x` on the
  label: the tree selection drops, the line, the `x` and the marker go with it, and the
  next task lands in the base folder
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
- Clicking a column heading orders the rows of that tab by it, ascending on the first
  click and descending on the next; clicking another heading starts ascending on that one,
  and no click ever returns to the default order by itself; the clip heading carries no name
  and orders nothing when clicked. Each tab keeps the column and
  the direction it was last sorted by while it is open, and a refresh re-applies it. The
  tasks of a category reorder among themselves, and the categories of the `All` and
  `Closed` tabs then reorder with them, by the first task under each heading, so the
  category holding the first record leads and two categories whose first tasks tie keep the
  order they had; a heading always stays above its own tasks. Ties keep the default order, the date is
  read from the folder name with a name that is not a task folder last, the task ignores
  case, the state follows the order of the domain, the interventions are counted as a
  number, and the last activity is read as the date it carries. Dragging a separator still
  resizes, and the native indicator marks the heading that is in force
- A task folder with no `.md` is not listed; a task two levels down is not found
- A task row is six columns, `Date`, `Task`, a clip column with no heading, `State`,
  `Interventions` and `Last activity`. The date is `dd/mm/yyyy`, read from the folder name
  or, for a closed task, the archive name; the task is `readable_title`, with the full path
  as tooltip; the clip column is blank until the folder carries an attachment, and then
  shows a paperclip and the number of them side by side; the state is
  `entry.state`, spelled as the file spells it; the interventions are the count from the
  `.md`, `0` when there are none; the activity is `_relative_age`, which says `today`,
  `yesterday` or `N days ago`, and reads a date that has not come yet as `today`
- The date and the task come from the `TaskEntry` the row carries, the same entry the
  attachments, the state, the count and the age come from, so the delegate reads the folder
  name without another import; `_date_cell` reads the date out of the name with
  `standards`, falling back to the raw prefix when the name is not a task folder
- `TaskPanel` is what a tab holds: `_ColumnHeader` over `TaskListing`. The header is the
  only source of column geometry: the delegate reads each column's position and size from it
  (`sectionPosition` and `sectionSize`), so a heading never sits over a value of another
  column and dragging a separator moves the cells with it. Every named column is measured
  from the bold application font, the clip column from the paperclip and the two digits it
  may hold at once, and the date column from a date; the clip column is held at that fixed
  width and cannot be dragged; the task starts as the rest of the room a row has and is then
  widened to fit the longest visible description, up to `_TASK_MAX_WIDTH`, never below that
  start and never once a separator has been dragged by hand, so a long description reads in
  full until the cap and elides past it
- The width of every item is the header's `length()`, so a header wider than the viewport
  makes the list scroll horizontally, and the horizontal scrollbar's `valueChanged` moves
  the header's offset with it; `sectionResized` lays the cells out again and repaints the
  viewport, and a row without a count is a heading painted across the whole item width
- The state, the count and the age reach the delegate in the item roles `_STATE_ROLE`,
  `_COUNT_ROLE` and `_AGE_ROLE`, and the clip column reads its number from that same entry
  rather than a role of its own, so painting reads no file and holds no date of its own.
  The window takes one day per reload and hands it to every row, so a refresh that runs as
  the date turns does not date half of the tasks to yesterday
- A row without those roles is a heading, which has no activity of its own and is painted
  where it stands, across the row
- A task row empties `option.text` in `initStyleOption`, not in `paint`, because the base
  class refills it from the display role on every paint; the style then draws only the row
  background, and the six cells are the whole text of the row, each inside its own column.
  The date is the first text after the room the indicator rail reserves on every row, so
  the date never moves when a row is selected; the bar of the selected row is indented
  past the rail rather than the cells being pushed right, and every row keeps the height
  the bar needs, or the list would shift as the selection moves. The date section is held
  at least as wide as the bar, so a separator cannot drag it under the bar and over the
  start of the task
- The selection of a task row is the delegate's own, painted over the one the style
  paints, so it looks the same under every style: a faint tint of the palette covers the
  whole selected area, the task row and the band it opens, so the two read as one and the
  band reads apart from the plain background, and a rail of the full `Highlight` sits at
  its left edge, wide enough to read and rounded at both ends. Both colours come from the
  palette group the state belongs to, the tint blending `Base` a little towards
  `Highlight`, so a light or dark mode and a new accent follow with no colour written
  down. The pen of a cell stays paired with the background it is drawn on: a selected row
  takes the `HighlightedText` or the `Text` of its group, whichever holds better against
  that same tint, and an unselected row reads `Text` of the group, which is what keeps
  tasks and folders apart as they were
- The list is striped to keep the eye on a row, and the colours are derived from the
  palette through one blend function rather than written down, so a dark mode needs no
  change. Every second task row under a separator is filled with the `Base` of its palette
  group blended a little towards the `Text`, a separator is filled the same way a touch
  stronger, and the stripe restarts at every separator, so the first task under one is
  always the plain `Base`. The delegate fills an unselected task row alone, before the
  style paints, so hover and the native look stay on top; a selected row gets no stripe
  of its own, because the selection tint the delegate paints over the style's covers it.
  A separator is painted as an enabled row, so its text
  keeps the `Text` of a task row rather than the grey a non-selectable row would be drawn
  in; the enabled state alone does not carry a style that reads the disabled group the view
  hands a non-selectable row, so the separator's palette is pointed at the group a task row
  uses before the style paints it
- Selecting a task shows an action bar over that row, aligned to the left, with the
  `Open`, `Resume` and `Rename` buttons, the change-state one and `Close`; it moves with
  the selection and disappears with it
- `Esc` in the task table deselects the current task, so the bar goes with the
  selection, and clears the destination through the same handler the label's `x` calls
- `TaskListing.select_task(path)` selects the row whose entry carries `path` and scrolls it
  into view, answering `True`; a path no row of this listing or of another tab holds answers
  `False`, with the selection and the current tab left as they were. A row in another tab is
  reached by switching to that tab first, so the action bar and the preview follow the task
  as they would after a click. It never changes the destination: no category is picked and
  none is cleared, so a new task lands where it would have landed without it
- Below the task table a read-only preview of the selected task shares the pane through
  a vertical `QSplitter`, the table over the preview and the two resizable between
  them, the table keeping the larger share. On the left the raw text of the `.md`,
  shown as it stands with no Markdown rendering and read again on every selection, so a
  reload re-renders the task that is still selected, or hides the preview when it is
  gone; on the right the names of the other attachments the folder carries
  (`list_attachments`), subfolders with a trailing `/` and the list hidden when there
  are none, so the text takes the full width. The preview follows the selection through
  the same path the action bar takes, so no selection, a heading selected or `Esc`
  hides it and the table keeps the full height; a `.md` that cannot be read previews as
  empty and never raises, and a closed task previews empty as well, because its archive
  is never opened. Neither panel takes focus, and the attachment list takes no
  selection, no click and no context menu. The attachment list stripes its rows through
  `setAlternatingRowColors`, so the colour comes from the palette and a light or dark
  mode follows with nothing written down
- Each panel of the preview opens with a title at its top, inside it: `Details` over
  the raw text and `Attachments` over the list. Both are standalone `QHeaderView`s
  carrying their title the way the `Directory` and `Search` headers do, so they take
  the tab bar height and the palette with nothing written down, and neither takes a
  click, a sort or the focus. The titles show and hide with the preview itself, so
  they appear only while a task is selected, and the `Attachments` title hides with
  its panel when the folder carries none, leaving `Details` the full width
- The buttons carry an icon and a tooltip, never a text label; the icons are a folder for
  `Open`, a plus for `Resume`, a pencil for `Rename`, a ring with a dot for the state and
  an archive box for `Close`, all drawn with `QPainter` in `gui/icons.py`, so no image
  file has to be collected for a frozen build. `Choose...`, `Up` and `Refresh` are drawn
  the same way, and `_icon_button` also gives each icon a faded copy for the disabled
  state and the tooltip as its accessible name
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