"""The SubagentStop seal: `seal_baseline.py` at dispatch, `seal_check.py` at stop.

Backlog item 141: the baseline hook rewrote its snapshot on every dispatch, so
with two subagents in flight the second dispatch cleared the first -- anything
the first agent wrote to a sealed file was already inside the new snapshot and
the check cleared it. A false negative, and a silent one.
`P1f-worktree-guards` made the snapshot happen when the in-flight count goes
0 -> 1 and only increment after that, with `seal_check.py` decrementing before
any comparison can exit.

Two things this file deliberately does NOT do
---------------------------------------------
1. **It does not depend on the harness delivering a payload.** Backlog item 143,
   measured three ways and reproducing at `HEAD`: neither seal hook is invoked
   by this harness. Every payload below is constructed here, by hand.
2. **It does not assert that the hooks never run.** That would lock item 143 in
   as correct behaviour and turn red the day it is fixed. The `P14g` and `P1e`
   testers each refused that trap for their own units; this file refuses it too.
   Nothing here reads `.agent/.seal-baseline.json` in the repository, and
   nothing here is sensitive to whether the harness ever starts these hooks.

Where every expected value in this file comes from
--------------------------------------------------
* **sha256 of bytes this test wrote**, computed here with `hashlib`. The hooks'
  own docstrings state the formula -- for the hooks directory, "sha256 over the
  sorted (name, bytes) pairs of every .py and .sh" -- and `HOOKS_SHA` below is
  that formula written out independently. A `tree_digest` that stopped hashing
  the file name would fail it.
* **Hand arithmetic on a counter.** 0 -> 1 -> 2, then 2 -> 1 -> 0, and
  `max(0, 0 - 1) = 0`. Every count asserted below is reached by adding or
  subtracting one, written out in the test.
* **The documented constant** `STALE_AFTER_HOURS = 12`, so 11 hours is inside
  the window and 13 is outside.
* **Python's own rule that `True` is an `int`**, which is why `as_count` has to
  reject it and why a bool must count as 0 and not as 1.

No value here was read off a run.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from tests.unit._hook_harness import (
    COMMIT_IDENTITY,
    SEAL_BASELINE,
    SEAL_CHECK,
    HookRun,
    drive_main,
    git,
    load_hook,
    run_hook,
)

# --- the sealed files, and their digests computed by hand -------------------

INDEX_BYTES = b"INDEX, as the orchestrator wrote it\n"
STATUS_BYTES = b"STATUS, as the orchestrator measured it\n"
HOOK_NAME = "probe_hook.py"
HOOK_BYTES = b"print('probe')\n"

INDEX_SHA = hashlib.sha256(INDEX_BYTES).hexdigest()
STATUS_SHA = hashlib.sha256(STATUS_BYTES).hexdigest()

# `tree_digest`'s formula, from the docstring both hooks carry, written out
# here rather than imported: sha256 over the sorted (name, bytes) pairs of
# every .py and .sh in the directory, name first.
_TREE = hashlib.sha256()
_TREE.update(HOOK_NAME.encode("utf-8"))
_TREE.update(HOOK_BYTES)
HOOKS_SHA = _TREE.hexdigest()

BASELINE_REL = Path(".agent") / ".seal-baseline.json"


@pytest.fixture(scope="session")
def seal_baseline() -> ModuleType:
    return load_hook(SEAL_BASELINE)


@pytest.fixture(scope="session")
def seal_check() -> ModuleType:
    return load_hook(SEAL_CHECK)


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A project laid out like this one, holding the three sealed things.

    Outside the repository, built from nothing, one per test.
    """
    root = tmp_path / "sealed_project"
    (root / ".agent" / "journal").mkdir(parents=True)
    (root / ".claude" / "hooks").mkdir(parents=True)
    (root / ".agent" / "journal" / "INDEX.md").write_bytes(INDEX_BYTES)
    (root / "STATUS.md").write_bytes(STATUS_BYTES)
    (root / ".claude" / "hooks" / HOOK_NAME).write_bytes(HOOK_BYTES)
    return root


