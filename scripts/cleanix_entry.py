"""PyInstaller entry point — builds a standalone `cleanix` binary."""

import sys

from cleanix.cli import main

if __name__ == "__main__":
    sys.exit(main())
