---
id: P1b-windows-gate
phase: 1 — make the suite runnable
agent: tester
depends_on: [P3a-one-pipeline]
---

# The test gate runs on the Windows machine: 14 failures that no product defect causes

## Objective

**The fact.** On the Windows machine, `pytest -q --ignore-glob="*_rule3_red.py"` reports
**14 failed, 1090 passed, 5 skipped**. The same command on the macOS machine reported
**1109 passed, 0 failed** at `ac736e7`. Not one of the 14 names a defect in `models/`,
`analysis/`, `ingestion/`, `api/`, `cli.py` or `pipeline.py`.

**What follows.** The build moved to the Windows machine on 2026-10-05, and no unit can
be measured here until the gate is green here. Two causes produce all 14, and both are
in `tests/`.

1. **Thirteen** come from the `_no_socket` fixture. It replaces `socket.socket.connect`
   with a function that raises. On Windows, `asyncio.ProactorEventLoop` builds its
   self-pipe by connecting a socket to `127.0.0.1`, so every Starlette `TestClient`
   request after the patch returns **500**.
2. **One** comes from an argparse message that differs between Python versions.
   `tests/unit/test_p15a_two_routes.py:232` asserts `choose from 'gemini'`. Python
   3.11.6 (macOS) prints that. Python 3.14.4 (Windows) prints `choose from gemini`,
   with no quotation marks.

When this unit is done, the gate reports 0 failed on the Windows machine, the fixture
still refuses every connection that leaves the machine, and the argparse test still
proves that `-p claude` is refused.

## What is already true — verify, do not redo

Measured by the overall lead at `7a3955d`, on the **Windows** machine
(`.venv/Scripts/python.exe`, Python 3.14.4), with `ANTHROPIC_API_KEY= GEMINI_API_KEY=`:

| Fact | Command | Result |
|---|---|---|
| gate | `.venv/Scripts/python.exe -m pytest -q --ignore-glob="*_rule3_red.py"` | **14 failed, 1090 passed, 5 skipped** |
| lint | `.venv/Scripts/python.exe -m ruff check .` | 4 errors, every one `BLE001` |
| types | `.venv/Scripts/python.exe -m mypy models analysis ingestion api config.py app.py pipeline.py --ignore-missing-imports` | 6 errors in 3 files |
| census | the grep at `docs/2-rules/rules.md:102` | 64 |
| route | `TestClient(app.app, raise_server_exceptions=False).get('/')` | 200 |
| guard | `.venv/Scripts/python.exe .claude/check_guard.py` | 48/48 |

**The cause of the 13 is proved, with no repository code involved.** A trivial Starlette
app, a `TestClient`, and the fixture's three patches:

```
before patch: 200
after patch:  500
Exception ignored ... proactor_events.py, _close_self_pipe
AttributeError: 'ProactorEventLoop' object has no attribute '_ssock'
```

The 14 failing test names:

```
tests/unit/test_p15a_two_routes.py::test_cli_refuses_dash_p_claude                      (argparse)
tests/unit/test_pipeline.py::test_cli_and_web_report_the_same_implied_share_price        (socket)
tests/unit/test_pipeline.py::test_the_share_count_stop_reaches_the_web_result_page       (socket)
tests/unit/test_routes.py::test_get_assumptions_shows_the_confirm_zero_debt_checkbox_inside_the_valuation_form
tests/unit/test_routes.py::test_post_valuation_with_a_value_no_checkbox_sends_stops_and_names_it   (5 cases)
tests/unit/test_routes.py::test_post_valuation_with_the_box_checked_and_an_override_says_the_rate_reaches_nothing
tests/unit/test_routes.py::test_post_valuation_with_the_box_checked_values_the_company_with_no_debt
tests/unit/test_routes.py::test_post_valuation_with_the_box_unchecked_stops_at_item_22            (3 cases)
```

**Four copies of the fixture exist**, and they differ only in the words of the message:
`tests/unit/test_cli_overrides.py:36`, `tests/unit/test_p14d_finance_leases.py:71`,
`tests/unit/test_pipeline.py:75`, `tests/unit/test_routes.py:1056`.

**`tests/conftest.py` exists** and holds one autouse fixture that empties both API keys.

## What to do

1. **Write one `_no_socket` fixture in `tests/conftest.py`** and delete the four copies.
   One definition, because four copies of one rule go stale in three of them. Keep the
   fixture's name, so no test that requests it changes.
