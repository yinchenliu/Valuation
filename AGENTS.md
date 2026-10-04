# Who does the work

**Read [docs/0-start.md](docs/0-start.md) first.** Codex, OpenCode and the other tools
that follow the `AGENTS.md` convention load this file and never load `CLAUDE.md`, so
that card is your only orientation. It holds the reading order, the one command you
need, and the four facts that change how you read the code.

Build a DCF valuation platform that reads 10-K/10-Q filings. **What** to build and
**why** is in [docs/INDEX.md](docs/INDEX.md). **How far it has got** is in
[STATUS.md](STATUS.md). This file governs **who does the work and how they hand off.**

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
the write, and `.claude/check_guard.py` holds the 48 cases it must get right.

The reviewer answers a different question from the tester. The reviewer asks *is this
code correct and rule-compliant*. The tester asks *does each number equal what the
formula gives for inputs whose answer was known before the code ran*. Both must be
answered, and **neither may edit the code it judges.**

**There is no benchmark in this repository.** No trustee, no signed reference file, no
published figure. That makes the tester's expected values the weakest link in the whole
build, and it is why `.claude/agents/tester.md` spends its first section on one trap:
running the code, reading the output, and asserting that. A test written that way
verifies nothing and passes forever.

### A builder outside Claude Code (Antigravity, from 2026-10-04)

**The user's decision of 2026-10-04:** Antigravity, with Gemini, builds. The Claude Code
session stays the orchestrator: it writes assignments, reviews, commits and reports.

**The write guard and the seal are Claude Code hooks. They do not run in Antigravity.**
So no permission stops a Gemini run from writing outside its role. The split above then
holds only if each run keeps to these rules, and the orchestrator checks the diff.

1. **One conversation, one role, one unit.** Start a new conversation for each run. A
   programmer run and the tester run of the same unit are never one conversation.
2. **Read your role card first.** A programmer reads `.claude/agents/programmer.md`. A
   tester reads `.claude/agents/tester.md`. They are plain text. Skip their "Claude Code
   harness notes" section.
3. **Write only the files your role may write.** A programmer writes the assignment's
   **Files in scope** and its own journal entry. A tester writes `tests/` and its own
   journal entry. Nothing else.
4. **Never write** `STATUS.md`, `.agent/journal/INDEX.md`, `.agent/assignments/`,
   `.claude/` or `extractions/`. The orchestrator owns them.
5. **Never commit, and never review your own unit.** Stop when your journal entry is
   written. The orchestrator reviews the diff, re-runs the done-criteria, commits, and
   logs the line in `.agent/journal/INDEX.md`.
6. **A tester starts only after the orchestrator records `approved`** for the unit in
   `.agent/journal/INDEX.md`.
7. **Make no paid API call.** Run every command with the keys empty, for example
   `ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python -m pytest -q`. Never a bare
   `python` ([docs/0-start.md](docs/0-start.md)).
8. **If an instruction conflicts with a rule or with the code, stop and say so in your
   entry.** Do not work around it. The orchestrator answers in the assignment, under a
   heading `## Orchestrator notes`.

**The orchestrator rejects a run whose `git status` shows a file outside its role**,
whatever the quality of the change.

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
```

### The review loop

**A programmer's report is a claim, not an acceptance.** Every programmer run goes to a
reviewer before the unit is accepted, before the tester, and before it is reported done.

Subagents cannot dispatch each other. **The orchestrator runs this loop.**

| Verdict | What the orchestrator does |
|---|---|
| `approved` | accept; log it; dispatch the tester |
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
   writer**, which is what keeps it free of concurrent-append conflicts.
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
├── journal/
│   ├── INDEX.md         one line per entry — the orchestrator is the sole writer
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