def baseline_path(project: Path) -> Path:
    return project / BASELINE_REL


def state(project: Path) -> dict[str, Any]:
    return json.loads(baseline_path(project).read_text())


#: `tool=OMIT_TOOL_NAME` builds a payload with no `tool_name` key at all. That
#: shape is not hypothetical politeness: it is the one that let a subagent
#: through until 2026-10-08, and a default of `""` would have hidden it.
OMIT_TOOL_NAME = object()


def dispatch(
    seal_baseline: ModuleType, project: Path, *, session: str = "s1",
    tool: object = "Agent", agent_type: str = "",
) -> HookRun:
    """One PreToolUse dispatch payload, constructed here."""
    payload: dict[str, Any] = {
        "session_id": session,
        "agent_type": agent_type,
        "cwd": str(project),
        "hook_event_name": "PreToolUse",
        "tool_input": {},
    }
    if tool is not OMIT_TOOL_NAME:
        payload["tool_name"] = tool
    return drive_main(seal_baseline, payload, project)


def stop(
    seal_check: ModuleType, project: Path, *, session: str = "s1", role: str = "tester"
) -> HookRun:
    """One SubagentStop payload, constructed here."""
    return drive_main(
        seal_check,
        {
            "session_id": session,
            "agent_type": role,
            "cwd": str(project),
            "hook_event_name": "SubagentStop",
        },
        project,
    )


def write_baseline(project: Path, content: bytes) -> None:
    baseline_path(project).parent.mkdir(parents=True, exist_ok=True)
    baseline_path(project).write_bytes(content)


def iso(hours_ago: float) -> str:
    return (datetime.now(UTC) - timedelta(hours=hours_ago)).isoformat()


def snapshot_json(**overrides: Any) -> bytes:
    """A well-formed baseline, with the digests of the untouched sealed files."""
    body: dict[str, Any] = {
        "index_sha256": INDEX_SHA,
        "status_sha256": STATUS_SHA,
        "hooks_sha256": HOOKS_SHA,
        "taken_at": iso(0),
        "tool": "Agent",
        "session_id": "s1",
        "in_flight": 1,
    }
    body.update(overrides)
    return json.dumps(body).encode("utf-8")


# --- criterion 7: the counting ----------------------------------------------


def test_the_first_dispatch_of_a_window_takes_the_snapshot(seal_baseline, project: Path) -> None:
    """0 -> 1. The count starts at nothing, so the first dispatch snapshots.

    The three digests are sha256 of bytes this test wrote, computed above.
    """
    run = dispatch(seal_baseline, project)
    assert run.returncode == 0
    saved = state(project)
    assert saved["in_flight"] == 1
    assert saved["index_sha256"] == INDEX_SHA
    assert saved["status_sha256"] == STATUS_SHA
    assert saved["hooks_sha256"] == HOOKS_SHA
    assert saved["session_id"] == "s1"


def test_a_second_dispatch_increments_and_does_not_retake_the_snapshot(
    seal_baseline, project: Path
) -> None:
    """Backlog item 141, stated as the property that was broken.

    Agent A is dispatched and changes `INDEX.md`. Agent B is then dispatched.
    If B's dispatch retook the snapshot, A's change would be inside it and A
    would be cleared. So the snapshot must still hold the sha256 of the ORIGINAL
    bytes, which this test computed before anything ran.
    """
    dispatch(seal_baseline, project)
    (project / ".agent" / "journal" / "INDEX.md").write_bytes(b"A wrote this\n")

    dispatch(seal_baseline, project)
    saved = state(project)
    assert saved["in_flight"] == 2                  # 1 + 1, by hand
    assert saved["index_sha256"] == INDEX_SHA       # the pre-window digest, kept


