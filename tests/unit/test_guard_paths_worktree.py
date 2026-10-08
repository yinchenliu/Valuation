"""The PreToolUse write guard, in a git worktree and in scratch space.

Backlog item 142: `guard_paths.py` allowed every path that was not under
`CLAUDE_PROJECT_DIR`, and a git worktree is not under it, so in a worktree the
write guard was off. `P1f-worktree-guards` closed that with `worktree_root_of`
and `resolve_repo_relative`. This file locks both halves: the worktree is
guarded, and scratch space -- which every unit in this repository works in --
still is not.

Where every expected value in this file comes from
--------------------------------------------------
**Not one of them is a reading of what the guard printed.** Each is one of:

* **The role matrix**, a contract written down before this unit existed, in
  `AGENTS.md` and in `.claude/agents/<role>.md`: a programmer writes everything
  except `tests/`, a code reviewer writes nothing except `.agent/journal/`, a
  tester writes nothing except `tests/` and `.agent/journal/`, and four paths
  are closed to all three. The test asserts the contract.
* **A closed-form identity**: the deny message for `<worktree>/analysis/dcf.py`
  must equal, byte for byte, the deny message for `<project>/analysis/dcf.py`.
  That identity is the whole content of item 142 -- a worktree *is* this
  repository, checked out elsewhere -- and it holds whatever the wording of the
  message happens to be, so it cannot be satisfied by photographing either side.
* **A fact about git's on-disk layout**, documented in `gitrepository-layout(5)`
  and older than this repository: a linked worktree's `.git` is a FILE holding
  `gitdir: <main>/.git/worktrees/<name>`, while an ordinary checkout's `.git` is
  a directory. Every scratch shape below is derived from that fact.

Nothing here skips. See `_hook_harness.require_git`.
"""

from __future__ import annotations

from pathlib import Path
from types import ModuleType

import pytest

from tests.unit._hook_harness import (
    add_worktree,
    ask_guard,
    ask_guard_in_process,
    decision_of,
    drive_main,
    guard_payload,
    load_hook,
    make_scratch_repository,
    require_git,
)

ROLES = ("programmer", "code-reviewer", "tester")


# --- the scratch repository, its worktree, and the hostile neighbours --------


