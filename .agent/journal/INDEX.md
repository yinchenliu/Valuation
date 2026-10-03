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
| 2026-09-25 | P8a-statements-data | programmer, r1 | `ok` — cache widened to four named fields; six context keys | [entry](2026-09-25T1149-programmer-p8a-statements-data.md) |
| 2026-09-25 | P8a-statements-data | code_reviewer, r1 | `changes_requested` — 1 major, **the orchestrator's error**: a two-sentence label cannot state this provenance | [entry](2026-09-25T1207-code_reviewer-p8a-statements-data.md) |
| 2026-09-25 | P8a-statements-data | programmer, r2 | `ok` — provenance moved into `derive_assumptions`; **overturned a done-criterion the orchestrator wrote** | [entry](2026-09-25T1217-programmer-p8a-statements-data-r2.md) |
| 2026-09-25 | P8a-statements-data | code_reviewer, r2 | **`approved`** — 2 notes. **Narrowed its own round-1 finding** after re-measuring | [entry](2026-09-25T1243-code_reviewer-p8a-r2.md) |
| 2026-09-26 | P8b-statements-ui | programmer | `ok` — 13 of 13 criteria; seven statement blocks rendered | [entry](2026-09-26T1716-programmer-p8b-statements-ui.md) |
| 2026-09-26 | P8b-statements-ui | code_reviewer | **`approved`** — 1 note on CapEx header. All 13 criteria verified | [entry](2026-09-26T1735-code_reviewer-p8b-statements-ui.md) |
| 2026-09-26 | P8b-statements-ui | tester | **`pass`** — 19 tests, 100 asserts over 7 blocks. Verified Rule 3 stops and badges | [entry](2026-09-26T1740-tester-p8b-statements-ui.md) |
| 2026-10-02 | P9a-session-route | programmer | `ok` — 12 of 12 criteria; same JSON gives equal statements and byte-equal prompts by both routes; mypy 14 → 10. **One possible paid API call** in a probe, because `.env` overrides `env -u` | [entry](2026-10-02T1630-programmer-p9a-session-route.md) |
| 2026-10-02 | P9a-session-route | code_reviewer | **`approved`** — round 1. Re-ran every criterion; loaded the `cde33cb` extractor beside the new one and found route A equal in 4 cases. F1 minor: Pass 2 shape and `NaN` amount not checked by the loader (→ `P9d`). Recorded the silent PDF drop as backlog item 49 | [entry](2026-10-02T1654-code_reviewer-p9a-session-route.md) |
| 2026-10-02 | P9b-session-web | programmer | `ok` — 8 of 8; `/upload-session`, the label recorded at extraction time in a fifth cache field, one `_run_extraction`; closed backlog item 29 at no extra cost | [entry](2026-10-02T1658-programmer-p9b-session-web.md) |
| 2026-10-02 | P9c-parse-tests | tester | `fail` **about the code, not the tests** — 156 new tests pass in the gate; 3 red cases lock review F1 for `P9d`. Six mutations each turned 1 to 11 tests red. Found items 50 and 51 | [entry](2026-10-02T1658-tester-p9c-parse-tests.md) |
| 2026-10-02 | P9b-session-web | code_reviewer | **`approved`** — round 1, all 8 criteria re-run with every paid call stubbed. F1 minor: a cache hit ignores `files` sent with `session_file` (backlog item 52) | [entry](2026-10-02T1710-code_reviewer-p9b-session-web.md) |
| 2026-10-02 | P9d-pass2-checks | programmer | `ok` — 3 red cases pass; the loader checks Pass 2 shape, 8 keys, finite numeric `amount`, integer `year`; F2's two `.get` reads removed | [entry](2026-10-02T1713-programmer-p9d-pass2-checks.md) |
| 2026-10-02 | P9b-route-tests | tester | `fail` **about the code** — 23 route tests pass; `api/` 86% → 97%; 11 mutations each turned a test red. 1 red test locks backlog item 52 | [entry](2026-10-02T1713-tester-p9b-route-tests.md) |
| 2026-10-02 | P9d-pass2-checks | code_reviewer | **`approved`** — round 1; failing-test sets compared against `dce8d42`; 19 malformed Walmart copies probed. F1 minor: `_NRI_SCHEMA` imported by its private name (backlog item 53) | [entry](2026-10-02T1720-code_reviewer-p9d-pass2-checks.md) |
| 2026-10-02 | P9d-tests | tester, run 1 | **stopped by the API usage limit** before its first change. `git status` showed no test file touched; the entry was only opened. Re-dispatched as run 2 | [entry](2026-10-02T1724-tester-p9d-tests.md) |
| 2026-10-02 | P9d-tests | tester, run 2 | **`pass`** — 3 green tests moved out of the red file, which is deleted; 18 new cases lock every `P9d` stop; 8 mutations each turned a new test red. Gate 376 → 397 passed | [entry](2026-10-02T2101-tester-p9d-tests-run2.md) |
| 2026-10-02 | P10b-capm-variance | programmer | `ok` — constant-market stop moved before `linregress`; identity test, because `np.var([0.01]*12)` is 3.0e-36; gate 398 passed, 0 failed | [entry](2026-10-02T2127-programmer-p10b-capm-variance.md) |
| 2026-10-02 | P10b-capm-variance | code_reviewer | **`approved`** — round 1, compared by name in a `54c966f` archive. F1 minor: the NaN message still blames the market (item 55) | [entry](2026-10-02T2130-code_reviewer-p10b-capm-variance.md) |
| 2026-10-02 | P10a-nci-bridge | programmer, r1 | `ok` — one summed NCI key; `run_dcf` stops on `None`; item 2's red test passes (rule 3 over the assignment); 31 fixtures red | [entry](2026-10-02T2127-programmer-p10a-nci-bridge.md) |
| 2026-10-02 | P10a-nci-bridge | code_reviewer, r1 | `changes_requested` — **F1 major, the orchestrator's error**: the assignment asked the model to add two printed lines (rule 1). Upheld the item 2 departure | [entry](2026-10-02T2139-code_reviewer-p10a-nci-bridge.md) |
| 2026-10-02 | P10a-nci-bridge | programmer, r2 | `ok` — two printed keys, sum in `total_noncontrolling_interest`; item 2's dead lines deleted, census 116 → 114 | [entry](2026-10-02T2141-programmer-p10a-nci-bridge-r2.md) |
| 2026-10-02 | P10a-nci-bridge | code_reviewer, r2 | **`approved`** — all round 1 findings closed; no double count (293 in other NCL, 6,270 in equity) | [entry](2026-10-02T2148-code_reviewer-p10a-nci-bridge-r2.md) |
| 2026-10-02 | P10c-fiscal-year | programmer | `ok`, 7 of 8 — filename year verified against cover date and column label; LHX stops on 2 filings; 5 fixtures red by step 2's stop | [entry](2026-10-02T2127-programmer-p10c-fiscal-year.md) |
| 2026-10-02 | P10c-fiscal-year | code_reviewer, r1 | `changes_requested` — F1 major: an unreachable `or ""` (rule 3). F2: **the orchestrator's rule** stops Target-style filers; decided: a printed bare-year label wins within one year of the cover | [entry](2026-10-02T2150-code_reviewer-p10c-fiscal-year.md) |
| 2026-10-02 | P10c-fiscal-year | programmer, r2 | `ok` — a printed bare-year label wins within the cover year or the year before (Target-style → 2024); two headings; web remedy = rename and upload | [entry](2026-10-02T2153-programmer-p10c-fiscal-year-r2.md) |
| 2026-10-02 | P10c-fiscal-year | code_reviewer, r2 | **`approved`** — all round 1 findings closed; failing sets compared in `1089c90` archives. Notes F7 (10-Q upload, item 57), F8 (unquoted remedy, item 58) | [entry](2026-10-02T2203-code_reviewer-p10c-fiscal-year-r2.md) |
| 2026-10-02 | P10-tests | tester | **`pass`** — 36 fixtures repaired with explicit values, no stop weakened; item 2's test moved out of the red file; 96 new cases; 14 mutations each turned 1 to 15 tests red. Gate 495 passed, 0 failed | [entry](2026-10-02T2205-tester-p10-tests.md) |
| 2026-10-02 | P11a-printed-lines | programmer, run 1 | **stopped by the API usage limit** before its first change; `git status` showed only the opened entry. Re-dispatched as run 2 | [entry](2026-10-02T2233-programmer-p11a-printed-lines.md) |




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