def test_each_stop_decrements_by_one(seal_baseline, seal_check, project: Path) -> None:
    dispatch(seal_baseline, project)
    dispatch(seal_baseline, project)
    assert state(project)["in_flight"] == 2

    assert stop(seal_check, project).returncode == 0
    assert state(project)["in_flight"] == 1         # 2 - 1
    assert stop(seal_check, project).returncode == 0
    assert state(project)["in_flight"] == 0         # 1 - 1


def test_the_count_cannot_go_below_zero(seal_check, project: Path) -> None:
    """`max(0, 0 - 1) = 0`. A stop with nothing in flight -- which item 143
    makes the normal case today -- must not drive the count negative, because a
    negative count would make the next `<= 0` test fire a snapshot that was
    already taken."""
    write_baseline(project, snapshot_json(in_flight=0))
    assert stop(seal_check, project).returncode == 0
    assert state(project)["in_flight"] == 0


def test_a_stop_fires_when_a_sealed_file_changed_and_still_decrements(
    seal_baseline, seal_check, project: Path
) -> None:
    """The seal's whole purpose, and the ordering that keeps the count honest.

    A firing exits 2. If the write-back sat after that exit, every firing would
    leave the count one too high for ever, so the decrement has to happen first.
    """
    dispatch(seal_baseline, project)
    (project / "STATUS.md").write_bytes(b"a subagent wrote this\n")

    run = stop(seal_check, project)
    assert run.returncode == 2
    assert "STATUS.md" in run.stderr
    assert state(project)["in_flight"] == 0         # 1 - 1, written before the exit


def test_the_first_of_two_agents_is_no_longer_cleared_by_the_second_dispatch(
    seal_baseline, seal_check, project: Path
) -> None:
    """Item 141 end to end: both agents in a concurrent window are judged
    against the state from before the window opened."""
    dispatch(seal_baseline, project)                                  # A
    (project / ".agent" / "journal" / "INDEX.md").write_bytes(b"A wrote this\n")
    dispatch(seal_baseline, project)                                  # B

    first = stop(seal_check, project)                                 # A stops
    assert first.returncode == 2
    assert "INDEX.md" in first.stderr
    assert state(project)["in_flight"] == 1                           # 2 - 1

    second = stop(seal_check, project)                                # B stops
    assert second.returncode == 2
    assert state(project)["in_flight"] == 0                           # 1 - 1


def test_a_stop_clears_a_run_that_changed_nothing(
    seal_baseline, seal_check, project: Path
) -> None:
    """The control. A seal that fired on every run would be no seal at all."""
    dispatch(seal_baseline, project)
    run = stop(seal_check, project)
    assert run.returncode == 0
    assert run.stderr == ""
    assert state(project)["in_flight"] == 0


@pytest.mark.parametrize(
    ("label", "change"),
    [
        ("index_changed", ".agent/journal/INDEX.md"),
        ("status_changed", "STATUS.md"),
        ("a_hook_changed", f".claude/hooks/{HOOK_NAME}"),
    ],
)
def test_each_of_the_three_sealed_things_fires_on_its_own(
    label: str, change: str, seal_baseline, seal_check, project: Path
) -> None:
    dispatch(seal_baseline, project)
    (project / change).write_bytes(b"different bytes\n")
    run = stop(seal_check, project)
    assert run.returncode == 2, label


def test_a_new_hook_file_fires_the_seal(seal_baseline, seal_check, project: Path) -> None:
    """The hooks digest covers the directory, not one file: adding a hook is a
    change to the set of permissions that bind the agent."""
    dispatch(seal_baseline, project)
    (project / ".claude" / "hooks" / "sneaky.py").write_bytes(b"pass\n")
    assert stop(seal_check, project).returncode == 2


def test_deleting_a_sealed_file_fires_the_seal(
    seal_baseline, seal_check, project: Path
) -> None:
    """`digest` returns None for a file that is not there, and None is not the
    sha256 the snapshot holds."""
    dispatch(seal_baseline, project)
    (project / "STATUS.md").unlink()
    run = stop(seal_check, project)
    assert run.returncode == 2
    assert "STATUS.md" in run.stderr


