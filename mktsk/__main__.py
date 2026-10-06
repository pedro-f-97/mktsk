import sys

from .gui import main as gui_main
from .main import main as cli_main


def main() -> int:
    if len(sys.argv) > 1:
        return cli_main()
    return gui_main()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
