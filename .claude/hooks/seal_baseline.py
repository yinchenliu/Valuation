#!/usr/bin/env python3
"""PreToolUse snapshot of the sealed files, taken at dispatch.

The SubagentStop seal asks "did this subagent change a sealed file?". It cannot
ask git, because AGENTS.md has the orchestrator write to `.agent/journal/INDEX.md`
and `STATUS.md` *after a subagent returns*. By the time the next subagent starts,
the orchestrator's own uncommitted lines are already there. Comparing against
HEAD then accuses every subagent of the orchestrator's write, and the only way to
clear the accusation is to delete the orchestrator's record -- the seal destroying
what it exists to protect.

So the seal needs a baseline taken at the moment of dispatch instead. This hook
writes it. It runs on PreToolUse for Agent, Task and SendMessage -- every way a
subagent starts or restarts, which is the orchestrator's last action before that
subagent runs.

SendMessage is in that list because resuming an agent through it skips the Agent
matcher entirely, which would leave the seal comparing against a stale snapshot
and blaming the resumed agent for every orchestrator write since.

Subagents cannot call Agent or Task (`disallowedTools` in every role's
frontmatter). They CAN call SendMessage, so the role check below is what stops a
subagent refreshing the measurement taken of it. That check is load bearing, not
defensive tidiness.

Three things are sealed:

  .agent/journal/INDEX.md   the orchestrator is its only writer
  STATUS.md                 the orchestrator's measurement of the build
  .claude/hooks/*.py, *.sh  the guard a subagent must not be able to disarm,
                            and run_hook.sh, which starts every hook

The baseline is a hash, not a copy. A subagent that changes a file and changes it
back has changed nothing, and that is the right answer.

Exit 0 always. A missing baseline makes the seal fall back to HEAD for the two
tracked files, which is the older, blunter behaviour -- never a hole.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

ROLES = {"programmer", "code-reviewer", "tester"}
INDEX = Path(".agent/journal/INDEX.md")
STATUS = Path("STATUS.md")
HOOKS = Path(".claude/hooks")
BASELINE = Path(".agent/.seal-baseline.json")


def digest(path: Path) -> str | None:
    """sha256 of `path`, or None if it does not exist."""
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def tree_digest(directory: Path) -> str | None:
    """sha256 over the sorted (name, bytes) pairs of every .py and .sh in `directory`.

    Sorted so the result does not depend on directory order, and the name is
    hashed alongside the bytes so a rename is a change.
    """
    try:
        files = sorted([*directory.glob("*.py"), *directory.glob("*.sh")])
    except OSError:
        return None
    if not files:
        return None
    h = hashlib.sha256()
    for f in files:
        try:
            h.update(f.name.encode("utf-8"))
            h.update(f.read_bytes())
        except OSError:
            return None
    return h.hexdigest()


# How long a snapshot may sit with subagents still counted in flight before it
# is treated as abandoned. An agent that is killed, or a session that ends
# mid-run, never fires SubagentStop, so the count would otherwise never return
# to 0 and every later agent would be judged against an ancient snapshot. Both
# happened on 2026-10-07 and 2026-10-08. `session_id` catches the new-session
# case exactly; this window is the backstop for a kill inside one session.
# Twelve hours: longer than any single agent run this repository has made. The
# longest measured is about an hour, and the window has to clear that by a wide
# margin, because expiring a live window is the loud failure and leaving a dead
# one is the quiet failure.
#
# **The first version of this comment said "shorter than a working day" and the
# code reviewer disproved it on 2026-10-08**: session `01fb2109` spans 26 hours
# and 14 dispatches. A session is not a working day, so that was never the
# bound. The number is unchanged because `session_id` already covers the
# session-ended case exactly, and this window only has to outlast one agent.
STALE_AFTER_HOURS = 12


def read_or_unreadable(path: Path) -> tuple[dict[str, object] | None, bool]:
    """`(state, unreadable)`. `unreadable` is True only when the file is there
    and could not be read or parsed as an object.

    **A caller must tell those two apart.** A file that is not there means "no
    window is open, start one". A file that is there and cannot be read -- a
    lock, a partial write -- means "a window may be open and I cannot see it".
    The code reviewer's G4 found that distinction missing.

    There was a `read_state` wrapper here that dropped the second value. **The
    unit's tester found it had no caller at all**, which ruff's default rules
    would never have said, so it is gone rather than left as a second way to
    read this file that silently discards the thing G4 added.
    """
    if not path.exists():
        return None, False
    try:
        loaded = json.loads(path.read_text())
    except (OSError, ValueError):
        return None, True
    return (loaded, False) if isinstance(loaded, dict) else (None, True)


def write_state(path: Path, state: dict[str, object]) -> None:
    """Write the snapshot. A failure here is silent on purpose: the seal is a
    tripwire, and a hook that stopped a dispatch because a file was locked would
    be worse than one that misses a check."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, indent=2) + "\n")
    except OSError:
        return


