# mktsk

CLI tool and desktop GUI for quickly setting up task folders.

## Features

* Creates task folders using the `YYMMDD - TaskName` naming convention.
* Creates an associated Markdown file.
* Adds the task title to the Markdown file, as a heading.
* Can be run from any directory.
* Optional desktop GUI (`mktsk-gui`) for the same workflow.

## Installation

From the project directory:

```bash
python -m pip install .
```

For development:

```bash
python -m pip install -e .
```

The desktop GUI requires the optional `gui` extra (PySide6):

```bash
python -m pip install ".[gui]"
```

For development with the GUI (including its tests):

```bash
python -m pip install -e ".[dev,gui]"
```

## Usage

Run:

```bash
mktsk It's Alive!
```

Creates:

```text
260923 - ItsAlive/
└── ItsAlive.md
```

The Markdown file contains:

```markdown
# 260923 - ItsAlive
```

The task folder is created in the directory from which `mktsk` is executed.

The Markdown file is then automatically opened with the system's default application.

If the folder already exists, no duplicate is created and no content is overwritten: the
existing Markdown file is opened instead.

Titles that normalize to an empty name, or to a Windows reserved name (`CON`, `PRN`, `AUX`,
`NUL`, `COM1-9`, `LPT1-9`), are rejected with an error.

## Desktop GUI

Launch with:

```bash
mktsk-gui
```

Or as a module:

```bash
python -m mktsk
```

Opens a window where you can:

* pick a base folder with the native file dialog or navigate inside the window;
* create a task with the same rules as the CLI, opening the resulting Markdown file with
  the default application;
* open existing `.md` files by double-clicking.

The last visited folder is remembered between sessions.

## Standalone executable

Release builds include a single-file executable of the GUI, for people who do not
want to install Python:

* `mktsk-gui-windows-x64.exe` for Windows;
* `mktsk-gui-linux-x86_64-glibc<version>` for Linux, named after the glibc it was
  built against.

The first launch unpacks the executable to a temporary folder, so it takes a
few seconds. The executables are not code signed, so antivirus software may
report them.

The source distribution (`mktsk-*.tar.gz`) attached to the same release is the
corresponding source for these executables, as required by GPL-3.0 section 6.

## Tests

Run with:

```bash
pytest
```

The project maintains high test coverage (95%+ enforced in CI).

## License

GPL-3.0-or-later. See [LICENSE](LICENSE).

