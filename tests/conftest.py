"""Step definitions for the shopsystem-test-harness BDD suite.

Step style mirrors ``shopsystem-scenarios/tests/conftest.py``: every CLI
under test is exercised via ``subprocess.run`` against the installed
console-scripts (``shop-test-harness``, ``shop-msg``, ``bd``), and
cross-step state lives in a ``context`` dict fixture that pytest-bdd
threads through each scenario. The third-party perspective is on
purpose — these scenarios pin the public CLI contract, not Python
internals.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml
from pytest_bdd import given, parsers, then, when


# -----------------------------------------------------------------------
# Shared cross-step state
# -----------------------------------------------------------------------


@pytest.fixture
def context(tmp_path: Path) -> dict:
    """Cross-step state. Pre-seeds the experiment target directory so
    every scenario has a stable ``<dir>`` to refer to without each
    Given having to invent its own path.
    """
    target = tmp_path / "experiment"
    target.mkdir()
    return {"tmp_path": tmp_path, "target": target}


# -----------------------------------------------------------------------
# Bootstrap scenarios — shared Given/When
# -----------------------------------------------------------------------


@given("an empty target directory for an experiment")
def given_empty_target(context: dict) -> None:
    # The ``context`` fixture already created ``target`` empty; assert
    # the invariant rather than recreate it so a later Given that
    # *populates* the target can't silently get reset here.
    target: Path = context["target"]
    assert target.is_dir(), f"expected target to exist as a dir: {target}"
    assert not any(target.iterdir()), (
        f"expected empty target; found entries: {list(target.iterdir())}"
    )


@when(
    parsers.parse(
        'I run "shop-test-harness bootstrap --target <dir> '
        '--lead-shop {lead_shop} --bc-shop {bc_shop}"'
    )
)
def when_run_bootstrap(lead_shop: str, bc_shop: str, context: dict) -> None:
    target: Path = context["target"]
    result = subprocess.run(
        [
            "shop-test-harness",
            "bootstrap",
            "--target", str(target),
            "--lead-shop", lead_shop,
            "--bc-shop", bc_shop,
        ],
        capture_output=True,
        text=True,
    )
    context["cli_returncode"] = result.returncode
    context["cli_stdout"] = result.stdout
    context["cli_stderr"] = result.stderr
    context["lead_shop"] = lead_shop
    context["bc_shop"] = bc_shop


@then("the exit code is 0")
def then_exit_zero(context: dict) -> None:
    rc = context["cli_returncode"]
    assert rc == 0, (
        f"expected exit code 0; got {rc}; "
        f"stdout:\n{context.get('cli_stdout', '')}\n"
        f"stderr:\n{context.get('cli_stderr', '')}"
    )


@then("the exit code is non-zero")
def then_exit_nonzero(context: dict) -> None:
    rc = context["cli_returncode"]
    assert rc != 0, (
        f"expected non-zero exit; got {rc}; "
        f"stdout:\n{context.get('cli_stdout', '')}\n"
        f"stderr:\n{context.get('cli_stderr', '')}"
    )


@then("stderr is empty")
def then_stderr_empty(context: dict) -> None:
    stderr = context["cli_stderr"]
    assert stderr == "", f"expected empty stderr; got:\n{stderr}"


@then("stdout is empty")
def then_stdout_empty(context: dict) -> None:
    stdout = context["cli_stdout"]
    assert stdout == "", f"expected empty stdout; got:\n{stdout}"


# -----------------------------------------------------------------------
# Bootstrap scenario 1 — lead-shop layout
# -----------------------------------------------------------------------


@then(
    parsers.parse(
        'a "{shop_name}/" subdirectory exists under <dir> with empty '
        '"inbox/" and "outbox/" subdirectories'
    )
)
def then_shop_layout(shop_name: str, context: dict) -> None:
    target: Path = context["target"]
    # Strip trailing slash if the parser kept one.
    shop_name = shop_name.rstrip("/")
    shop = target / shop_name
    assert shop.is_dir(), f"expected {shop} to be a directory"
    inbox = shop / "inbox"
    outbox = shop / "outbox"
    assert inbox.is_dir(), f"expected {inbox} to be a directory"
    assert outbox.is_dir(), f"expected {outbox} to be a directory"
    assert not any(inbox.iterdir()), (
        f"expected {inbox} empty; found: {list(inbox.iterdir())}"
    )
    assert not any(outbox.iterdir()), (
        f"expected {outbox} empty; found: {list(outbox.iterdir())}"
    )


def _assert_beads_runs_cleanly(shop_dir: Path, expected_prefix: str) -> None:
    """Shared assertion: ``bd list`` succeeds in the shop and ``bd create``
    yields an issue id with the expected prefix.

    Lifted into a helper so both bootstrap Thens (lead and BC) can call
    it without duplicating the subprocess plumbing.
    """
    env = os.environ.copy()
    env["BD_NON_INTERACTIVE"] = "1"
    # ``bd list`` is the scenario's chosen liveness probe.
    list_proc = subprocess.run(
        ["bd", "list"],
        cwd=str(shop_dir),
        env=env,
        capture_output=True,
        text=True,
    )
    assert list_proc.returncode == 0, (
        f"expected `bd list` to exit 0 in {shop_dir}; "
        f"got {list_proc.returncode}; stderr:\n{list_proc.stderr}"
    )
    # ``bd create`` confirms the issue prefix actually matches the shop
    # name — the scenario explicitly pins this.
    create_proc = subprocess.run(
        ["bd", "create", "--title", "prefix-probe", "--type", "task", "--json"],
        cwd=str(shop_dir),
        env=env,
        capture_output=True,
        text=True,
    )
    assert create_proc.returncode == 0, (
        f"expected `bd create` to exit 0 in {shop_dir}; "
        f"got {create_proc.returncode}; stderr:\n{create_proc.stderr}"
    )
    import json
    issue = json.loads(create_proc.stdout)
    issue_id = issue.get("id", "")
    assert issue_id.startswith(f"{expected_prefix}-"), (
        f"expected issue id to start with {expected_prefix!r}-; got {issue_id!r}"
    )


@then(
    parsers.parse(
        'a "{shop_name}/.beads/" subdirectory exists with beads metadata '
        'sufficient for "bd list" to run cleanly (issue prefix matches the '
        'lead-shop name)'
    )
)
def then_lead_beads_ready(shop_name: str, context: dict) -> None:
    target: Path = context["target"]
    shop_name = shop_name.rstrip("/")
    shop = target / shop_name
    beads = shop / ".beads"
    assert beads.is_dir(), f"expected {beads} to be a directory"
    _assert_beads_runs_cleanly(shop, expected_prefix=context["lead_shop"])


@then(
    parsers.parse(
        'a "{shop_name}/.beads/" subdirectory exists with beads metadata '
        '(issue prefix matches the BC-shop name)'
    )
)
def then_bc_beads_ready(shop_name: str, context: dict) -> None:
    target: Path = context["target"]
    shop_name = shop_name.rstrip("/")
    shop = target / shop_name
    beads = shop / ".beads"
    assert beads.is_dir(), f"expected {beads} to be a directory"
    _assert_beads_runs_cleanly(shop, expected_prefix=context["bc_shop"])


# -----------------------------------------------------------------------
# Bootstrap scenario 2 — shop-msg send against the resulting BC shop
# -----------------------------------------------------------------------


@then(
    parsers.parse(
        '"shop-msg send request_maintenance --bc-root <dir>/bc-foo '
        "--work-id w-001 --description 'sanity check'\" succeeds and "
        'writes "<dir>/bc-foo/inbox/w-001.yaml"'
    )
)
def then_shop_msg_send_succeeds(context: dict) -> None:
    target: Path = context["target"]
    bc_root = target / "bc-foo"
    result = subprocess.run(
        [
            "shop-msg", "send", "request_maintenance",
            "--bc-root", str(bc_root),
            "--work-id", "w-001",
            "--description", "sanity check",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"expected shop-msg send to succeed; got {result.returncode}; "
        f"stderr:\n{result.stderr}"
    )
    inbox_file = bc_root / "inbox" / "w-001.yaml"
    assert inbox_file.is_file(), (
        f"expected {inbox_file} to exist after shop-msg send; "
        f"inbox now contains: {list((bc_root / 'inbox').iterdir())}"
    )


# -----------------------------------------------------------------------
# Freeze scenario — Givens
# -----------------------------------------------------------------------


@given(
    "an experiment target directory <dir> populated by a prior bootstrap "
    "(lead-shop + one BC-shop, with at least one inbox YAML and one outbox "
    "YAML present in the BC-shop's mailboxes)"
)
def given_populated_target(context: dict) -> None:
    """Bootstrap a topology in-test, then drop in placeholder YAML files
    in the BC's mailboxes so freeze has something to copy.

    Done as a real bootstrap (subprocess) rather than synthesized by hand
    so the freeze scenario also indirectly exercises the bootstrap
    capability — if bootstrap stops producing valid shop layouts, freeze
    fails too, which is the right coupling.
    """
    target: Path = context["target"]
    boot = subprocess.run(
        [
            "shop-test-harness", "bootstrap",
            "--target", str(target),
            "--lead-shop", "lead",
            "--bc-shop", "bc-foo",
        ],
        capture_output=True,
        text=True,
    )
    assert boot.returncode == 0, (
        f"prior bootstrap failed: rc={boot.returncode} stderr:\n{boot.stderr}"
    )
    inbox_file = target / "bc-foo" / "inbox" / "placeholder.yaml"
    outbox_file = target / "bc-foo" / "outbox" / "placeholder.yaml"
    inbox_file.write_text("message_type: placeholder\nwork_id: x\n")
    outbox_file.write_text("message_type: placeholder\nwork_id: x\n")
    context["lead_shop"] = "lead"
    context["bc_shop"] = "bc-foo"


@given("an evidence root directory <evidence>")
def given_evidence_root(context: dict) -> None:
    evidence = context["tmp_path"] / "evidence"
    evidence.mkdir()
    context["evidence"] = evidence


@when(
    parsers.parse(
        'I run "shop-test-harness freeze --target <dir> --evidence <evidence>"'
    )
)
def when_run_freeze(context: dict) -> None:
    target: Path = context["target"]
    evidence: Path = context["evidence"]
    result = subprocess.run(
        [
            "shop-test-harness", "freeze",
            "--target", str(target),
            "--evidence", str(evidence),
        ],
        capture_output=True,
        text=True,
    )
    context["cli_returncode"] = result.returncode
    context["cli_stdout"] = result.stdout
    context["cli_stderr"] = result.stderr


@then(
    parsers.parse(
        'a numbered subdirectory "<evidence>/runs/{n:d}/" exists '
        '(numbering is the next free integer)'
    )
)
def then_runs_n_exists(n: int, context: dict) -> None:
    evidence: Path = context["evidence"]
    expected = evidence / "runs" / str(n)
    assert expected.is_dir(), (
        f"expected {expected} to be a directory; runs/ now contains: "
        f"{list((evidence / 'runs').iterdir()) if (evidence / 'runs').is_dir() else 'no runs/'}"
    )
    context["run_dir"] = expected


def _files_under(root: Path) -> dict[str, bytes]:
    """Return {relpath -> bytes} for every regular file under ``root``.

    Symlinks are followed if they resolve to a file; otherwise skipped.
    This is the byte-for-byte comparison primitive used by the freeze
    Then.
    """
    out: dict[str, bytes] = {}
    for path in root.rglob("*"):
        if path.is_file():
            rel = path.relative_to(root).as_posix()
            out[rel] = path.read_bytes()
    return out


@then(
    parsers.parse(
        'every file under "<dir>/{lead_shop}/" and "<dir>/{bc_shop}/" is '
        'present under the corresponding path inside "<evidence>/runs/{n:d}/", '
        'byte-for-byte'
    )
)
def then_every_file_present(
    lead_shop: str, bc_shop: str, n: int, context: dict
) -> None:
    target: Path = context["target"]
    evidence: Path = context["evidence"]
    run_dir = evidence / "runs" / str(n)
    for shop_name in (lead_shop, bc_shop):
        src = target / shop_name
        dst = run_dir / shop_name
        assert dst.is_dir(), f"expected snapshot dir {dst} to exist"
        src_files = _files_under(src)
        dst_files = _files_under(dst)
        # A missing file is more diagnostic than a generic dict-equality
        # failure, so check membership + content explicitly.
        missing = set(src_files) - set(dst_files)
        assert not missing, (
            f"files missing from snapshot of {shop_name}/: {sorted(missing)}"
        )
        for rel, body in src_files.items():
            assert dst_files[rel] == body, (
                f"byte mismatch in snapshot of {shop_name}/{rel}"
            )


@then(
    "the evidence directory is a complete, self-contained copy of the "
    "topology at the moment freeze was called"
)
def then_evidence_self_contained(context: dict) -> None:
    """Sanity: deleting the source target leaves the evidence intact and
    still readable. This pins "self-contained" rather than "happens to
    share inodes" — i.e. it would fail if freeze used hardlinks or
    symlinks back to the source.
    """
    target: Path = context["target"]
    run_dir: Path = context["run_dir"]
    # Snapshot what's there first.
    before = _files_under(run_dir)
    # Now destroy the source.
    shutil.rmtree(target)
    after = _files_under(run_dir)
    assert before == after, (
        "evidence is not self-contained: deleting the source changed "
        "its contents"
    )


# -----------------------------------------------------------------------
# Verify scenarios — Givens
# -----------------------------------------------------------------------


def _write_work_done(
    target: Path, bc: str, work_id: str, hashes: list[str]
) -> Path:
    """Drop a valid ``<work-id>-work_done.yaml`` into the BC's outbox.

    We use ``shop-msg respond work_done`` so the file shape exactly
    matches what a real BC would write — going through the CLI is
    cheaper than synthesizing the YAML by hand and lying about its
    provenance.
    """
    bc_root = target / bc
    (bc_root / "inbox").mkdir(parents=True, exist_ok=True)
    (bc_root / "outbox").mkdir(parents=True, exist_ok=True)
    cmd = [
        "shop-msg", "respond", "work_done",
        "--bc-root", str(bc_root),
        "--work-id", work_id,
        "--status", "complete",
    ]
    for h in hashes:
        cmd.extend(["--scenario-hash", h])
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0, (
        f"setup: shop-msg respond work_done failed: {result.stderr}"
    )
    return bc_root / "outbox" / f"{work_id}-work_done.yaml"


@given(
    parsers.re(
        r'an experiment target directory <dir> with a BC-shop whose outbox '
        r'contains a valid "<work-id>-work_done\.yaml" carrying '
        r'scenario_hashes \[(?P<h1>[^,\]]+), (?P<h2>[^,\]]+), (?P<h3>[^,\]]+)\]'
    )
)
def given_workdone_three_hashes(
    h1: str, h2: str, h3: str, context: dict
) -> None:
    target: Path = context["target"]
    work_id = "wd-001"
    _write_work_done(target, "bc-foo", work_id, [h1, h2, h3])
    context["bc_shop"] = "bc-foo"
    context["work_id"] = work_id
    context["echoed_hashes"] = [h1, h2, h3]


@given(
    parsers.re(
        r'an experiment target directory <dir> with a BC-shop whose outbox '
        r'contains a valid "<work-id>-work_done\.yaml" carrying '
        r'scenario_hashes \[(?P<h1>[^,\]]+), (?P<h2>[^,\]]+)\]'
    )
)
def given_workdone_two_hashes(h1: str, h2: str, context: dict) -> None:
    target: Path = context["target"]
    work_id = "wd-002"
    _write_work_done(target, "bc-foo", work_id, [h1, h2])
    context["bc_shop"] = "bc-foo"
    context["work_id"] = work_id
    context["echoed_hashes"] = [h1, h2]
    context["divergent_H1"] = h1
    context["divergent_H2"] = h2


@given(
    parsers.parse(
        'an "expected hashes" file at path <expected> listing the same three '
        'hashes, one per line, in any order'
    )
)
def given_expected_three_matching(context: dict) -> None:
    expected = context["tmp_path"] / "expected.txt"
    # Deliberately reorder relative to ``echoed_hashes`` so the scenario's
    # "in any order" clause is actually exercised.
    hashes = list(reversed(context["echoed_hashes"]))
    expected.write_text("\n".join(hashes) + "\n")
    context["expected_path"] = expected


@given(
    parsers.re(
        r'an "expected hashes" file at path <expected> listing '
        r'\[(?P<h1>[^,\]]+), (?P<h3>[^,\]]+)\] '
        r'\(H1 in common, H2 unexpected, H3 missing\)'
    )
)
def given_expected_divergent(h1: str, h3: str, context: dict) -> None:
    # The Given names H1 and H3 by reference to the BC-shop's prior
    # [H1, H2]: H1 is common, H2 is the BC's extra, H3 is what was
    # expected but missing. Stash them for the Then to reference.
    expected = context["tmp_path"] / "expected.txt"
    expected.write_text(f"{h1}\n{h3}\n")
    context["expected_path"] = expected
    context["divergent_H3"] = h3


@when(
    parsers.parse(
        'I run "shop-test-harness verify --target <dir> --bc {bc} '
        '--work-id <work-id> --expected <expected>"'
    )
)
def when_run_verify(bc: str, context: dict) -> None:
    target: Path = context["target"]
    expected: Path = context["expected_path"]
    work_id: str = context["work_id"]
    result = subprocess.run(
        [
            "shop-test-harness", "verify",
            "--target", str(target),
            "--bc", bc,
            "--work-id", work_id,
            "--expected", str(expected),
        ],
        capture_output=True,
        text=True,
    )
    context["cli_returncode"] = result.returncode
    context["cli_stdout"] = result.stdout
    context["cli_stderr"] = result.stderr


@then(parsers.parse('stdout reports "verify: {n:d} hashes match"'))
def then_stdout_reports_n_match(n: int, context: dict) -> None:
    stdout = context["cli_stdout"]
    expected = f"verify: {n} hashes match"
    assert expected in stdout, (
        f"expected stdout to contain {expected!r}; got:\n{stdout!r}"
    )


@then(
    "stderr names H3 as a hash that was expected but not echoed back "
    "(forward-conformance gap)"
)
def then_stderr_names_h3_forward(context: dict) -> None:
    stderr = context["cli_stderr"]
    h3 = context["divergent_H3"]
    assert h3 in stderr, (
        f"expected stderr to mention H3={h3!r}; got:\n{stderr}"
    )
    assert "forward-conformance" in stderr, (
        f"expected stderr to mention 'forward-conformance'; got:\n{stderr}"
    )


@then(
    "stderr names H2 as a hash that was echoed back but not assigned "
    "(reverse-conformance gap)"
)
def then_stderr_names_h2_reverse(context: dict) -> None:
    stderr = context["cli_stderr"]
    h2 = context["divergent_H2"]
    assert h2 in stderr, (
        f"expected stderr to mention H2={h2!r}; got:\n{stderr}"
    )
    assert "reverse-conformance" in stderr, (
        f"expected stderr to mention 'reverse-conformance'; got:\n{stderr}"
    )
