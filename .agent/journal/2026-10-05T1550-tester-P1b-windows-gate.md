---
agent: tester
assignment: P1b-windows-gate
round: 1
status: complete
files_touched: [tests/conftest.py, tests/unit/test_routes.py, tests/unit/test_pipeline.py, tests/unit/test_cli_overrides.py, tests/unit/test_p14d_finance_leases.py, tests/unit/test_p15a_two_routes.py]
verdict: pass
---

# P1b-windows-gate — the gate is green on the Windows machine, and the fixture still refuses the network

## What I did

The 14 failures had two causes and both were in `tests/`. Thirteen came from the
`_no_socket` fixture: it replaced `socket.socket.connect` with a function that raised
for every address, and on Windows `asyncio.ProactorEventLoop` builds its own self-pipe
with `socket.socketpair()`, which connects a socket to `127.0.0.1`. With that connection
refused, the loop's self-pipe never came up and every Starlette `TestClient` request made
after the patch returned 500. I replaced the four copies of the fixture with **one**
definition in `tests/conftest.py` that allows `127.0.0.1`, `::1` and `localhost` and
refuses every other address with the same `AssertionError` the copies raised, and gave
the three modules that had it autouse a `pytestmark = pytest.mark.usefixtures("_no_socket")`
so no test lost the refusal. Three new tests in `tests/unit/test_routes.py` hold both
halves of the fixture's contract in place. The fourteenth failure was argparse wording:
Python 3.11.6 prints `(choose from 'gemini')` and Python 3.14.4 prints
`(choose from gemini)`, so `tests/unit/test_p15a_two_routes.py:232` now matches
`r"choose from '?gemini'?\)"`, which both versions satisfy and which still goes red if a
second provider is ever accepted.

## Done-criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | The gate is green on this machine | **pass** | `ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/Scripts/python.exe -m pytest -q --ignore-glob="*_rule3_red.py"` → `1107 passed, 5 skipped, 2 warnings in 138.91s`. 0 failed; 1107 ≥ 1104 (1104 = the 1090 that passed plus the 14 that failed, plus the 3 tests this unit added) |
| 2 | The full suite shows only the two deliberate failures | **pass** | `... -m pytest -q` → `2 failed, 1107 passed, 5 skipped`. The two are `tests/unit/test_projector_rule3_red.py::test_an_extraction_with_no_income_statements_stops_and_names_the_input` and `tests/unit/test_routes_session_rule3_red.py::test_valuation_with_session_file_and_files_on_a_cache_hit_stops` |
| 3 | One definition of the fixture | **pass** | `grep -rn "def _no_socket" tests/ \| wc -l` → `1` (was 4) |
| 4 | The fixture refuses an address that leaves the machine | **pass** | `... -m pytest -q tests/conftest.py tests/unit/test_routes.py -k "no_socket or loopback"` → `3 passed, 37 deselected`. Node ids below |
| 5 | The fixture allows the loopback address | **pass** | the same command; node id below |
| 6 | The argparse test passes and still proves the refusal | **pass** | `... -m pytest -q tests/unit/test_p15a_two_routes.py::test_cli_refuses_dash_p_claude` → `1 passed`. All three facts still asserted: exit code 2, `invalid choice: 'claude'`, and that the remaining choice list is exactly `gemini` |
| 7 | Nothing outside `tests/` changed | **pass, with a caveat** | `git status --porcelain` lists 5 modified files outside `tests/` — `api/routes_valuation.py`, `cli.py`, `ingestion/claude_extractor.py`, `ingestion/filings.py`, `pipeline.py`. **None of them is mine**; they are the concurrent `P3b-pipeline-stops` programmer's, which the assignment's "Out of scope" section names. My six paths all start with `tests/`: `git diff --stat -- tests/` → 6 files, 224 insertions, 45 deletions |
| 8 | A fixture turned into a no-op is caught | **pass** | Inserted `return` as the first line of the fixture body in `tests/conftest.py`, ran criterion 4's command → `1 failed, 1 passed`: `FAILED tests/unit/test_routes.py::test_no_socket_refuses_an_address_that_leaves_the_machine` with `Failed: DID NOT RAISE AssertionError`. Removed the `return`; the same command then gave `2 passed`, and `git diff --stat tests/conftest.py` showed `93 insertions(+)` and no deletions, i.e. the original file is intact under the addition |

