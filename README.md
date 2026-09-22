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
mktsk
```

Enter the task description when prompted.

For example:

```text
Task description:
Alterar formulário de embalagem
```

Creates:

```text
260922 - AlterarFormularioDeEmbalagem/
└── AlterarFormularioDeEmbalagem.md
```

The Markdown file contains:

```markdown
# 260922 - AlterarFormularioDeEmbalagem
```

The task folder is created in the directory from which `mktsk` is executed.
