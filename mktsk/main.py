import argparse
from pathlib import Path

from . import helpers, workers


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("title", nargs="+")
    return parser.parse_args()

def main() -> int:
    args = parse_arguments()

    raw_title = " ".join(args.title)

    try:
        result = workers.open_or_create_task(Path.cwd(), raw_title)
        print(result.message)
    except (OSError, helpers.TaskError) as error:
        print(f"Error: {error}")
        return 1

    try:
        helpers.open_file(result.file)
    except OSError as error:
        print(f"Warning: {error}")

    return 0

if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())