def as_count(value: object) -> int:
    """`value` as a count, and 0 for anything that is not one.

    The first shape of this hook wrote `int(previous.get("in_flight") or 0)`,
    which raises `ValueError` on a string. The code reviewer measured the cost on
    2026-10-08: a baseline holding `"abc"` crashed BOTH hooks at exit 1, so
    `SubagentStop` performed no comparison at all and said nothing. Before this
    unit a corrupt baseline healed at the next dispatch. **A hook that crashes is
    a guard that is off**, so every read of this field goes through here.
    """
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def is_stale(taken_at: object) -> bool:
    """True when `taken_at` is missing, unreadable, or older than the window."""
    if not isinstance(taken_at, str):
        return True
    try:
        when = datetime.fromisoformat(taken_at)
    except ValueError:
        return True
    if when.tzinfo is None:
        return True
    return (datetime.now(UTC) - when).total_seconds() > STALE_AFTER_HOURS * 3600


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (ValueError, OSError):
        sys.exit(0)

    cwd = data.get("cwd") or os.getcwd()
    project = Path(os.environ.get("CLAUDE_PROJECT_DIR") or cwd)
    path = project / BASELINE

    # Recorded BEFORE any exit below, and it has to be, because the question it
    # answers is "did this hook see a real dispatch at all?". On 2026-10-08 the
    # answer turned out to be no: fourteen real dispatches in one session and
    # this file was never written, so the seal has not been firing. The role
    # check below is one candidate cause -- if the harness puts the TARGET
    # agent's role in `agent_type`, every dispatch exits here -- and recording
    # first is the only way to tell that apart from the hook never running.
    #
    # Key names, `agent_type` and `tool_name` only. A payload carries prompts,
    # and a prompt does not belong in a file the repository keeps.
    observation = {
        "payload_keys": sorted(data.keys()),
        "agent_type": (data.get("agent_type") or "").strip(),
        "tool_name": data.get("tool_name") or "",
        "seen_at": datetime.now(UTC).isoformat(),
    }
    saved, unreadable = read_or_unreadable(path)
    seen = dict(saved) if saved else {}
    seen["last_dispatch_seen"] = observation
    write_state(path, seen)

    # A subagent must never refresh the baseline. The seal is worth nothing if
    # the thing it measures can reset the measurement taken of it.
    #
    # **The role decides this, and the tool name does not.** Round 2 of
    # `P1f-worktree-guards` scoped the check to `tool_name == "SendMessage"`, to
    # remove a guessed cause for backlog item 143. The guess was refuted the same
    # day -- the hook is never invoked, so nothing about `agent_type` can be the
    # cause -- and the narrowing was left in anyway, on the claim that it was
    # "correct on its own terms". **The unit's tester measured that it is not**,
    # in a scratch copy on 2026-10-08:
    #
    #   tool_name=SendMessage, agent_type=tester   in_flight 1 -> 1   REFUSED
    #   tool_name ABSENT,      agent_type=tester   in_flight 1 -> 2   let through
    #   tool_name=Agent,       agent_type=tester   in_flight 1 -> 2   let through
    #
    # and, with a subagent that had already written `STATUS.md`, the snapshot was
    # retaken over the tampered bytes. That is exactly the false negative item
    # 141 exists to remove, reintroduced by a narrowing that bought nothing.
    #
    # So the check reads the role and nothing else. A payload that carries a
    # role but no tool name is the dangerous shape, not the exempt one.
    if (data.get("agent_type") or "").strip() in ROLES:
        sys.exit(0)

    # Backlog item 141. Until `P1f-worktree-guards` this hook rewrote the file on
    # every dispatch, so with two subagents in flight the second dispatch
    # overwrote the snapshot the first would be judged against: anything the
    # first wrote to a sealed file was already inside the new snapshot, and the
    # check cleared it. A false negative, and a silent one.
    #
    # The fix counts instead of rewriting. The snapshot is taken when the number
    # of subagents in flight goes from 0 to 1, and later dispatches only
    # increment. `seal_check.py` decrements. So every agent in a concurrent
    # window is judged against the state before that window opened.
    #
    # The direction of the remaining error is deliberate. An agent that started
    # late is judged against a slightly older state than its own dispatch, so a
    # sealed file that moved in between is reported rather than ignored. That is
    # a false positive, which is loud, and this repository already forbids the
    # one write that could cause it: `main-agent` says the orchestrator does not
    # write `.agent/journal/INDEX.md` while a unit is building.
    # G4: an unreadable file is NOT an absent one, and neither is recoverable.
    # The digests it held are gone, so there is nothing to keep. The choice is
    # between taking a fresh snapshot, which risks ONE false negative for an
    # agent already in flight and then self-heals, and writing a state with no
    # digests, which makes `seal_check.py` skip every comparison in silence --
    # no check at all, for ever. The first is strictly better, and it is what
    # this hook did before `P1f-worktree-guards`.
    #
    # **What G4 actually asks for is that the loss not be silent**, so an
    # unreadable file is recorded as `window_lost_at` in the snapshot that
    # replaces it. A reader of this file can then see that a window was dropped
    # and when.
    previous = seen if seen else None
    fresh = (
        unreadable
        or (
        previous is None
        or as_count(previous.get("in_flight")) <= 0
        or previous.get("session_id") != (data.get("session_id") or "")
        or is_stale(previous.get("taken_at"))
        )
    )

    if fresh:
        state = {
            "index_sha256": digest(project / INDEX),
            "status_sha256": digest(project / STATUS),
            "hooks_sha256": tree_digest(project / HOOKS),
            "taken_at": datetime.now(UTC).isoformat(),
            "tool": data.get("tool_name") or "",
            "session_id": data.get("session_id") or "",
            "in_flight": 1,
            # Recorded so the next change to these hooks can see what the harness
            # actually sends, instead of guessing. Keys only: a payload carries
            # prompts, and a prompt does not belong in a file the repository keeps.
            "payload_keys": sorted(data.keys()),
            # Carried through a refresh on purpose. It is the evidence that this
            # hook ran at all, and a refresh that dropped it would erase exactly
            # the thing the 2026-10-08 investigation needs.
            "last_dispatch_seen": observation,
        }
        if unreadable:
            state["window_lost_at"] = observation["seen_at"]
    else:
        state = dict(previous)
        state["in_flight"] = as_count(previous.get("in_flight")) + 1
        state["payload_keys"] = sorted(
            set(state.get("payload_keys") or []) | set(data.keys())
        )

    write_state(path, state)
    sys.exit(0)


if __name__ == "__main__":
    main()
