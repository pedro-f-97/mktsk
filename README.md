# mktsk

CLI tool for quickly setting up task folders.

## Features

* Creates task folders using the `YYMMDD - TaskName` naming convention.
* Creates an associated Markdown file.
* Adds the task name to the Markdown file.
* Can be run from any directory.

## Installation

From the project directory:

```bash
python -m pip install .
```

For development:

```bash
python -m pip install -e .
```

## Usage

Run:

```bash
mktsk It's Alive!
```

Creates:

```text
260923 - ItSAlive/
└── ItSAlive.md
```

The Markdown file contains:

```markdown
# 260923 - ItSAlive
```

The task folder is created in the directory from which `mktsk` is executed.

The Markdown file is then automatically opened with the system's default application.


## Tests

Run with:

```bash
pytest
```

The project maintains high test coverage (95%+ enforced in CI).
