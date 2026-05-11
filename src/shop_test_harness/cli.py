"""shop-test-harness CLI entry point.

Subcommands are added as behavior gets pinned by scenarios under
``features/``. This module's job is purely the argparse wiring; per-
subcommand handlers live in sibling modules and are imported here.

At v0.1.0 the CLI exposes only ``--help``. Subcommands land via
forthcoming ``assign_scenarios`` work from the lead shop.
"""
from __future__ import annotations

import argparse
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="shop-test-harness",
        description=(
            "Harness for the shopsystem product. Drives experiments "
            "and validates the framework against itself by composing "
            "shop-msg, scenarios, and shop-templates at the CLI "
            "boundary."
        ),
    )
    parser.add_subparsers(dest="command")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help(sys.stderr)
        return 0
    # No subcommands wired yet — assign_scenarios from the lead will
    # add them.
    return 0


if __name__ == "__main__":
    sys.exit(main())