def test_a_change_made_and_undone_is_not_a_change(
    seal_baseline, seal_check, project: Path
) -> None:
    """Stated in the hook's docstring: "The baseline is a hash, not a copy. A
    subagent that changes a file and changes it back has changed nothing, and
    that is the right answer." """
    dispatch(seal_baseline, project)
    (project / "STATUS.md").write_bytes(b"temporarily different\n")
    (project / "STATUS.md").write_bytes(STATUS_BYTES)
    assert stop(seal_check, project).returncode == 0


# --- the window: session_id and the 12-hour backstop ------------------------


def test_a_new_session_refreshes_a_stranded_count(seal_baseline, project: Path) -> None:
    """An agent killed mid-run never fires SubagentStop, so the count strands.
    A new `session_id` is the exact signal that the old window is gone."""
    write_baseline(project, snapshot_json(in_flight=2, session_id="s1"))
    dispatch(seal_baseline, project, session="s2")
    assert state(project)["in_flight"] == 1         # a fresh window, not 2 + 1


def test_a_snapshot_older_than_the_window_is_refreshed(seal_baseline, project: Path) -> None:
    """`STALE_AFTER_HOURS = 12`, so 13 hours is outside it."""
    write_baseline(project, snapshot_json(in_flight=2, taken_at=iso(13)))
    dispatch(seal_baseline, project)
    assert state(project)["in_flight"] == 1


def test_a_snapshot_inside_the_window_is_not_refreshed(seal_baseline, project: Path) -> None:
    """...and 11 hours is inside it, so the window survives and the count grows."""
    write_baseline(project, snapshot_json(in_flight=2, taken_at=iso(11)))
    dispatch(seal_baseline, project)
    assert state(project)["in_flight"] == 3         # 2 + 1


@pytest.mark.parametrize(
    ("taken_at", "expected"),
    [
        (None, True),                       # missing
        (12345, True),                      # not text
        ("not a timestamp", True),          # unparseable
        ("2026-10-08T12:00:00", True),      # parseable but naive: no zone, no answer
    ],
)
def test_is_stale_is_true_for_anything_it_cannot_read(
    seal_baseline, taken_at: object, expected: bool
) -> None:
    assert seal_baseline.is_stale(taken_at) is expected


def test_is_stale_reads_the_window_from_the_constant(seal_baseline) -> None:
    hours = seal_baseline.STALE_AFTER_HOURS
    assert seal_baseline.is_stale(iso(hours - 1)) is False
    assert seal_baseline.is_stale(iso(hours + 1)) is True


# --- criterion 10: `as_count` rejects `bool` --------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0, 0),
        (1, 1),
        (7, 7),
        (-3, -3),
        (True, 0),          # `True` is an `int` in Python and would count as 1
        (False, 0),
        ("abc", 0),
        ("3", 0),
        (None, 0),
        (2.0, 0),
        ([1], 0),
        ({"in_flight": 1}, 0),
    ],
)
def test_as_count_returns_a_count_or_zero(seal_baseline, value: object, expected: int) -> None:
    assert seal_baseline.as_count(value) == expected


def test_as_count_rejects_bool_where_int_would_have_accepted_it(
    seal_baseline, project: Path
) -> None:
    """`int(True)` is 1. If `in_flight` were read that way, a baseline holding
    `true` would look like one agent already in flight, the window would be
    treated as open, and the dispatch would increment to 2 instead of taking the
    fresh snapshot a corrupt field must produce.
    """
    write_baseline(project, snapshot_json(in_flight=True))
    dispatch(seal_baseline, project)
    assert state(project)["in_flight"] == 1


# --- criterion 8: the corrupt shapes ----------------------------------------