The exact node ids for criteria 4 and 5:

```
tests/unit/test_routes.py::test_no_socket_refuses_an_address_that_leaves_the_machine
tests/unit/test_routes.py::test_no_socket_refuses_an_address_it_cannot_read
tests/unit/test_routes.py::test_no_socket_allows_the_loopback_address
```

**A note on criterion 8 worth keeping.** Only the *refusal* test catches a no-op fixture.
The loopback test stays green against a no-op, because a no-op also allows loopback. That
is the right split — the refusal test is the one the assignment calls the guard — but it
means the loopback test must never be treated as the one that proves the fixture works.

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| `_no_socket` in `tests/conftest.py` is **not** `autouse` | It was autouse in three modules and an explicitly-requested fixture in `test_routes.py`. Making it globally autouse would newly apply it to `tests/test_e2e_*.py` and `tests/compare_models.py`, which are scripts that reach the network on purpose (`docs/5-testing/strategy.md` §4) | A global autouse would have changed the behaviour of files outside the six in scope, which is a review finding even when the change is good |
| The three formerly-autouse modules get `pytestmark = pytest.mark.usefixtures("_no_socket")` | Reproduces the exact scope the local autouse copy had, with no second definition of the fixture | A module-local wrapper fixture would have been a fifth place to keep in step, which is the defect this unit exists to remove |
| Allowed hosts are exactly `127.0.0.1`, `::1`, `localhost` | Assignment step 2. Each is an address that cannot leave the machine | Allowing all of `127.0.0.0/8`, or sniffing `ipaddress.is_loopback`, widens the hole for no measured need. Three literals are readable and auditable |
| An address shape the fixture cannot read is **refused**, not passed through | A fixture that is the only check against reaching the network must fail closed | Passing an unrecognised address to the real `connect` would make a future AF_UNIX or bytes-host call invisible to the check |
| The argparse assertion is a regex with an optional quote and a literal `)` | The only difference between 3.11.6 and 3.14.4 is the quoting; everything else in the message is stable | `assert "gemini" in stderr` would also pass on the usage line `[-p {gemini}]`, so it would stay green if argparse stopped printing the choice list at all. The trailing `)` keeps the assertion "the remaining choice list is exactly gemini" rather than "gemini appears somewhere" |
| The three new tests live in `tests/unit/test_routes.py` | It is in the assignment's "Files in scope" list and is the file criterion 4's command names | A new `tests/unit/test_conftest_no_socket.py` would read better but is outside the six files, which the assignment calls a review finding |

No change here was made to reach a target number. The fixture's allowance is the one
change that moved a count, and its reason is the measured Windows self-pipe, stated in
the assignment and reproduced in the comment block in `tests/conftest.py`.

## Rule 3 — what stops, and what does not

This unit reads one input: the socket address passed to `connect`, `connect_ex` or
`create_connection`. No financial figure passes through it.

| Value read | If it were missing | Evidence |
|---|---|---|
| the host of the socket address | **stops**: `AssertionError("a unit test opened a network connection: <address>")`, and the message carries the address itself | `tests/unit/test_routes.py::test_no_socket_refuses_an_address_that_leaves_the_machine` asserts `"example.com" in str(exc_info.value)` |
| an address with no readable host (a path, a bytes host, a non-text host) | **stops**: same `AssertionError`. It does not fall through to the real socket | `tests/unit/test_routes.py::test_no_socket_refuses_an_address_it_cannot_read` |
| `-p <provider>` on the CLI, given a value that is not a declared choice | **stops**: exit code 2, stderr names the rejected value and the full list of accepted ones | `tests/unit/test_p15a_two_routes.py::test_cli_refuses_dash_p_claude` |

No row says "defaults to". I found no stop path in scope that the code defaults past.

## Measurements

Failure sets, not counts.

**Before** (`.venv/Scripts/python.exe -m pytest -q --ignore-glob="*_rule3_red.py"`,
`14 failed, 1090 passed, 5 skipped in 132.52s`) — the set was exactly the 14 the
assignment names: `test_p15a_two_routes.py::test_cli_refuses_dash_p_claude`, two in
`test_pipeline.py`, and eleven in `test_routes.py` (`...confirm_zero_debt_checkbox...`,
`...no_checkbox_sends_stops_and_names_it` ×5, `...the_rate_reaches_nothing`,
`...values_the_company_with_no_debt`, `...stops_at_item_22` ×3).

