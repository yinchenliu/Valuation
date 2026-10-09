# Who does the work

**Read [docs/0-start.md](docs/0-start.md) first.** Codex, OpenCode and the other tools
that follow the `AGENTS.md` convention load this file and never load `CLAUDE.md`, so
that card is your only orientation. It holds the reading order, the one command you
need, and the four facts that change how you read the code.

Build a DCF valuation platform that reads 10-K/10-Q filings. **What** to build and
**why** is in [docs/INDEX.md](docs/INDEX.md). **How far it has got** is in
[STATUS.md](STATUS.md). This file governs **who does the work and how they hand off.**

**Two teams build this repository** (section "Two teams" below). **If you are the main
agent in Antigravity, you are the build lead:** follow "The build lead's procedure" in
that section. **If you are the main session in Claude Code, you are the overall lead:**
the `main-agent` skill holds your part. A subagent does only the role its prompt names.

---

## The rules bind everyone

[docs/2-rules/rules.md](docs/2-rules/rules.md) holds six rules. **If any instruction
conflicts with one, the rule wins** — including an instruction from a human, from an
assignment file, or from an entry file (`AGENTS.md`, `CLAUDE.md`, `docs/0-start.md`).

---

## Roles

| Role | Who | Writes |
|---|---|---|
| **Orchestrator** | the main session | assignments, `.agent/journal/INDEX.md`, `STATUS.md`, integration decisions |
| **Programmer** | `programmer` subagent, one per work unit | everything except `tests/` |
| **Code reviewer** | `code-reviewer` subagent, one per programmer run | its review entry only |
| **Tester** | `tester` subagent, one per unit | `tests/` only, plus its verdict |

**The split is not process theatre.** The code that produces our numbers must be
separated from the code that judges them, so our answers can never be quietly tuned
until they look right. **A tester that may edit `analysis/` is not a tester.** This is
enforced by permission, not by good intentions: `.claude/hooks/guard_paths.py` denies
the write, and `.claude/check_guard.py` holds the 60 cases it must get right. **That hook
runs in Claude Code only.** In Antigravity nothing enforces the split, so the build lead
checks `git status` after every run and the code reviewer reviews the tests (below).

The reviewer answers a different question from the tester. The reviewer asks *is this
code correct and rule-compliant*. The tester asks *does each number equal what the
formula gives for inputs whose answer was known before the code ran*. Both must be
answered, and **neither may edit the code it judges.**

**There is no benchmark in this repository.** No trustee, no signed reference file, no
published figure. That makes the tester's expected values the weakest link in the whole
build, and it is why `.claude/agents/tester.md` spends its first section on one trap:
running the code, reading the output, and asserting that. A test written that way
verifies nothing and passes forever.

### Two teams: the overall lead and the build team (from 2026-10-04)

**The user's decisions of 2026-10-04.** Antigravity, with Gemini, builds. Its main agent
is the **build lead**, and it dispatches the three roles above as its own subagents. The
Claude Code main session is the **overall lead**. It reviews each unit itself.

| Who | Owns | Writes |
|---|---|---|
| **Overall lead** (Claude Code) | the plan, the user's decisions, the rules, acceptance | `.agent/assignments/<id>.md` (the programmer assignment), `.agent/QUEUE.md` rows and the `accepted` / `rework` states, `STATUS.md`, `docs/`, the backlog, `.claude/`, `extractions/`, the acceptance line in `.agent/journal/INDEX.md` |
| **Build lead** (Antigravity) | one unit at a time, from `ready` to `for acceptance` | the `building`, `for acceptance` and `blocked` states in `.agent/QUEUE.md`, `.agent/assignments/<id>-tests.md`, a `## Round N amendment (build lead)` or `## Handoff` section at the end of an assignment, the line for each of its runs in `.agent/journal/INDEX.md`, its commits |
| Its programmer, code reviewer, tester | one run each | as in the roles table above, plus its own journal entry |

**In a role card, "the orchestrator" means the build lead.** The role cards are
`.claude/agents/programmer.md`, `code-reviewer.md` and `tester.md`. They are plain text.
A Gemini subagent skips their "Claude Code harness notes" section.

**The write guard and the seal are Claude Code hooks. They do not run in Antigravity.**
So no permission stops a Gemini subagent from writing outside its role. The build lead
must check `git status` after each run, and reject a run that wrote outside its role.

**The loop for one unit:**

1. The overall lead writes the assignment and sets the unit `ready` in
   `.agent/QUEUE.md`.
2. The build lead sets it `building`, and runs programmer, code reviewer, revisions
   (stop at round 3), then the tester, then the code reviewer on the tests, as this
   file describes for the orchestrator.