#: (label, bytes on disk, must the loss be recorded as `window_lost_at`?)
#:
#: `read_or_unreadable` reports "unreadable" only when the file is there and
#: cannot be read or parsed **as an object**. `{"in_flight": "abc"}` is a
#: perfectly readable object with a field that is not a count, so it is not a
#: lost window -- it is a fresh one. A list and an empty file are not objects.
CORRUPT = [
    ("in_flight is a string", b'{"in_flight": "abc"}', False),
    ("in_flight is true", b'{"in_flight": true}', False),
    ("in_flight is null", b'{"in_flight": null}', False),
    ("the file is not JSON", b"{ this is not json at all", True),
    ("the file is a JSON list", b"[1, 2, 3]", True),
    ("the file is empty", b"", True),
]


@pytest.mark.parametrize(("label", "content", "lost"), CORRUPT)
def test_a_corrupt_baseline_stops_neither_hook_and_heals(
    label: str, content: bytes, lost: bool, seal_baseline, seal_check, project: Path
) -> None:
    """Six shapes, and the whole of criterion 8 for each.

    The round 1 reviewer measured the cost of getting this wrong: a baseline
    holding `"abc"` crashed BOTH hooks at exit 1, so `SubagentStop` performed no
    comparison at all and said nothing. **A hook that crashes is a guard that is
    off.**

    Exit 0 on a corrupt field is NOT asserted here as a desirable fallback on
    its own -- that would be locking in a silence. It is asserted together with
    the two things that make it a repair rather than a hole: the count comes
    back to 0, and the very next stop still fires on a real change.
    """
    write_baseline(project, content)
    assert stop(seal_check, project).returncode == 0          # does not crash

    write_baseline(project, content)
    run = dispatch(seal_baseline, project)
    assert run.returncode == 0                                # does not crash
    saved = state(project)
    assert saved["in_flight"] == 1                            # a fresh window
    assert saved["index_sha256"] == INDEX_SHA                 # with digests
    assert saved["status_sha256"] == STATUS_SHA
    assert saved["hooks_sha256"] == HOOKS_SHA
    assert ("window_lost_at" in saved) is lost

    (project / "STATUS.md").write_bytes(b"a subagent wrote this\n")
    fired = stop(seal_check, project)
    assert fired.returncode == 2                              # the seal is back on
    assert "STATUS.md" in fired.stderr
    assert state(project)["in_flight"] == 0                   # 1 - 1


@pytest.mark.parametrize(("label", "content", "lost"), CORRUPT[:2] + CORRUPT[3:4])
def test_a_corrupt_baseline_stops_neither_hook_as_a_subprocess_either(
    label: str, content: bytes, lost: bool, project: Path
) -> None:
    """The same claim, taken the way the harness runs the hooks. `main()` called
    in this process would turn an uncaught `ValueError` into a test error; a
    subprocess turns it into exit 1, which is what the reviewer measured."""
    payload = {"session_id": "s1", "tool_name": "Agent", "agent_type": "",
               "cwd": str(project), "hook_event_name": "PreToolUse", "tool_input": {}}
    stop_payload = {"session_id": "s1", "agent_type": "tester",
                    "cwd": str(project), "hook_event_name": "SubagentStop"}

    write_baseline(project, content)
    assert run_hook(SEAL_CHECK, stop_payload, project).returncode == 0, label
    write_baseline(project, content)
    assert run_hook(SEAL_BASELINE, payload, project).returncode == 0, label
    assert state(project)["in_flight"] == 1


# --- criterion 9: `window_lost_at`, and the no-digest state that is worse ---


