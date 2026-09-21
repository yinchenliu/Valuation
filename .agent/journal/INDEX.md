# Journal index

One line per entry, appended by the orchestrator after a subagent returns.
**The orchestrator is its only writer** — that is what keeps this file free of
concurrent-append conflicts, and it is enforced by
`.claude/hooks/guard_paths.py` and sealed again at `SubagentStop`.

Entries themselves live beside this file as
`<YYYY-MM-DDTHHMM>-<agent>-<slug>.md`. A subagent writes its own entry and never
edits another's.

| Date | Unit | Agent | Verdict | Entry |
|---|---|---|---|---|
| 2026-09-20 | P1-suite | tester | `fail` — deliverable complete; the `fail` belongs to `analysis/dcf.py:80` | [entry](2026-09-20T2010-tester-p1-suite.md) |
| 2026-09-20 | P2-hygiene | programmer | `partial` — 8 of 9 criteria; the 9th needed a file outside its scope | [entry](2026-09-20T2010-programmer-p2-hygiene.md) |
| 2026-09-20 | P1-suite | code_reviewer | `approved` — 1 minor, 2 notes | [entry](2026-09-20T2100-code_reviewer-p1-suite.md) |
| 2026-09-20 | P2-hygiene | code_reviewer | `approved` — 3 notes, none citing a rule | [entry](2026-09-20T2100-code_reviewer-p2-hygiene.md) |
| 2026-09-20 | P1b-arith | tester | `fail` — deliverable complete; 6 stop paths in `analysis/` default instead of raising | [entry](2026-09-20T2145-tester-p1b-arith.md) |
| 2026-09-20 | P1c-flow | tester | `fail` — deliverable complete; found the normalizer sign error | [entry](2026-09-20T2145-tester-p1c-flow.md) |
| 2026-09-20 | P1b-arith | code_reviewer | `approved` — 1 minor, 2 notes. Confirmed the NaN chain end to end | [entry](2026-09-20T2215-code_reviewer-p1b-arith.md) |
| 2026-09-20 | P1c-flow | code_reviewer | `approved` — 5 notes. Confirmed the sign error and quantified it | [entry](2026-09-20T2215-code_reviewer-p1c-flow.md) |
| 2026-09-20 | P4-normalizer | programmer | `ok` — 9 of 9 criteria. Backlog items 19, 3 and 21 fixed | [entry](2026-09-20T2300-programmer-p4-normalizer.md) |
| 2026-09-20 | P4-normalizer | code_reviewer | `approved` — 1 minor, 2 notes. Re-derived all six signs two ways | [entry](2026-09-20T2330-code_reviewer-p4-normalizer.md) |
| 2026-09-21 | P4b-normalizer-verify | tester | **`pass`** — the first `pass` in this repository. Closed the gate defect, found item 25 | [entry](2026-09-21T0000-tester-p4b-normalizer-verify.md) |
| 2026-09-21 | P2b-provider | programmer, r1 | `partial` — extraction runs; found the web app returns 500 on every route | [entry](2026-09-21T0030-programmer-p2b-provider.md) |
| 2026-09-21 | P2b-provider | code_reviewer, r1 | `changes_requested` — 1 major. Disproved the blocking claim by execution | [entry](2026-09-21T0130-code_reviewer-p2b-provider.md) |
| 2026-09-21 | P2b-provider | programmer, r2 | `partial` — F1, F2, F4 answered; F3 escalated with the three lines that block it | [entry](2026-09-21T0200-programmer-p2b-provider-r2.md) |
| 2026-09-21 | P2b-provider | code_reviewer, r2 | **`approved`** — every finding reproduced. Corrected the orchestrator's backlog item 26 | [entry](2026-09-21T0300-code_reviewer-p2b-provider-r2.md) |

`P2b-provider` is the first unit to take two review rounds. Round 1's `changes_requested`
was caused by **the assignment**, not the code: its file scope excluded the two lines
needed to prove a criterion the same assignment set. The orchestrator amended it rather
than asking the programmer to work around it.

`P1-suite` and `P2-hygiene` were accepted together at `d1854fb`, because they landed in
one working tree in parallel and no commit separates them. `P1b-arith` and `P1c-flow`
were accepted together for the same reason.

**A `fail` from a tester is a verdict about the code it tested, not about its own
deliverable.** All four units were approved by review. Read the verdict line at the top
of each entry before reading the word alone.