**After** — the set is **empty**: `1107 passed, 5 skipped, 2 warnings in 138.91s`.

**Full suite after**: `2 failed, 1107 passed, 5 skipped`. The failure set is exactly the
two deliberate red tests, and both are genuinely red — checked per the role card's
standing instruction about backlog item 24, neither `*_rule3_red.py` file holds a test
that has quietly gone green and been left outside the gate.

**Lint**: `.venv/Scripts/python.exe -m ruff check .` → `Found 4 errors`, all `BLE001`, in
`api/routes_valuation.py` (×2), `cli.py` and `tests/test_e2e_all_googl.py`. Same as the
baseline the assignment records. My first edit introduced a fifth (`I001` in
`test_cli_overrides.py`, one blank line too many after the import block); it is fixed, and
`tests/` is clean.

**Types**: `.venv/Scripts/python.exe -m mypy models analysis ingestion api config.py app.py pipeline.py --ignore-missing-imports`
→ `Found 5 errors in 2 files`, against the assignment's baseline of 6 in 3. **I am not
claiming that movement.** This unit changed no file mypy checks; the concurrent
`P3b-pipeline-stops` programmer is editing five of them while I work, so the figure is
theirs to explain, not mine.

**Fixture setup, proved rather than assumed.** A `usefixtures` mark that silently failed
to apply would leave every test green and the network open, so I measured it with
`pytest --setup-show` and counted `SETUP    F _no_socket` lines against the tests that ran:

| Module | `_no_socket` setups | tests that ran |
|---|---|---|
| `tests/unit/test_cli_overrides.py` | 11 | 11 passed |
| `tests/unit/test_pipeline.py` | 17 | 17 passed |
| `tests/unit/test_p14d_finance_leases.py` | 25 | 25 passed, 1 skipped (a skipped test sets up no fixture) |

Every test that runs in those three modules still gets the refusal, exactly as it did
from the deleted autouse copies.

## Expected values — testers only

Twelve assertions, none of them a figure read off a run. Every expected value here comes
from a specification: the fixture's contract as written in the assignment
(`.agent/assignments/P1b-windows-gate.md`, step 2) and in `tests/conftest.py`, the Python
`socket` module's documented return contract, or `argparse`'s documented behaviour for an
invalid `choices` value together with `cli.py`'s declared choice list. No formula in
`analysis/` is in this unit's scope, so there is no hand arithmetic to show.

| Assertion | Expected | Where the expected value came from |
|---|---|---|
| `sock.connect(("example.com", 80))` raises | `AssertionError` | fixture contract: refuse every address that is not one of the three loopback hosts (assignment step 2; `tests/conftest.py` `_no_socket`) |
| the raised message contains the address | `"example.com"` | the fixture's own message text, specified as "refuse ... with the `AssertionError` the fixture raises today", which interpolates `address` |
| `socket.create_connection(("example.com", 80))` raises | `AssertionError` matching `example.com` | same contract, applied to the third patched entry point |
| `sock.connect_ex(("example.com", 80))` raises | `AssertionError` matching `example.com` | same contract, applied to the second patched entry point |
| `sock.connect("/tmp/p1b-no-such-socket")` raises | `AssertionError` | "allow three named hosts, refuse everything else" — a path is not one of the three, so the fixture must fail closed |
| `sock.connect((b"example.com", 80))` raises | `AssertionError` matching `example.com` | same; a bytes host is decoded for the message but is still not an allowed host |
| `sock.connect((1234, 80))` raises | `AssertionError` | same; a non-text host is not one of the three |
| `client_sock.connect(("127.0.0.1", <port>))` does not raise | completes | assignment step 2: "Allow `127.0.0.1`, `::1` and `localhost`" |
| `client_sock.getpeername()[0]` | `"127.0.0.1"` | the listener was bound to `("127.0.0.1", 0)` three lines earlier, so the peer of a socket connected to it is that address by construction — an identity, not a measurement |
| `ex_sock.connect_ex(address)` | `0` | CPython `socket` documentation: `connect_ex` "returns an error indicator ... 0 if the operation succeeded". The allowance means the operation succeeds, so the indicator is 0 |
| `made_sock.getpeername()[0]` via `create_connection` | `"127.0.0.1"` | the same construction identity as above |
| `re.search(r"choose from '?gemini'?\)", stderr)` matches | matches | `argparse`'s invalid-choice message prints the accepted choices in parentheses, and `cli.py` declares exactly one: `gemini`. The optional quote is the only thing that differs between 3.11.6 (`'gemini'`) and 3.14.4 (`gemini`); both wordings are stated in the assignment's §2 |

