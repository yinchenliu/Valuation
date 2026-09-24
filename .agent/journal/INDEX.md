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
| 2026-09-21 | P5-web-routes | programmer | `ok` — 7 of 7. `GET /` 500 → 200; found two errors in the orchestrator's own documents | [entry](2026-09-21T0400-programmer-p5-web-routes.md) |
| 2026-09-21 | P5-web-routes | code_reviewer | **`approved`** — 2 minor. Settled a disputed finding against the programmer | [entry](2026-09-21T0500-code_reviewer-p5-web-routes.md) |
| 2026-09-21 | P5b-route-tests | tester | **`pass`** — 104 asserts over 4 routes. Proved the old suite blind. Escalated E1 and E2 | [entry](2026-09-21T0600-tester-p5b-route-tests.md) |
| 2026-09-21 | P4c-nan-stops | programmer | `ok` — items 20 and 14 closed. Found the NaN tax clamp | [entry](2026-09-21T0700-programmer-p4c-nan-stops.md) |
| 2026-09-21 | P4c-nan-stops | code_reviewer | **`approved`** — 5 notes. Built its own 23-case probe rather than re-running the programmer's | [entry](2026-09-21T0800-code_reviewer-p4c-nan-stops.md) |
| 2026-09-21 | P4d-cashflow-nan | programmer | `ok` — 8 of 8. Items 30 and 23b closed | [entry](2026-09-21T0900-programmer-p4d-cashflow-nan.md) |
| 2026-09-21 | P4d-cashflow-nan | code_reviewer | **`approved`** — 3 notes. Verified the dead-code argument by stack trace | [entry](2026-09-21T1000-code_reviewer-p4d-cashflow-nan.md) |
| 2026-09-22 | P6-honest-output | programmer, r1 | `ok` — cache keyed on content; four labels | [entry](2026-09-22T1400-programmer-p6-honest-output.md) |
| 2026-09-22 | P6-honest-output | code_reviewer, r1 | `changes_requested` — 2 major, **both the orchestrator's scope errors** | [entry](2026-09-22T1500-code_reviewer-p6-honest-output.md) |
| 2026-09-22 | P6-honest-output | programmer, r2 | `ok` — F1, F2, F6 answered; escalated a test collision rather than narrowing a check | [entry](2026-09-22T1600-programmer-p6-honest-output-r2.md) |
| 2026-09-22 | P6b-wacc-fixture | tester | **`pass`** — **rejected the binary the assignment gave it, and was right** | [entry](2026-09-22T1700-tester-p6b-wacc-fixture.md) |
| 2026-09-22 | P6 + P6b | code_reviewer | **`approved`** — measured all three open questions on a patched scratch tree | [entry](2026-09-22T1800-code_reviewer-p6-p6b.md) |
| 2026-09-22 | P7-low-confidence | programmer, r1 | `ok` — implements the user's 2026-09-22 decision | [entry](2026-09-22T1900-programmer-p7-low-confidence.md) |
| 2026-09-22 | P7-low-confidence | code_reviewer, r1 | `changes_requested` — 2 major: a `.get` the rewrite carried in, and a counterfactual wrong twice | [entry](2026-09-22T2000-code_reviewer-p7-low-confidence.md) |
| 2026-09-22 | P7-low-confidence | programmer, r2 | `ok` — **withdrew its own figure** and showed it cannot be recomputed | [entry](2026-09-22T2100-programmer-p7-low-confidence-r2.md) |
| 2026-09-22 | P7-low-confidence | code_reviewer, r2 | **`approved`** — **withdrew its own round-1 repair suggestion** | [entry](2026-09-22T2200-code_reviewer-p7-r2.md) |

`P2b-provider` is the first unit to take two review rounds. Round 1's `changes_requested`
was caused by **the assignment**, not the code: its file scope excluded the two lines
needed to prove a criterion the same assignment set. The orchestrator amended it rather
than asking the programmer to work around it.

`P1-suite` and `P2-hygiene` were accepted together at `d1854fb`, because they landed in
one working tree in parallel and no commit separates them. `P1b-arith` and `P1c-flow`
were accepted together for the same reason.

**A `fail` from a tester is a verdict about the code it tested, not about its own
deliverable.** Three units reported `fail` and all three were approved by review; two
reported `pass`. Read the verdict line at the top of an entry before reading the word
alone.

**Fifteen units, and not one was accepted on its own report.** Every programmer run went to
a reviewer that re-ran the measurements rather than reading them. Three times a reviewer
overturned a claim: it disproved a programmer's reason for stopping, it disproved a
different programmer's finding, and it confirmed two errors in the orchestrator's own
documents.