def test_an_unreadable_baseline_is_replaced_by_a_snapshot_that_still_has_digests(
    seal_baseline, seal_check, project: Path
) -> None:
    """The test that would have caught the first fix for G4.

    That fix wrote a state with **no digests**. `seal_check.py` skips a
    comparison whose key is absent (`if key not in baseline: continue`), so all
    three comparisons were skipped -- silently, permanently, no check at all,
    where the defect being fixed was one restarted window.

    The assertions that separate the two are the last two: a replacement
    snapshot that holds no digests passes every `in_flight` assertion above and
    then lets a changed `STATUS.md` through at exit 0.
    """
    write_baseline(project, b"{ not json, the file was locked mid-write")
    dispatch(seal_baseline, project)
    saved = state(project)

    for key, expected in (
        ("index_sha256", INDEX_SHA),
        ("status_sha256", STATUS_SHA),
        ("hooks_sha256", HOOKS_SHA),
    ):
        assert key in saved, f"{key} is missing, so seal_check will skip it in silence"
        assert saved[key] == expected

    # ...and the loss is on the record rather than silent.
    lost_at = saved["window_lost_at"]
    assert isinstance(lost_at, str)
    assert datetime.fromisoformat(lost_at).tzinfo is not None

    # The decisive one. With a no-digest state this exits 0 and says nothing.
    (project / "STATUS.md").write_bytes(b"a subagent wrote this\n")
    fired = stop(seal_check, project)
    assert fired.returncode == 2
    assert "STATUS.md" in fired.stderr


def test_a_baseline_that_cannot_be_written_does_not_stop_the_dispatch(
    seal_baseline, project: Path
) -> None:
    """"A failure here is silent on purpose: the seal is a tripwire, and a hook
    that stopped a dispatch because a file was locked would be worse than one
    that misses a check."

    A directory where the file should be makes every read and write of it fail
    with `OSError`, which is the lock the comment is about, reproduced without
    needing one. The dispatch must still exit 0.
    """
    baseline_path(project).parent.mkdir(parents=True, exist_ok=True)
    baseline_path(project).mkdir()
    assert dispatch(seal_baseline, project).returncode == 0
    assert baseline_path(project).is_dir()      # nothing was written over it


def test_an_absent_baseline_is_not_a_lost_window(seal_baseline, project: Path) -> None:
    """"No window is open, start one" and "a window may be open and I cannot see
    it" are different answers, and only the second is a loss. A `window_lost_at`
    on every first dispatch would make the field mean nothing."""
    assert not baseline_path(project).exists()
    dispatch(seal_baseline, project)
    assert "window_lost_at" not in state(project)


# --- no route a subagent has may refresh the measurement taken of it --------
#
# These five tests were `tests/unit/test_seal_baseline_rule3_red.py` on
# 2026-10-08: red on purpose, stating a requirement the hook did not meet. The
# role check read `tool_name == "SendMessage"` and let a payload carrying a
# role through on every other tool shape, including when `tool_name` was
# absent. Measured then, in a scratch copy:
#
#   tool_name=SendMessage, agent_type=tester   in_flight 1 -> 1   REFUSED
#   tool_name ABSENT,      agent_type=tester   in_flight 1 -> 2   let through
#   tool_name=Agent,       agent_type=tester   in_flight 1 -> 2   let through
#   ...and the snapshot was retaken over a STATUS.md the subagent had changed.
#
# The orchestrator removed the narrowing the same day, so the check now reads
# the role and nothing else, and these went green. **They are moved here in the
# same unit, out of the `*_rule3_red.py` pattern the gate excludes**, because a
# green test left inside that pattern is a test the gate never runs -- the
# defect at `38b903c`, backlog item 24.
#
# The expected values are unchanged by the move: 1 stays 1 is hand arithmetic,
# and "the snapshot must not hold the bytes the subagent wrote" is sha256 of
# bytes this file wrote, computed at the top.

SUBAGENT_ROUTES = [
    ("SendMessage", "the one tool a subagent can call"),
    (OMIT_TOOL_NAME, "no tool_name at all -- the shape that used to be let through"),
    ("Agent", "disallowed for the three roles, so it should never arrive"),
    ("Task", "likewise"),
]


@pytest.mark.parametrize(("tool", "why"), SUBAGENT_ROUTES)
def test_a_subagent_cannot_extend_the_window_by_any_route(
    tool: object, why: str, seal_baseline, project: Path
) -> None:
    """The role decides this, and the tool name does not.

    A payload carrying a subagent's role must leave the count and the snapshot
    alone whatever tool it names, including when it names none. 1 stays 1.
    """
    write_baseline(project, snapshot_json(in_flight=1))
    before = state(project)["taken_at"]

    run = dispatch(seal_baseline, project, tool=tool, agent_type="tester")
    assert run.returncode == 0
    after = state(project)
    assert after["in_flight"] == 1, why     # not 1 + 1
    assert after["taken_at"] == before      # not retaken