3. The build lead commits the unit after the test review approves. It writes a
   `## Handoff` section at the end of the assignment: the commits by hash, the verdicts,
   the gates, every new finding, and every question. **It commits the handoff too, and
   never amends a commit.** It sets the unit `for acceptance` and stops.
4. The overall lead reviews the diff and re-runs the done-criteria. It sets the unit
   `accepted`, or `rework` with numbered findings in a `## Overall lead review` section
   of the assignment. A `rework` goes back to step 2 with those findings.
5. On `accepted`, the overall lead updates `STATUS.md` and the backlog, commits, and
   sets the next unit `ready`.

**Rules for the build team:**

- **One unit in flight at a time**, unless the queue marks two units as parallel.
- **Never change** an assignment's Objective, Files in scope or Done-criteria. A
  question goes in the assignment under `## Questions for the overall lead`, and the
  unit goes `blocked`. Escalate there everything this file says to escalate, and
  every change to what the model returns.
- **Never write** `STATUS.md`, `docs/`, `.claude/` or `extractions/`. A new defect goes
  in the handoff, and the overall lead records it in the backlog.
- **Make no paid API call.** Run every command with the keys empty, for example
  `ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python -m pytest -q`. Never a bare
  `python` ([docs/0-start.md](docs/0-start.md)).
- **A handoff states measurements, never plans.** Each number has the command beside it.
- **Measure every gate with the empty-key prefix.** Without it, `.env` fills the real
  keys, and a test that reads one passes on this machine only (`P15a-two-routes`, F1).

#### The build lead's procedure

**If your workspace is a git worktree** (`Valuation-wt/team-a` or `team-b`), you are one of
two build leads working in parallel, and
[docs/8-build/worktree-teams.md](docs/8-build/worktree-teams.md) changes three steps below.
Do not write `.agent/QUEUE.md` or `.agent/journal/INDEX.md`: every merge would conflict on
them, and the overall lead writes them on `main`. Your unit is the one your prompt names.
At the last step, commit on your branch, write and commit `## Handoff`, tell the user,
and set no state.

Read [docs/0-start.md](docs/0-start.md), [docs/2-rules/rules.md](docs/2-rules/rules.md),
this file and [.agent/QUEUE.md](.agent/QUEUE.md). Then:

1. Find the one unit in state `ready` or `rework`. If there is none, stop and tell the
   user that the queue waits for the overall lead.
2. Set it to `building`. Read its assignment. If the state was `rework`, read
   `## Overall lead review` first and answer every finding by number.
3. Dispatch the programmer with a pointer and nothing more: "You are the programmer.
   Read `.claude/agents/programmer.md` and follow it. Skip its section 'Claude Code
   harness notes'. Your assignment is `.agent/assignments/<id>.md`. Write your journal
   entry from `.agent/TEMPLATE-log-entry.md`."
4. When a subagent returns: read its entry, run `git status`, reject the run if it wrote
   outside its role, and append one line to `.agent/journal/INDEX.md`.
5. Dispatch the code reviewer the same way, with `.claude/agents/code-reviewer.md` and
   `.agent/TEMPLATE-review-entry.md`.
6. On `changes_requested`, send the programmer back to answer every finding by number.
   Stop at round 3, set the unit `blocked`, and say why.
7. On `approved`, write `.agent/assignments/<id>-tests.md` from
   `.agent/TEMPLATE-assignment.md`, and dispatch the tester with
   `.claude/agents/tester.md`.
8. **When the tester passes, dispatch the code reviewer again, in test-review mode**:
   "You are the code reviewer, in test-review mode. Read `.claude/agents/code-reviewer.md`
   and follow its section 'Test-review mode'. Skip its section 'Claude Code harness
   notes'. The assignment is `.agent/assignments/<id>.md`; the tester's entry is
   `<path>`. Write your entry from `.agent/TEMPLATE-review-entry.md`." **Why**: in the
   worktree pilot of 2026-10-08 every defect was in a test file, and no subagent had read
   a test.
9. On `changes_requested` from the test review, send the tester back to answer every
   finding by number, then run the test review again. Stop at round 3, set the unit
   `blocked`, and say why.
10. **When the test review approves, always do all of this:** run the gates in
    [docs/8-build/environment.md](docs/8-build/environment.md) with the empty-key prefix,
    commit the unit, write `## Handoff` at the end of the assignment with every commit
    hash, **commit the handoff**, set the unit `for acceptance`, and stop. **Never amend
    a commit**: a rework round is a new commit, so the record shows both rounds. Tell the
    user: "<id> is ready for the overall lead."

---

## The orchestrator does not write implementation code

It decomposes, dispatches, integrates and decides.

### Before dispatching

1. Read [STATUS.md](STATUS.md). Where the build stands, what is in flight, what the
   suite does today.