2. **Let the fixture allow a connection to the loopback address, and refuse every other
   address.** The reason is the measurement above: the Windows event loop connects to
   `127.0.0.1` to build its own self-pipe, and that connection never leaves the machine.
   Allow `127.0.0.1`, `::1` and `localhost`. Refuse everything else with the
   `AssertionError` the fixture raises today.
   **Do not delete the fixture and do not make it allow every address.** It is the only
   check that a unit test does not reach the network.
3. **Write one test that proves the fixture still refuses an outbound connection.** It
   requests `_no_socket`, calls `socket.socket().connect(("example.com", 80))`, and
   asserts that `AssertionError` is raised. Without it, a later change that turns the
   fixture into a no-op passes every test in the suite.
4. **Write one test that proves the fixture allows the loopback address**, so the reason
   for the allowance is on the record and a revert shows as a failing test.
5. **Repair `tests/unit/test_p15a_two_routes.py:232`** so it does not depend on the
   argparse wording. The test must still prove all three facts it proves today: exit
   code 2, `invalid choice: 'claude'`, and that the remaining choice is named `gemini`.
   Assert on a substring that both Python 3.11 and Python 3.14 print.
6. **Change no file outside `tests/`.** If the suite needs a change in
   `models/`, `analysis/`, `ingestion/`, `api/`, `cli.py`, `pipeline.py` or `app.py`,
   stop and report it. The write guard denies the write.

## Files in scope

- `tests/conftest.py`
- `tests/unit/test_routes.py`
- `tests/unit/test_pipeline.py`
- `tests/unit/test_cli_overrides.py`
- `tests/unit/test_p14d_finance_leases.py`
- `tests/unit/test_p15a_two_routes.py`

**Nothing else.** Work outside this list is a review finding, even if the change is good.

## Out of scope

- Every file outside `tests/`. The programmer of `P3b-pipeline-stops` is editing
  `cli.py`, `api/routes_valuation.py`, `ingestion/filings.py`,
  `ingestion/claude_extractor.py` and `pipeline.py` while you work. Do not read them for
  a fix and do not change them.
- The two tests that are red on purpose (`tests/unit/*_rule3_red.py`). They stay red.

## Done-criteria

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | The gate is green on this machine | `0 failed`, 1104 or more passed | `ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/Scripts/python.exe -m pytest -q --ignore-glob="*_rule3_red.py"` |
| 2 | The full suite shows only the two deliberate failures | `2 failed` | `ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/Scripts/python.exe -m pytest -q` |
| 3 | One definition of the fixture | `1` | `grep -rn "def _no_socket" tests/ \| wc -l` |
| 4 | The fixture refuses an address that leaves the machine | the new test passes | `... -m pytest -q tests/conftest.py tests/unit/test_routes.py -k "no_socket or loopback"` (name the exact node ids in your entry) |
| 5 | The fixture allows the loopback address | the new test passes | the same command |
| 6 | The argparse test passes and still proves the refusal | 1 passed | `... -m pytest -q tests/unit/test_p15a_two_routes.py::test_cli_refuses_dash_p_claude` |
| 7 | Nothing outside `tests/` changed | every path starts with `tests/` | `git status --porcelain` |
| 8 | A fixture turned into a no-op is caught | criterion 4's test fails | replace the fixture body with `return`, run criterion 4, record the failure, then restore |

**Every criterion is a measurement, never an opinion.**

## Citations

- `docs/2-rules/rules.md` — the six rules. Rule 3 is the one this fixture protects: a
  test that silently reached the network would read live market data.
- `.claude/agents/tester.md` — your role card, and the trap it opens with.
- `tests/conftest.py` — the existing home of a global fixture.
- CPython `asyncio/proactor_events.py`, `_close_self_pipe` — the Windows self-pipe that
  the patched `connect` breaks.

## Known open items

- Backlog item 75: the write guard reads text inside a Bash command as a file path, and
  refuses a `>` or a heredoc. Write files with the Write tool, not with a shell
  redirection.
- The suite takes about 135 seconds on this machine. Measure once, not after every edit.

## Backlog items this unit is NOT fixing

- **Item 40** — five dev scripts in `tests/` produce a price neither entry point would.
- **Item 91** — seven scripts in `tests/` run their own valuation sequence with the
  yfinance share count fallback that `P3a-one-pipeline` deleted.
- **Item 16** — nine scripts carry a `sys.path.insert` to a path that does not exist.

None of the three is in the six files above. Leave all three alone.