def test_a_subagent_cannot_have_the_snapshot_retaken_over_its_own_write(
    seal_baseline, project: Path
) -> None:
    """The sharp one, and the reason the count alone is not enough.

    Between units `in_flight` is 0, so any dispatch that gets past the role
    check takes a FRESH snapshot. A subagent that reaches this hook after
    writing to `STATUS.md` would therefore have its own bytes hashed into the
    baseline, and `seal_check.py` would clear it at `SubagentStop`. The
    expected value is sha256 of the original bytes, computed at the top of this
    file before anything ran.
    """
    write_baseline(project, snapshot_json(in_flight=0))
    (project / "STATUS.md").write_bytes(b"a subagent wrote this\n")
    tampered = hashlib.sha256(b"a subagent wrote this\n").hexdigest()

    dispatch(seal_baseline, project, tool=OMIT_TOOL_NAME, agent_type="tester")
    after = state(project)
    assert after["status_sha256"] != tampered, (
        "the snapshot holds the bytes the subagent wrote, so the seal will "
        "clear it at SubagentStop"
    )
    assert after["status_sha256"] == STATUS_SHA


ORCHESTRATOR_ROUTES = [
    ("Agent", "the ordinary dispatch"),
    ("Task", "the other ordinary dispatch"),
    ("SendMessage", "resuming an agent, which skips the Agent matcher"),
    (OMIT_TOOL_NAME, "a payload with no tool_name and no role"),
]


@pytest.mark.parametrize(("tool", "why"), ORCHESTRATOR_ROUTES)
def test_the_orchestrator_is_still_counted_on_every_route(
    tool: object, why: str, seal_baseline, project: Path
) -> None:
    """The control, and without it a hook that refused EVERY payload would pass
    every test above.

    The check is on the role, so a payload that carries no role is the
    orchestrator dispatching and must be counted. An orchestrator dropped here
    would leave the seal comparing against a stale snapshot and blaming the next
    agent for every orchestrator write since.
    """
    write_baseline(project, snapshot_json(in_flight=1))
    dispatch(seal_baseline, project, tool=tool, agent_type="")
    assert state(project)["in_flight"] == 2, why    # 1 + 1


@pytest.mark.parametrize("role", ["programmer", "code-reviewer", "tester"])
def test_the_refusal_covers_all_three_roles(role: str, seal_baseline, project: Path) -> None:
    """`ROLES` is the same three names the write guard binds. A check that
    happened to name only one of them would pass every test above."""
    write_baseline(project, snapshot_json(in_flight=1))
    dispatch(seal_baseline, project, tool=OMIT_TOOL_NAME, agent_type=role)
    assert state(project)["in_flight"] == 1


def test_the_refusal_still_records_that_the_hook_ran(
    seal_baseline, project: Path
) -> None:
    """The instrument is written BEFORE the role check, and it has to be: it is
    the only way to tell "the hook ran and exited early" from "the hook never
    ran", which is the question backlog item 143 turns on. A refusal must not
    erase it."""
    write_baseline(project, snapshot_json(in_flight=1))
    dispatch(seal_baseline, project, tool=OMIT_TOOL_NAME, agent_type="tester")
    seen = state(project)["last_dispatch_seen"]
    assert seen["agent_type"] == "tester"
    assert seen["tool_name"] == ""


# --- the fallback when there is no snapshot, which must still fire ----------


@pytest.fixture
def git_project(project: Path) -> Path:
    git(["init", "-b", "main"], project)
    git(["add", "-A"], project)
    git([*COMMIT_IDENTITY, "commit", "-m", "sealed"], project)
    return project