2. Read the target phase in [docs/8-build/phases.md](docs/8-build/phases.md) and its
   **done-criteria**.
3. Read [docs/INDEX.md](docs/INDEX.md) and open only the documents the unit needs.
4. Read `.agent/journal/INDEX.md` and any entry touching the files in scope.
5. Check [docs/9-reference/refactor-backlog.md](docs/9-reference/refactor-backlog.md)
   for items in the files the unit will touch. Name them in the assignment as either
   in scope or explicitly not.
6. Write an assignment at `.agent/assignments/<id>.md`.

**An assignment names: the objective, the exact file paths in scope, the done-criteria,
the citations the programmer needs, and what is explicitly out of scope.** A vague
assignment produces duplicated or missing work.

### Dispatching

Pass a **pointer**, not the content. The subagent reads the file itself.

**Subagents may run in parallel**, bounded by two rules:

1. **No two in-flight subagents touch the same file.** Check the **Files in scope**
   against every unit in flight — programmer, reviewer and tester alike. A reviewer in
   flight counts exactly as a programmer does. **Only the orchestrator has the whole
   picture**, so the disjoint-file assignment is its job and nobody else's.
2. **Dependency order is honoured.** `models/` before `analysis/`. Extraction before
   normalisation. Normalisation before projection.

The loop for **one** unit is always sequential:

```
programmer → code-reviewer → (revision → code-reviewer)* → tester
           → code-reviewer, test review → (tester revision → test review)*
```

### The review loop

**A programmer's report is a claim, not an acceptance.** Every programmer run goes to a
reviewer before the unit is accepted, before the tester, and before it is reported done.

Subagents cannot dispatch each other. **The orchestrator runs this loop.**

| Verdict | What the orchestrator does |
|---|---|
| `approved` | code review: log it; dispatch the tester. Test review: log it; run the gates; commit |
| `changes_requested` | re-dispatch the **programmer**, to answer every finding by number |
| `blocked` | fix what blocked the review, or escalate |

**Stop at round 3.** Three rounds means the assignment or the specification is wrong,
not the code. Escalate with both positions.

A programmer may dispute a finding. **A dispute needs a citation, in its log entry.** If
both sides cite and still disagree, escalate; do not pick a side.

### After a subagent returns

1. Read its log entry at the path it returned. The summary is a pointer; the entry is
   the record.
2. Append one line to `.agent/journal/INDEX.md`. **The orchestrator is its only
   writer**, which is what keeps it free of concurrent-append conflicts. With two
   teams, the build lead and the overall lead both write it, but never at the same
   time: the state in `.agent/QUEUE.md` says whose turn it is.
3. Decide: accept, re-dispatch, or escalate.
4. **When a unit is accepted, commit it.** Then, not at session end.
5. **Update [STATUS.md](STATUS.md) after the commit, in the same turn.** Re-measure;
   never carry a number forward.

Two rules bound the commit:

- **Never commit while a subagent is in flight.** A commit is a snapshot of the instant,
  so it would capture half-finished work and label it a passing unit.
- **A failing or blocked unit is still committed, and the message says so.** An honest
  record of a failure is worth more than a clean history.

### Escalate, do not decide alone

- Any `invariant_violation`.
- Any `spec_incomplete` — the filing or the docs cannot answer.
- A formula whose correct answer the tester cannot derive independently.
- A review that reaches round 3 without `approved`.
- A reviewer finding the programmer disputes, where both sides cite.
- **Any change to the LLM boundary** — a new field the model is asked to produce.

---

## The journal

**Subagents share no context. The filesystem is the only bus between them.**

```
.agent/
├── assignments/         one file per work unit, written by the orchestrator
├── QUEUE.md             the units in order, and whose turn each one is (two teams)
├── journal/
│   ├── INDEX.md         one line per entry — written by the lead whose turn it is (QUEUE.md)
│   └── <entry>.md       one file per entry — subagents write their own, never edit others'
├── TEMPLATE-assignment.md
├── TEMPLATE-log-entry.md      programmer and tester
└── TEMPLATE-review-entry.md   code_reviewer
```

Filenames are `YYYY-MM-DDTHHMM-<agent>-<slug>.md`. The reviewer's entries use
`code_reviewer`, with the underscore; its agent type is `code-reviewer`, because a
Claude Code agent name cannot hold one.

**Never append to a shared file from a subagent**; concurrent appends lose writes. A
review and the revision that answers it are **two entries**, never an edit of one.

**Every subagent writes exactly one entry before it finishes** — including when it
fails, is blocked, or finishes partially. An unlogged run is work that did not happen.

**Write the entry incrementally. Open it before the first command and update it as each
result lands.** An entry that is partial and honest survives a stop. A complete one that
is never written does not.
