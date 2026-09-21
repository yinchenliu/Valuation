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

`P1-suite` and `P2-hygiene` were accepted together at `d1854fb`, because they landed in
one working tree in parallel and no commit separates them. `P1b-arith` and `P1c-flow`
were accepted together for the same reason.

**A `fail` from a tester is a verdict about the code it tested, not about its own
deliverable.** All four units were approved by review. Read the verdict line at the top
of each entry before reading the word alone.