def test_with_no_snapshot_the_seal_falls_back_to_head_and_still_fires(
    seal_check, git_project: Path
) -> None:
    """A missing snapshot is the blunter, older behaviour -- and the thing that
    matters about it is that it is blunter, not that it is quieter. It must
    still catch a real change."""
    assert not baseline_path(git_project).exists()
    (git_project / "STATUS.md").write_bytes(b"a subagent wrote this\n")

    run = stop(seal_check, git_project)
    assert run.returncode == 2
    assert "STATUS.md" in run.stderr


def test_with_no_snapshot_a_clean_tree_is_cleared(seal_check, git_project: Path) -> None:
    assert stop(seal_check, git_project).returncode == 0


def test_dirty_against_head_names_the_file_it_found(seal_check, git_project: Path) -> None:
    """`git status --porcelain -- <path>` prints one line per changed path. The
    expected shape is git's own documented porcelain v1 format: two status
    characters, a space, then the path."""
    (git_project / "STATUS.md").write_bytes(b"changed\n")
    lines = seal_check.dirty_against_head(str(git_project), "STATUS.md")
    assert len(lines) == 1
    assert lines[0].endswith("STATUS.md")
    assert seal_check.dirty_against_head(str(git_project), "AGENTS.md") == []


# --- the two digest helpers, against hand-computed values -------------------


def test_digest_is_sha256_of_the_bytes(seal_baseline, seal_check, project: Path) -> None:
    target = project / "STATUS.md"
    assert seal_baseline.digest(target) == STATUS_SHA
    assert seal_check.digest(target) == STATUS_SHA


def test_digest_of_a_file_that_is_not_there_is_none(seal_baseline, project: Path) -> None:
    assert seal_baseline.digest(project / "no_such_file.md") is None


def test_tree_digest_hashes_the_name_alongside_the_bytes(
    seal_baseline, seal_check, project: Path
) -> None:
    """Both hooks must compute this identically or the seal fires on every run.
    `HOOKS_SHA` is the formula written out in this file, from the docstring."""
    hooks = project / ".claude" / "hooks"
    assert seal_baseline.tree_digest(hooks) == HOOKS_SHA
    assert seal_check.tree_digest(hooks) == HOOKS_SHA


def test_tree_digest_changes_when_a_file_is_renamed(seal_baseline, project: Path) -> None:
    """"the name is hashed alongside the bytes so a rename is a change". A
    digest over the bytes alone would be identical after this move."""
    hooks = project / ".claude" / "hooks"
    (hooks / HOOK_NAME).rename(hooks / "renamed_hook.py")

    renamed = hashlib.sha256()
    renamed.update(b"renamed_hook.py")
    renamed.update(HOOK_BYTES)
    assert seal_baseline.tree_digest(hooks) == renamed.hexdigest()
    assert seal_baseline.tree_digest(hooks) != HOOKS_SHA


def test_tree_digest_of_an_empty_directory_is_none(seal_baseline, tmp_path: Path) -> None:
    empty = tmp_path / "no_hooks"
    empty.mkdir()
    assert seal_baseline.tree_digest(empty) is None


# --- read_or_unreadable: absent is not unreadable ---------------------------


def test_read_or_unreadable_tells_absent_from_corrupt(seal_baseline, tmp_path: Path) -> None:
    """The G4 distinction, at the function. `None` because the file is not there
    means "no window is open, start one". `None` because the read failed means
    "a window may be open and I cannot see it"."""
    absent = tmp_path / "absent.json"
    assert seal_baseline.read_or_unreadable(absent) == (None, False)

    corrupt = tmp_path / "corrupt.json"
    corrupt.write_bytes(b"{ not json")
    assert seal_baseline.read_or_unreadable(corrupt) == (None, True)

    listed = tmp_path / "list.json"
    listed.write_bytes(b"[1]")
    assert seal_baseline.read_or_unreadable(listed) == (None, True)

    good = tmp_path / "good.json"
    good.write_bytes(b'{"in_flight": 2}')
    assert seal_baseline.read_or_unreadable(good) == ({"in_flight": 2}, False)