@pytest.fixture(scope="session")
def scratch_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Session scratch, outside this repository.

    Everything below is built here from nothing. No test adds a worktree to, or
    commits in, the repository under test.
    """
    return tmp_path_factory.mktemp("p1f_guard")


@pytest.fixture(scope="session")
def project(scratch_root: Path) -> Path:
    return make_scratch_repository(scratch_root)


@pytest.fixture(scope="session")
def worktree(project: Path, scratch_root: Path) -> Path:
    """A real `git worktree add --detach` of the scratch repository."""
    return add_worktree(project, scratch_root / "worktree_7f3a_checkout")


@pytest.fixture(scope="session")
def outside(scratch_root: Path, project: Path, worktree: Path) -> dict[str, Path]:
    """Six directories that are NOT worktrees of `project`, by six routes.

    Each shape comes from git's layout, not from running the guard:

    `plain`        no `.git` anywhere above it -- ordinary scratch space.
    `own_clone`    its own repository, so `.git` is a DIRECTORY, not a file.
    `foreign`      a `.git` file naming ANOTHER repository's `worktrees/`.
    `junk`         a `.git` file holding bytes that are not a `gitdir:` line.
    `empty`        a `.git` file with no bytes at all.
    `submodule`    a `.git` file naming `<project>/.git` itself, which is the
                   submodule shape and not a worktree of it.
    `wt_extra`     a sibling whose name is the worktree's name plus a suffix.
                   A prefix test on the string `<wt>` would wrongly catch it.
    """
    root = scratch_root / "outside"
    root.mkdir(exist_ok=True)

    plain = root / "plain"
    (plain / "analysis").mkdir(parents=True, exist_ok=True)

    own_clone = root / "own_clone"
    (own_clone / "analysis").mkdir(parents=True, exist_ok=True)
    make_scratch_repository(own_clone, name="inner")

    def with_git_file(name: str, content: bytes) -> Path:
        folder = root / name
        (folder / "analysis").mkdir(parents=True, exist_ok=True)
        (folder / ".git").write_bytes(content)
        return folder

    other = scratch_root / "other_repo"
    (other / ".git" / "worktrees" / "w").mkdir(parents=True, exist_ok=True)

    wt_extra = Path(str(worktree) + "_extra")
    (wt_extra / "analysis").mkdir(parents=True, exist_ok=True)

    return {
        "plain": plain,
        "own_clone": own_clone / "inner",
        "foreign": with_git_file(
            "foreign", f"gitdir: {other}/.git/worktrees/w\n".encode()
        ),
        "junk": with_git_file("junk", b"not a gitdir line at all\x00\xff\n"),
        "empty": with_git_file("empty", b""),
        "submodule": with_git_file("submodule", f"gitdir: {project}/.git\n".encode()),
        "wt_extra": wt_extra,
    }


@pytest.fixture(scope="session")
def guard() -> ModuleType:
    return load_hook("guard_paths.py")


def test_git_is_present_so_no_worktree_case_can_skip() -> None:
    """The guard against the guard's own history.

    `.claude/check_guard.py` ran the hook with `PATH: ""`, so every worktree
    case would have passed as "allow" for the wrong reason. If git disappears
    from this machine, this file must go RED, not green with fewer cases.
    """
    assert require_git()


# --- criterion 2: the worktree decisions, for all three roles ---------------

# (role, repo-relative target, expected). Every expectation is the role matrix
# in `AGENTS.md` and `.claude/agents/<role>.md`, applied to a path that happens
# to sit in a worktree. The worktree changes nothing about the matrix, and that
# is the claim under test.
ROLE_CASES = [
    ("tester", "analysis/dcf.py", "deny"),
    ("tester", "models/valuation.py", "deny"),
    ("tester", "config.py", "deny"),
    ("tester", "tests/unit/test_x.py", "allow"),
    ("tester", ".agent/journal/x.md", "allow"),
    ("programmer", "analysis/dcf.py", "allow"),
    ("programmer", "models/valuation.py", "allow"),
    ("programmer", "tests/unit/test_x.py", "deny"),
    ("programmer", ".agent/journal/x.md", "allow"),
    ("code-reviewer", "analysis/dcf.py", "deny"),
    ("code-reviewer", "tests/unit/test_x.py", "deny"),
    ("code-reviewer", ".agent/journal/r.md", "allow"),
]


@pytest.mark.parametrize(("role", "target", "expected"), ROLE_CASES)
def test_the_role_matrix_holds_inside_a_worktree(
    role: str, target: str, expected: str, project: Path, worktree: Path, guard
) -> None:
    got, _ = ask_guard(
        role, "Write", {"file_path": str(worktree / target)}, project, cwd=worktree
    )
    assert got == expected


@pytest.mark.parametrize(("role", "target", "expected"), ROLE_CASES)
def test_the_same_matrix_holds_in_the_project_itself(
    role: str, target: str, expected: str, project: Path, guard
) -> None:
    """The control. A worktree case that agreed with nothing would prove nothing."""
    run = drive_main(
        guard,
        guard_payload(role, "Write", {"file_path": str(project / target)}, project),
        project,
    )
    got, _ = decision_of(run)
    assert got == expected


# --- criterion 2, continued: ALWAYS_DENIED, and the Bash tripwire -----------

ALWAYS_DENIED_TARGETS = [
    ".agent/journal/INDEX.md",
    "STATUS.md",
    "AGENTS.md",
    ".claude/hooks/guard_paths.py",
    ".claude/agents/tester.md",
    ".agent/.seal-baseline.json",
]


@pytest.mark.parametrize("target", ALWAYS_DENIED_TARGETS)
@pytest.mark.parametrize("role", ROLES)
def test_the_sealed_paths_are_denied_to_every_role_in_a_worktree(
    role: str, target: str, project: Path, worktree: Path, guard
) -> None:
    """`ALWAYS_DENIED` beats "whatever its allow list says", and a worktree is
    not an exception to it. The list is in `AGENTS.md`: the orchestrator owns
    `INDEX.md` and `STATUS.md`, `AGENTS.md` is the contract, `.claude/` holds
    the permissions, and the seal's baseline is the instrument that measures
    the agent."""
    got, reason = ask_guard_in_process(
        guard, role, "Write", {"file_path": str(worktree / target)},
        project, cwd=worktree,
    )
    assert got == "deny"
    assert "every subagent" in reason
    assert target in reason


@pytest.mark.parametrize("target", ALWAYS_DENIED_TARGETS)
def test_the_sealed_paths_are_denied_through_a_real_subprocess_too(
    target: str, project: Path, worktree: Path
) -> None:
    """The same six targets, re-taken the way the harness runs the hook."""
    got, _ = ask_guard(
        "programmer", "Write", {"file_path": str(worktree / target)},
        project, cwd=worktree,
    )
    assert got == "deny"


BASH_CASES = [
    ("tester", "rm -rf {wt}/analysis", "deny"),
    ("tester", "echo hi > {wt}/analysis/x.py", "deny"),
    ("tester", "echo hi > {wt}/STATUS.md", "deny"),
    ("programmer", "echo x | tee {wt}/tests/unit/test_x.py", "deny"),
    ("code-reviewer", "git restore {wt}/analysis/dcf.py", "deny"),
    ("tester", "echo hi > {wt}/tests/unit/test_x.py", "allow"),
    ("tester", "grep -rn kwargs {wt}/analysis/", "allow"),
]


@pytest.mark.parametrize(("role", "template", "expected"), BASH_CASES)
def test_the_bash_tripwire_reaches_into_a_worktree(
    role: str, template: str, expected: str, project: Path, worktree: Path
) -> None:
    command = template.format(wt=worktree.as_posix())
    got, _ = ask_guard(role, "Bash", {"command": command}, project, cwd=worktree)
    assert got == expected


@pytest.mark.parametrize(("role", "template", "expected"), BASH_CASES)
def test_the_bash_tripwire_reaches_into_a_worktree_in_process_too(
    role: str, template: str, expected: str, project: Path, worktree: Path, guard
) -> None:
    command = template.format(wt=worktree.as_posix())
    got, _ = ask_guard_in_process(
        guard, role, "Bash", {"command": command}, project, cwd=worktree
    )
    assert got == expected


BASH_TARGET_CASES = [
    ("echo hi > analysis/x.py", {"analysis/x.py"}),
    ("cat f >> models/valuation.py", {"models/valuation.py"}),
    ("echo x | tee tests/test_x.py", {"tests/test_x.py"}),
    ("rm -rf analysis", {"analysis"}),
    ("cp scratch/a STATUS.md", {"STATUS.md"}),
    ("mv a.py b.py", {"b.py"}),
    ('sed -i "" "s/a/b/" analysis/dcf.py', {"analysis/dcf.py"}),
    ("git restore analysis/dcf.py", {"analysis/dcf.py"}),
    ("grep -rn kwargs analysis/", set()),
    ("git diff HEAD -- analysis/dcf.py", set()),
]


@pytest.mark.parametrize(("command", "expected"), BASH_TARGET_CASES)
def test_bash_targets_names_what_the_shell_would_write(
    guard, command: str, expected: set[str]
) -> None:
    """Expected from the shell's own semantics, read off each command: `>` and
    `>>` write their operand, `tee` and `rm` write every positional argument,
    `cp` and `mv` write their last one, `sed -i` writes everything after the
    script, `git restore` writes its paths, and `grep` and `git diff` write
    nothing. The guard is a tripwire, so it is allowed to over-report; it is not
    allowed to miss one of these."""
    assert expected <= set(guard.bash_targets(command)), command
    if not expected:
        assert guard.bash_targets(command) == []


def test_a_relative_path_is_resolved_against_the_worktree_cwd(
    project: Path, worktree: Path
) -> None:
    """An agent working *inside* a worktree types `analysis/dcf.py`, not an
    absolute path. `cwd` is what makes that a repository path."""
    denied, _ = ask_guard(
        "tester", "Write", {"file_path": "analysis/dcf.py"}, project, cwd=worktree
    )
    allowed, _ = ask_guard(
        "tester", "Write", {"file_path": "tests/unit/test_x.py"}, project, cwd=worktree
    )
    assert (denied, allowed) == ("deny", "allow")


# --- criterion 3: the message is identical, not merely present --------------


def test_the_worktree_deny_message_is_identical_to_the_in_project_one(
    project: Path, worktree: Path
) -> None:
    """The identity that defines item 142.

    A test that only asserted "denied" would pass against a message naming the
    wrong path, or naming an absolute path the reader cannot act on. The
    expected value here is not a string this file quotes -- it is the
    in-project message, whatever it says.
    """
    in_project, project_reason = ask_guard(
        "tester", "Write", {"file_path": str(project / "analysis" / "dcf.py")},
        project, cwd=project,
    )
    in_worktree, worktree_reason = ask_guard(
        "tester", "Write", {"file_path": str(worktree / "analysis" / "dcf.py")},
        project, cwd=worktree,
    )
    assert in_project == "deny"
    assert in_worktree == "deny"
    assert worktree_reason == project_reason

    # ...and the message is about the repository-relative path, so a reader can
    # act on it. `<worktree>/analysis/dcf.py` relative to the worktree root is
    # `analysis/dcf.py`, by hand.
    assert "analysis/dcf.py" in worktree_reason
    assert "`tester`" in worktree_reason
    assert "worktree_7f3a_checkout" not in worktree_reason
    assert ".." not in worktree_reason


def test_the_always_denied_message_is_identical_in_a_worktree(
    project: Path, worktree: Path
) -> None:
    _, project_reason = ask_guard(
        "programmer", "Write", {"file_path": str(project / "STATUS.md")},
        project, cwd=project,
    )
    _, worktree_reason = ask_guard(
        "programmer", "Write", {"file_path": str(worktree / "STATUS.md")},
        project, cwd=worktree,
    )
    assert worktree_reason == project_reason
    assert "STATUS.md" in worktree_reason


# --- criterion 4: the guard needs no git ------------------------------------


@pytest.mark.parametrize("path_value", ["", "C:/nonexistent_directory"])
def test_the_guard_denies_in_a_worktree_with_no_git_on_path(
    path_value: str, project: Path, worktree: Path
) -> None:
    """The reviewer's F6.

    Round 1 asked `git worktree list`. With no git on `PATH` it failed open
    **silently**, which put item 142 back under a condition nobody would notice.
    `worktree_root_of` reads the `.git` file instead and runs no subprocess, so
    the decision must not move when `PATH` is emptied.
    """
    with_path, reason_with = ask_guard(
        "tester", "Write", {"file_path": str(worktree / "analysis" / "dcf.py")},
        project, cwd=worktree,
    )
    without_path, reason_without = ask_guard(
        "tester", "Write", {"file_path": str(worktree / "analysis" / "dcf.py")},
        project, cwd=worktree, path_value=path_value,
    )
    assert with_path == "deny"
    assert without_path == "deny"
    assert reason_without == reason_with


def test_scratch_is_still_allowed_with_no_git_on_path(
    project: Path, outside: dict[str, Path]
) -> None:
    """The other direction of F6: no git must not mean "deny everything"."""
    got, _ = ask_guard(
        "tester", "Write", {"file_path": str(outside["plain"] / "analysis" / "dcf.py")},
        project, cwd=outside["plain"], path_value="",
    )
    assert got == "allow"


# --- criterion 5: scratch stays writable ------------------------------------

SCRATCH_SHAPES = ["plain", "own_clone", "foreign", "junk", "empty", "submodule", "wt_extra"]


@pytest.mark.parametrize("shape", SCRATCH_SHAPES)
@pytest.mark.parametrize("role", ROLES)
def test_scratch_space_stays_writable_whatever_it_looks_like(
    role: str, shape: str, project: Path, outside: dict[str, Path], guard
) -> None:
    """Criterion 5, the one a regression breaks every unit with.

    Each of these seven directories would be denied if `worktree_root_of` were
    loose about what counts as a worktree of THIS repository. None of them is
    one: the expectation is git's layout, not the guard's output.
    """
    target = outside[shape] / "analysis" / "dcf.py"
    got, reason = ask_guard_in_process(
        guard, role, "Write", {"file_path": str(target)}, project, cwd=outside[shape]
    )
    assert got == "allow", f"{shape} is not a worktree of the project: {reason}"


@pytest.mark.parametrize("shape", SCRATCH_SHAPES)
def test_scratch_space_stays_writable_through_a_real_subprocess_too(
    shape: str, project: Path, outside: dict[str, Path]
) -> None:
    """The same seven shapes, re-taken the way the harness runs the hook."""
    target = outside[shape] / "analysis" / "dcf.py"
    got, _ = ask_guard("tester", "Write", {"file_path": str(target)}, project,
                       cwd=outside[shape])
    assert got == "allow"


def test_the_two_drivers_agree_on_every_shape(
    project: Path, worktree: Path, outside: dict[str, Path], guard
) -> None:
    """`main()` in this process and `main()` in a subprocess are the same code,
    and this is what entitles the fast driver above to stand for the slow one.
    If they ever diverge -- a module-level read of the environment, say -- every
    in-process result in this file is suspect, and this test says so."""
    targets = [
        worktree / "analysis" / "dcf.py",       # the item 142 case
        worktree / "tests" / "x.py",            # allowed inside a worktree
        worktree / "STATUS.md",                 # ALWAYS_DENIED inside a worktree
        outside["plain"] / "analysis" / "dcf.py",     # scratch
        outside["wt_extra"] / "analysis" / "dcf.py",  # the sibling name trap
    ]
    for target in targets:
        fast = ask_guard_in_process(
            guard, "tester", "Write", {"file_path": str(target)}, project, cwd=target.parent
        )
        slow = ask_guard(
            "tester", "Write", {"file_path": str(target)}, project, cwd=target.parent
        )
        assert fast == slow, target


def test_a_scratch_bash_command_is_still_allowed(
    project: Path, outside: dict[str, Path]
) -> None:
    scratch = outside["plain"].as_posix()
    for command in (
        f"rm -rf {scratch}/analysis",
        f"echo hi > {scratch}/STATUS.md",
        f'sed -i "" "s/a/b/" {scratch}/analysis/dcf.py',
    ):
        got, _ = ask_guard("tester", "Bash", {"command": command}, project,
                           cwd=outside["plain"])
        assert got == "allow", command


def test_a_pruned_worktree_of_this_project_is_still_denied(
    project: Path, scratch_root: Path
) -> None:
    """The error direction, and it is closed rather than open.

    A directory whose `.git` file names `<project>/.git/worktrees/<anything>` is
    a checkout of this repository whether or not git has pruned the entry. The
    guard must not need git's bookkeeping to agree.
    """
    ghost = scratch_root / "ghost_worktree"
    (ghost / "analysis").mkdir(parents=True, exist_ok=True)
    (ghost / ".git").write_bytes(
        f"gitdir: {project}/.git/worktrees/already_pruned\n".encode()
    )
    got, _ = ask_guard("tester", "Write",
                       {"file_path": str(ghost / "analysis" / "dcf.py")},
                       project, cwd=ghost)
    assert got == "deny"


# --- criterion 6: `worktree_root_of` and `resolve_repo_relative`, directly ---


def test_worktree_root_of_finds_the_root_from_the_root_itself(
    guard, project: Path, worktree: Path
) -> None:
    assert guard.worktree_root_of(worktree, project) == worktree


def test_worktree_root_of_finds_the_root_from_a_file_deep_inside(
    guard, project: Path, worktree: Path
) -> None:
    deep = worktree / "analysis" / "sub" / "deeper" / "dcf.py"
    assert guard.worktree_root_of(deep, project) == worktree


def test_worktree_root_of_returns_none_for_the_project_itself(
    guard, project: Path
) -> None:
    """The project's own `.git` is a directory, so it is not a linked worktree.
    `main` reaches `worktree_root_of` only after `repo_relative` has declined,
    and the project must never be mistaken for one of its own worktrees."""
    assert guard.worktree_root_of(project / "analysis" / "dcf.py", project) is None


def test_worktree_root_of_returns_none_for_scratch(
    guard, project: Path, outside: dict[str, Path]
) -> None:
    assert guard.worktree_root_of(outside["plain"] / "analysis" / "dcf.py", project) is None


def test_worktree_root_of_returns_none_when_gitdir_points_elsewhere(
    guard, project: Path, outside: dict[str, Path]
) -> None:
    """A `.git` file is necessary and not sufficient: it has to name THIS
    project's `worktrees/`."""
    assert guard.worktree_root_of(outside["foreign"] / "analysis" / "dcf.py", project) is None
    assert guard.worktree_root_of(outside["submodule"] / "analysis" / "dcf.py", project) is None


