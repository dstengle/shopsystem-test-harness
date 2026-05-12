"""``shop-test-harness bootstrap`` — stand up an isolated shop topology.

A bootstrapped topology under ``--target`` is two sibling shop
directories: the lead shop (``<target>/<lead-shop>/``) and one BC shop
(``<target>/<bc-shop>/``). Each shop is the same shape downstream
tooling (``shop-msg``, ``bd``) expects:

    <shop>/
      inbox/
      outbox/
      .beads/        (initialized via ``bd init``)

The two scenarios pinned in ``features/`` require that:

* both subdirectories exist with empty ``inbox/`` and ``outbox/``;
* both have a ``.beads/`` directory whose beads metadata is sufficient
  for ``bd list`` to run cleanly, with the issue prefix matching the
  shop name;
* ``shop-msg send request_maintenance --bc-root <target>/<bc-shop>``
  succeeds against the resulting BC shop.

We delegate beads metadata creation to ``bd init`` itself (rather than
synthesizing ``.beads/config.yaml`` by hand) — that is the only sure
way to keep up with whatever the bd binary considers "sufficient".
``--skip-agents --skip-hooks`` keep the init free of editor/agent
artifacts that would just be noise in an experiment evidence trail;
``--non-interactive`` makes it safe under pytest's captured stdin.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def _make_shop(shop_dir: Path, prefix: str) -> None:
    """Create one shop's directory layout and initialize beads in it.

    Idempotent on the directory layout (``mkdir`` with ``exist_ok``)
    but defers to ``bd init`` for the ``.beads/`` contents. ``bd init``
    is invoked with the shop directory as its working directory so the
    embedded Dolt database lands inside the shop, not in the harness
    process's cwd.
    """
    (shop_dir / "inbox").mkdir(parents=True, exist_ok=True)
    (shop_dir / "outbox").mkdir(parents=True, exist_ok=True)

    # Hand the inner directory to ``bd init``. The ``--prefix`` flag
    # sets the issue-id prefix, which the scenarios require to match
    # the shop directory name.
    env = os.environ.copy()
    env["BD_NON_INTERACTIVE"] = "1"
    subprocess.run(
        [
            "bd",
            "init",
            "--prefix",
            prefix,
            "--quiet",
            "--skip-agents",
            "--skip-hooks",
            "--non-interactive",
        ],
        cwd=str(shop_dir),
        env=env,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )


def run_bootstrap(
    target: Path,
    lead_shop: str,
    bc_shop: str,
) -> int:
    """Create a fresh ``lead-shop`` + ``bc-shop`` topology under ``target``.

    Returns the process exit code (0 on success). Errors from ``bd init``
    propagate as a non-zero exit with the underlying stderr forwarded.
    """
    target = target.resolve()
    target.mkdir(parents=True, exist_ok=True)

    try:
        _make_shop(target / lead_shop, lead_shop)
        _make_shop(target / bc_shop, bc_shop)
    except subprocess.CalledProcessError as exc:
        sys.stderr.write(
            f"bootstrap: bd init failed: {exc.stderr.decode() if exc.stderr else exc}\n"
        )
        return 1
    return 0


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "bootstrap",
        help="create an isolated lead-shop + BC-shop topology",
        description=(
            "Create an isolated experiment topology under --target with "
            "two shops (lead and one BC), each containing empty inbox/ "
            "and outbox/ subdirectories and a .beads/ initialized via "
            "`bd init` with the shop name as the issue prefix."
        ),
    )
    p.add_argument("--target", required=True, type=Path,
                   help="target directory under which the topology is created")
    p.add_argument("--lead-shop", required=True,
                   help="name of the lead-shop subdirectory")
    p.add_argument("--bc-shop", required=True,
                   help="name of the BC-shop subdirectory")
    p.set_defaults(handler=_handler)


def _handler(args: argparse.Namespace) -> int:
    return run_bootstrap(
        target=args.target,
        lead_shop=args.lead_shop,
        bc_shop=args.bc_shop,
    )
