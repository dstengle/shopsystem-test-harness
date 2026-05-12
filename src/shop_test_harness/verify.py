"""``shop-test-harness verify`` — compare the BC's echoed scenario hashes
to an expected list.

Inputs:

* ``--target <dir>`` — experiment target directory containing the BC shop.
* ``--bc <name>`` — BC shop subdirectory name.
* ``--work-id <id>`` — work_id identifying the assignment whose
  ``work_done`` is being verified.
* ``--expected <path>`` — file with one expected hash per line. Blank
  lines and lines starting with ``#`` are ignored so the file can carry
  a human-readable header without breaking parsing.

Behavior:

* On match (set equality): exit 0, stdout ``"verify: N hashes match"``,
  empty stderr. We report the size of the *matched* set because that is
  what the scenario asserts.
* On divergence: exit non-zero, empty stdout, stderr names two gaps
  separately:

    - forward-conformance: hashes expected but not echoed back
      (the BC under-delivered or echoed the wrong hashes).
    - reverse-conformance: hashes echoed back but not expected
      (the BC over-delivered, claimed credit it was not assigned).

The two labels matter to the scenario, so the wording is fixed.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from catalog.schemas import WorkDone


def _load_expected(path: Path) -> list[str]:
    text = path.read_text()
    out: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        out.append(line)
    return out


def _load_work_done(target: Path, bc: str, work_id: str) -> WorkDone:
    """Locate and parse ``<target>/<bc>/outbox/<work-id>-work_done.yaml``."""
    path = target / bc / "outbox" / f"{work_id}-work_done.yaml"
    if not path.exists():
        raise FileNotFoundError(f"work_done file not found at {path}")
    data = yaml.safe_load(path.read_text())
    # Validate via the messaging package's schema rather than trusting
    # raw YAML — this also enforces ``message_type == 'work_done'``.
    return WorkDone(**data)


def run_verify(
    target: Path,
    bc: str,
    work_id: str,
    expected_path: Path,
) -> int:
    target = target.resolve()
    expected_path = expected_path.resolve()

    try:
        work_done = _load_work_done(target, bc, work_id)
    except FileNotFoundError as exc:
        sys.stderr.write(f"verify: {exc}\n")
        return 2
    except Exception as exc:  # noqa: BLE001 — surface schema errors verbatim
        sys.stderr.write(f"verify: failed to parse work_done: {exc}\n")
        return 2

    expected = set(_load_expected(expected_path))
    echoed = set(work_done.scenario_hashes)

    forward_missing = expected - echoed   # expected but not echoed
    reverse_extra = echoed - expected     # echoed but not expected

    if not forward_missing and not reverse_extra:
        matched = len(expected & echoed)
        sys.stdout.write(f"verify: {matched} hashes match\n")
        return 0

    # Divergence path: name both gaps separately, in deterministic order.
    if forward_missing:
        for h in sorted(forward_missing):
            sys.stderr.write(
                f"forward-conformance gap: expected but not echoed: {h}\n"
            )
    if reverse_extra:
        for h in sorted(reverse_extra):
            sys.stderr.write(
                f"reverse-conformance gap: echoed but not assigned: {h}\n"
            )
    return 1


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "verify",
        help="check that a BC's work_done echoed back the expected scenario hashes",
        description=(
            "Compare scenario_hashes echoed back in a BC shop's "
            "<work-id>-work_done.yaml against an expected list of "
            "hashes (one per line). Exits 0 on set equality. On "
            "divergence, exits non-zero and reports forward-conformance "
            "(expected-but-not-echoed) and reverse-conformance "
            "(echoed-but-not-assigned) gaps separately on stderr."
        ),
    )
    p.add_argument("--target", required=True, type=Path,
                   help="experiment target directory containing the BC shop")
    p.add_argument("--bc", required=True,
                   help="BC shop subdirectory name")
    p.add_argument("--work-id", required=True,
                   help="work_id whose work_done is being verified")
    p.add_argument("--expected", required=True, type=Path,
                   help="path to file listing expected scenario hashes "
                        "(one per line; blanks and # comments ignored)")
    p.set_defaults(handler=_handler)


def _handler(args: argparse.Namespace) -> int:
    return run_verify(
        target=args.target,
        bc=args.bc,
        work_id=args.work_id,
        expected_path=args.expected,
    )