def test_resolve_repo_relative_maps_a_worktree_path_onto_the_repository(
    guard, project: Path, worktree: Path
) -> None:
    """The function item 142 turns on. `<worktree>/analysis/dcf.py` is
    `analysis/dcf.py` in the repository, by hand."""
    assert guard.resolve_repo_relative(
        str(worktree / "analysis" / "dcf.py"), project, worktree
    ) == "analysis/dcf.py"
    assert guard.resolve_repo_relative(
        str(project / "analysis" / "dcf.py"), project, project
    ) == "analysis/dcf.py"


def test_resolve_repo_relative_returns_none_for_scratch(
    guard, project: Path, outside: dict[str, Path]
) -> None:
    """`None` is what `main` reads as "outside the repository, allowed". Every
    unit's scratch discipline is this one return value."""
    assert guard.resolve_repo_relative(
        str(outside["plain"] / "analysis" / "dcf.py"), project, outside["plain"]
    ) is None


def test_resolve_repo_relative_handles_a_path_relative_to_a_worktree_cwd(
    guard, project: Path, worktree: Path
) -> None:
    """An agent inside a worktree types `analysis/dcf.py`. The target is only a
    repository path once `cwd` is applied to it, and `cwd` is the worktree."""
    assert guard.resolve_repo_relative("analysis/dcf.py", project, worktree) == "analysis/dcf.py"
    assert guard.resolve_repo_relative("tests/unit/x.py", project, worktree) == "tests/unit/x.py"


