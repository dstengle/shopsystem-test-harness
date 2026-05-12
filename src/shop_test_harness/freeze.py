"""``shop-test-harness freeze`` — snapshot a live topology into evidence.

The scenario pins three things:

1. Output directory is ``<evidence>/runs/N/`` where N is the next free
   integer (1, 2, 3, ...).
2. Every file under each shop in ``<target>/`` is mirrored under the
   matching path inside ``<evidence>/runs/N/``, byte-for-byte.
3. The result is a complete, self-contained copy of the topology at
   the moment freeze was called.

We use ``shutil.copytree`` per shop subdirectory rather than copying
the whole target, because the scenario assertions are scoped to the
shop subdirectories (``<dir>/lead/`` and ``<dir>/bc-foo/``) — copying
the whole target would also pull anything the experiment runner has
lying around at the top level, which is not what evidence should
contain. A shop is anything under ``<target>/`` that has both
``inbox/`` and ``outbox/`` subdirectories.

The embedded Dolt runtime under each shop's ``.beads/embeddeddolt/``
is normally gitignored. We *do* copy it: the scenario says
"every file under <dir>/lead/ and <dir>/bc-foo/ is present", with
no exception carved out for the Dolt runtime. If a future run finds
the runtime files corrupt the byte-for-byte guarantee under
concurrent bd activity, that will surface as a scenario failure and
the lead can carve out an exception then.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


def _next_run_index(runs_dir: Path) -> int:
    """Return the next free integer N such that ``runs_dir/N`` does not exist."""
    if not runs_dir.exists():
        return 1
    used: list[int] = []
    for child in runs_dir.iterdir():
        if child.is_dir() and child.name.isdigit():
            used.append(int(child.name))
    return (max(used) + 1) if used else 1


def _is_shop_dir(path: Path) -> bool:
    """A shop is any subdirectory of <target> with both inbox/ and outbox/."""
    return path.is_dir() and (path / "inbox").is_dir() and (path / "outbox").is_dir()


def run_freeze(target: Path, evidence: Path) -> int:
    target = target.resolve()
    evidence = evidence.resolve()

    if not target.exists() or not target.is_dir():
        sys.stderr.write(f"freeze: target does not exist or is not a directory: {target}\n")
        return 1

    shops = [child for child in sorted(target.iterdir()) if _is_shop_dir(child)]
    if not shops:
        sys.stderr.write(f"freeze: no shops (inbox/+outbox/ subdirs) found under {target}\n")
        return 1

    runs_dir = evidence / "runs"
    n = _next_run_index(runs_dir)
    out_dir = runs_dir / str(n)
    out_dir.mkdir(parents=True, exist_ok=False)

    for shop in shops:
        dest = out_dir / shop.name
        # ``copytree`` preserves the directory structure under each shop
        # verbatim, including dotfiles. ``dirs_exist_ok=False`` is fine
        # because we just created ``out_dir``.
        shutil.copytree(shop, dest, symlinks=True, dirs_exist_ok=False)

    return 0


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "freeze",
        help="copy a live topology into <evidence>/runs/N/",
        description=(
            "Copy every shop subdirectory under --target into a fresh "
            "<evidence>/runs/N/ directory, where N is the next free "
            "integer. The result is a byte-for-byte snapshot of the "
            "topology at the moment of the call."
        ),
    )
    p.add_argument("--target", required=True, type=Path,
                   help="experiment target directory to freeze")
    p.add_argument("--evidence", required=True, type=Path,
                   help="evidence root directory (runs/ is created under it)")
    p.set_defaults(handler=_handler)


def _handler(args: argparse.Namespace) -> int:
    return run_freeze(target=args.target, evidence=args.evidence)