The two assertions already in the argparse test (`returncode == 2`,
`"invalid choice: 'claude'" in stderr`) are unchanged and came from argparse's documented
usage-error behaviour; I kept them.

**Two counts, with their units.**

- **Accuracy: 12 of 12 assertions match their independently derived expectation.** Zero
  of the twelve took its expected side from a run of the code under test. (I did run
  `argparse` in a scratch file under `c:/tmp/` to confirm the 3.14.4 wording the
  assignment states; that is stdlib formatting, not the unit under test, and the
  assertion is written to be independent of it either way.)
- **Coverage: 100% of what this unit added, measured.**
  `.venv/Scripts/python.exe -m coverage run --branch -m pytest -q tests/unit/test_routes.py -k "no_socket or loopback"`
  then `... -m coverage report -m --include="tests/conftest.py"`:

  ```
  Name                Stmts   Miss Branch BrPart  Cover   Missing
  tests\conftest.py      40      0     12      0   100%
  ```

  **40 of 40 statements and 12 of 12 branches**, from the three new tests alone.
  **6 of 6 functions**: `_host_of`, `_is_loopback`, `_no_socket`, and the three patched
  callables `_connect`, `_connect_ex`, `_create_connection` — each of the latter three on
  **both** its allow branch and its refuse branch, which is why the loopback test
  exercises all three entry points rather than just `connect`.

  `pytest --cov=tests/conftest.py` does **not** work for this: `conftest.py` is imported
  before the coverage plugin starts, so it reports `module-not-imported` and no data.
  `coverage run -m pytest` is the measurement that works.

  This unit added no code under `analysis/` or `models/`, so the role card's
  `--cov=analysis --cov=models` command measures nothing this unit changed and I did not
  cite it.

## What I did not do

- **I did not touch the five files outside `tests/` that `git status` shows as modified.**
  They belong to the concurrent `P3b-pipeline-stops` programmer. I did not read them for a
  fix and I am not reporting their state as a result of mine.
- **I did not fold the two other copies of the no-network rule onto the new fixture.**
  `tests/unit/test_claude_extractor.py:643` and `tests/unit/test_p14b_note_figures.py:645`
  patch the same three `socket` entry points under different fixture names and with
  different exception types (`_NetworkReached`, a `BaseException` subclass, and
  `RuntimeError`). Neither file is in this unit's six, so I left both alone. See the
  finding below.
- **I did not make the fixture globally autouse.** Reason in the decisions table.

## Findings for the orchestrator

1. **Two more copies of the no-network rule survive under other names, and both carry the
   same Windows defect this unit just fixed.**
   `tests/unit/test_claude_extractor.py:643` (raises `_NetworkReached`) and
   `tests/unit/test_p14b_note_figures.py:645` (raises `RuntimeError`) refuse *every*
   address, loopback included. Neither fails today only because neither module builds a
   Starlette `TestClient` or an asyncio event loop. The day either does, it fails on
   Windows for exactly the reason the 13 did. An assignment could say: fold both onto
   `tests/conftest.py::_no_socket`, keeping `test_claude_extractor.py`'s
   `BaseException`-derived type if the tests there rely on it not being swallowed by an
   `except Exception`. Neither file was in this unit's scope.
2. **The argparse-wording class of failure is not limited to the one test that was
   repaired.** Any assertion on a stdlib message's exact punctuation will break again when
   the interpreter moves. Worth a one-off grep for assertions on stdlib-generated text
   before the next interpreter bump; I did not run it, because it is outside the six files.
3. **`.agent/assignments/P1b-windows-gate.md` criterion 4's command names
   `tests/conftest.py` as a test path.** pytest collects nothing from it, so the command
   works only because `tests/unit/test_routes.py` is also on the line. Harmless, but a
   future reader may take it to mean the tests live in `conftest.py`. They live in
   `tests/unit/test_routes.py`, at the three node ids listed above.