@pytest.mark.parametrize("target", ["$S/out.py", "%TEMP%/out.py", "${S}/out.py", ""])
def test_resolve_repo_relative_declines_to_guess_at_an_unexpanded_variable(
    guard, project: Path, worktree: Path, target: str
) -> None:
    """The documented threat model, not a hole: the guard cannot know what the
    shell will expand `$S` to, so it declines rather than treating `$S` as a
    repo-relative directory name. The worktree branch has to decline for the
    same reason the project branch does, or a variable path would be resolved
    against a worktree root and judged on a guess."""
    assert guard.resolve_repo_relative(target, project, worktree) is None


def test_repo_relative_alone_cannot_see_a_worktree(
    guard, project: Path, worktree: Path
) -> None:
    """Item 142, stated as a property rather than as history.

    `repo_relative` is the pre-unit function and it still returns None for a
    worktree path -- that is not a defect in it, it is why
    `resolve_repo_relative` had to exist. If this ever returns a path, the two
    functions have been collapsed into one and the worktree branch is dead.
    """
    assert guard.repo_relative(
        str(worktree / "analysis" / "dcf.py"), project, worktree
    ) is None


# --- the role matrix at the function level ----------------------------------

VERDICT_CASES = [
    ("tester", "analysis/dcf.py", False),
    ("tester", "tests/unit/test_x.py", True),
    ("tester", ".agent/journal/x.md", True),
    ("tester", ".agent/journal/INDEX.md", False),
    ("programmer", "analysis/dcf.py", True),
    ("programmer", "tests/x.py", False),
    ("programmer", "STATUS.md", False),
    ("code-reviewer", ".agent/journal/r.md", True),
    ("code-reviewer", "docs/INDEX.md", False),
    ("code-reviewer", ".claude/hooks/guard_paths.py", False),
]


@pytest.mark.parametrize(("role", "rel", "allowed"), VERDICT_CASES)
def test_verdict_applies_the_role_matrix(guard, role: str, rel: str, allowed: bool) -> None:
    """`verdict` is path-resolution-free, so this is the matrix on its own.
    Expected from `AGENTS.md` and `.claude/agents/<role>.md`."""
    reason = guard.verdict(rel, role)
    assert (reason is None) is allowed
    if reason is not None:
        assert rel in reason


def test_a_deny_reason_always_names_the_path_and_the_rule(guard) -> None:
    """Rule 3's shape, applied to a guard: a refusal that does not name what it
    refused tells the next reader nothing."""
    for role, rel in (("tester", "analysis/dcf.py"), ("programmer", "tests/x.py")):
        reason = guard.verdict(rel, role)
        assert reason is not None
        assert rel in reason
        assert role in reason
