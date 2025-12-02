"""Command-line interface entry point for AutoData.

This module provides the main CLI entry point that is referenced in pyproject.toml.
"""

import sys
from typing import NoReturn

from autodata.core.exceptions import AutoDataInitializationError
from autodata.main import main as autodata_main


def main() -> NoReturn:
    """Main CLI entry point for AutoData.

    This function serves as the entry point for the 'autodata' command
    and delegates to the main AutoData functionality.

    Raises:
        SystemExit: Always exits with appropriate code
    """
    try:
        autodata_main()
        sys.exit(0)
    except AutoDataInitializationError as exc:
        print(f"Initialization failed: {exc}", file=sys.stderr)
        sys.exit(2)
    except KeyboardInterrupt:
        print("\nOperation cancelled by user", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
