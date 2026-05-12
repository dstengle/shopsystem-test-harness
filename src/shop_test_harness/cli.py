"""shop-test-harness CLI entry point.

Subcommands are added as behavior gets pinned by scenarios under
``features/``. This module's job is purely the argparse wiring; per-
subcommand handlers live in sibling modules and are imported here.

Subcommands wired:

* ``bootstrap`` — create a lead-shop + BC-shop topology under --target
  (``shop_test_harness.bootstrap``).
* ``freeze`` — copy a live topology into ``<evidence>/runs/N/``
  (``shop_test_harness.freeze``).
* ``verify`` — compare echoed scenario hashes against an expected list
  (``shop_test_harness.verify``).
"""
from __future__ import annotations

import argparse
import sys

from shop_test_harness import bootstrap, freeze, verify


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
    subparsers = parser.add_subparsers(dest="command")

    bootstrap.add_subparser(subparsers)
    freeze.add_subparser(subparsers)
    verify.add_subparser(subparsers)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help(sys.stderr)
        return 0
    handler = getattr(args, "handler", None)
    if handler is None:
        # Should not happen — every subparser sets ``handler`` as a default.
        parser.print_help(sys.stderr)
        return 2
    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
