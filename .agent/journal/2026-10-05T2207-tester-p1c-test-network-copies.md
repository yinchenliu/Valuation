---
agent: tester
assignment: P1c-test-network-copies
round: 1
status: complete
files_touched: [tests/unit/test_claude_extractor.py, tests/unit/test_p14b_note_figures.py]
verdict: pass
---

# P1c-test-network-copies — the two surviving copies of the no-network rule are folded onto the one fixture

## What I did

Backlog item 93. `P1b-windows-gate` left one definition of "a unit test must not reach
the network" in `tests/conftest.py` (`_no_socket`), which allows `127.0.0.1`, `::1` and
`localhost` and refuses everything else. Two copies survived, both the blanket-refusal
version that `P1b` measured as the one that breaks the Windows `ProactorEventLoop`
self-pipe. I deleted both socket patches and applied the one fixture to each module with
`pytestmark = pytest.mark.usefixtures("_no_socket")`, the shape the four other modules
use. In `test_claude_extractor.py` the `no_network` fixture keeps its two key deletions
and both model-client patches — those are the guard; the socket patch was only ever the
backstop. In `test_p14b_note_figures.py` the in-test `_block_connect` and its
`monkeypatch.setattr` are gone. I added one test, in `test_p14b_note_figures.py`, so that
the module's fixture application is held in place by something that goes red when it is
removed; `test_claude_extractor.py` already had such a control test and I retargeted its
two socket assertions onto `_no_socket`'s contract. No implementation file was touched,
and `tests/conftest.py` is byte-identical to `HEAD`.

## Done-criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | One definition of the rule | **pass** | `grep -rn "socket.socket, .connect\|socket, .create_connection\|socket.socket, .connect_ex" tests/` → exactly 3 lines, all `tests/conftest.py:105`, `:106`, `:107`. Before this unit the same grep also hit `tests/unit/test_claude_extractor.py:652,653` and `tests/unit/test_p14b_note_figures.py:648`. |
| 2 | The model-client guard survives | **pass** | `grep -n "_call_gemini\|genai.Client" tests/unit/test_claude_extractor.py` → `668: monkeypatch.setattr(ce, "_call_gemini", _block)`, `669: monkeypatch.setattr(genai.Client, "__init__", _block)`, `807: genai.Client(api_key="not-a-key")` |
| 3 | The fixture is applied to both changed modules | **pass** | `-m pytest --setup-show -q <module>` counting `SETUP    F _no_socket`, against `--collect-only -q`. `test_claude_extractor.py`: **34 setups / 34 collected / 34 ran**. `test_p14b_note_figures.py`: **31 setups / 35 collected / 31 ran, 4 skipped**. The gap is exactly the four `skipif` tests that want real 10-K PDFs not on this machine (`-rs` names them: Walmart `:899`, Chipotle `:939`, Okta `:963`, L3Harris `:1007`); a skipped test sets up no fixture, so 31 setups is every test that ran. |
| 4 | The gate is green, no new failing name | **pass** | `-m pytest -q --ignore-glob="*_rule3_red.py"` → **1137 passed, 5 skipped, 0 failed** in 101.86s. Failing set before = failing set after = **∅**. One more passed than the lead's 1136, which is the one test I added. |
| 5 | Full suite shows only the two deliberate failures | **pass** | `-m pytest -q` → **2 failed, 1137 passed, 5 skipped** in 104.80s. See the set comparison in Measurements. |
| 6 | `P1b`'s contract tests still pass, unedited | **pass** | `-m pytest -q tests/unit/test_routes.py -k no_socket` → **3 passed, 37 deselected**. (The assignment said two; there are three — `..._refuses_an_address_that_leaves_the_machine`, `..._refuses_an_address_it_cannot_read`, `..._allows_the_loopback_address`.) `git diff --stat tests/unit/test_routes.py` → empty, and the file is absent from `git status --porcelain`. |
| 7 | A no-op fixture is still reported | **pass** | Mutation in place, then restored. See "The mutation" below. Under the mutation: `test_no_socket_refuses_an_address_that_leaves_the_machine` **FAILED**, `test_no_socket_refuses_an_address_it_cannot_read` **FAILED**, and both of my module control tests **FAILED** (`socket.gaierror: [Errno 11001] getaddrinfo failed` — the real resolver was reached, which is the point). `test_no_socket_allows_the_loopback_address` still passed, correctly: a no-op fixture still allows loopback. Restore proven byte-identical: `sha256sum tests/conftest.py` = `33a62ca96509687b053e781d3b1e5824ad24eab372b987c74885997894194092` before **and** after, and `git status --porcelain` does not list the file. |
| 8 | Both changed modules still refuse a real address | **pass** | Not a throwaway — one permanent test in each module. `-m pytest -q "tests/unit/test_claude_extractor.py::test_the_network_guard_fires" "tests/unit/test_p14b_note_figures.py::test_this_module_refuses_an_address_that_leaves_the_machine"` → **2 passed** with the fixture, **2 failed** with the fixture mutated to a no-op (criterion 7's run). Each asserts `connect`, `connect_ex` and `create_connection` against `192.0.2.1` (RFC 5737 TEST-NET-1) and `example.invalid` (RFC 2606), so a regression cannot put a packet on the wire. |
| 9 | Lint | **pass** | `-m ruff check .` → **Found 4 errors**, every one `BLE001` (`api/routes_valuation.py:451`, `:709`, `cli.py:1139`, `tests/test_e2e_all_googl.py:106`) — the same four the lead measured at `1188891`. `-m ruff check tests/unit/test_claude_extractor.py tests/unit/test_p14b_note_figures.py` → **All checks passed!** |
| 10 | Nothing outside `tests/` changed | **pass** | `git status --porcelain` → ` M tests/unit/test_claude_extractor.py`, ` M tests/unit/test_p14b_note_figures.py`, `?? .agent/assignments/P1c-test-network-copies.md` (the assignment, pre-existing and untracked, not mine). Every modified path starts with `tests/`. |

All commands prefixed `ANTHROPIC_API_KEY= GEMINI_API_KEY=` and run with
`.venv/Scripts/python.exe`. No bare `python` was used.

### The mutation (criterion 7)

`tests/conftest.py` was copied to `c:/tmp/conftest_p1c_backup.py`, the three
`monkeypatch.setattr` lines in `_no_socket` were replaced with
`_ = (_connect, _connect_ex, _create_connection)  # MUTATION: patches removed`, the four
tests above were run, then the backup was copied back. Both the SHA-256 and
`git status --porcelain` confirm the restore. This is the only reason I opened
`tests/conftest.py` for writing; its committed content is unchanged, so the assignment's
"do not write a second fixture" holds.

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| `pytestmark = pytest.mark.usefixtures("_no_socket")` at module level in both files | the shape `test_cli_overrides.py:35`, `test_p14d_finance_leases.py:71`, `test_pipeline.py:76` and `test_p3b_pipeline_stops.py:59` already use; assignment step 1 | A per-test `_no_socket: None` parameter would have left the rule applying to the one test it was written inside — which is exactly the defect in `test_p14b_note_figures.py` that this unit removes. |
| Kept `_NetworkReached` | assignment step 2: delete only if nothing reads it. It is still read by three sites: `tests/unit/test_claude_extractor.py:664` (raised by `no_network`'s `_block`), `:804` and `:806` (two `pytest.raises` in the control test, for `_call_llm` and `genai.Client`) | Deleting it would have forced the two model-client roads onto a plain `Exception`, and `_NetworkReached` is a `BaseException` precisely so no `except Exception` in `ingestion/` can swallow it. That property is load-bearing and is not `_no_socket`'s job. |
| Kept `import socket` in `test_p14b_note_figures.py` | the new control test uses it | Removing the import and then the only socket reference would have left criterion 8 unprovable in that module. Ruff is clean either way. |
| Added one permanent test rather than the "throwaway check" criterion 8 offers | criterion 8 allows either; a throwaway proves the fact once, on my machine, today | `test_p14b_note_figures.py` had no control test of its own. Without one, deleting the `pytestmark` I added leaves the whole module silently unguarded and every gate still green — the same shape of failure as backlog item 24. The test is the thing that notices. |
| Retargeted the two socket assertions in `test_the_network_guard_fires` from `_NetworkReached` to `AssertionError` | `_no_socket` raises `AssertionError` by its documented contract, `tests/conftest.py:88` and `:93` | Leaving them asserting `_NetworkReached` would have been a red test stating a requirement the one fixture deliberately does not meet; the exception type is the fixture's choice, not this module's. |
| Used `192.0.2.1` and `example.invalid` in both control tests | RFC 5737 TEST-NET-1 and RFC 2606 `.invalid` are guaranteed non-routable / non-resolvable | `example.com` would reach a real resolver if the fixture ever regressed. The mutation run showed exactly that boundary: `getaddrinfo failed`, not a connection. |

**No change was made to reach a target number.** The suite count moved from 1136 to 1137
because I added one test, and for no other reason.

## Rule 3 — what stops, and what does not

This unit reads no financial value and adds no formula; it is a test-infrastructure
fold. The rule 3 table is about the one input the changed code does read: the fixture
name. For completeness, the stop paths in scope:

| Value read | If it were missing | Evidence |
|---|---|---|
| the fixture name `"_no_socket"` in each `pytestmark` | pytest stops the module with `fixture '_no_socket' not found` — it never silently runs unguarded | pytest's own behaviour for `usefixtures` with an unknown name; the three other modules rely on the same |
| a non-loopback socket address, under `_no_socket` | stops, with `AssertionError` whose message names the address (`a unit test opened a network connection: {address!r}`) | `tests/conftest.py:93`, `:98`, `:103`; locked by `test_the_network_guard_fires` (matches `example.invalid`, `192.0.2.1`) and `test_this_module_refuses_an_address_that_leaves_the_machine` (same) |
| a model client, under `no_network` | stops, with `_NetworkReached`, a `BaseException` | `tests/unit/test_claude_extractor.py:664`; locked by `test_the_network_guard_fires` lines 804 and 806 |
| `GEMINI_API_KEY` / `GOOGLE_API_KEY`, under `no_network` | deleted, so any read stops rather than finding a live key | `tests/unit/test_claude_extractor.py:666-667`; the suite-wide `isolate_environment_keys` (`tests/conftest.py:11`) holds the same for every other test |

**No "defaults to" row.** No stop path in scope defaults, and I did not find one I could
not reach. I did **not** write any test that asserts a fallback.

## Measurements

Failure **sets**, not counts, both measured by me on this machine:

| | Full suite `-m pytest -q` | Gate `-m pytest -q --ignore-glob="*_rule3_red.py"` |
|---|---|---|
| **before** (working tree at `1188891`) | `{test_projector_rule3_red.py::test_an_extraction_with_no_income_statements_stops_and_names_the_input, test_routes_session_rule3_red.py::test_valuation_with_session_file_and_files_on_a_cache_hit_stops}` — 2 failed, 1136 passed, 5 skipped, 121.25s | not re-run before; lead measured 1136 passed, 5 skipped, 0 failed |
| **after** | the **same two names** — 2 failed, 1137 passed, 5 skipped, 104.80s | **1137 passed, 5 skipped, 0 failed**, 101.86s |

The set difference is empty in both directions. Both remaining failures are
`*_rule3_red.py`, red on purpose.

- Lint: 4 errors, every one `BLE001`, unchanged from `1188891`. My two files: clean.
- Guard: `.claude/check_guard.py` → **48/48 guard cases correct**, unchanged.
- Types: not re-run. The mypy command in `docs/8-build/environment.md` covers
  `models analysis ingestion api config.py app.py pipeline.py` and no file under
  `tests/`, so nothing this unit changed is inside its scope.
- Passed count moved 1136 → 1137: one added test, named above.

## Expected values — testers only

This unit asserts no financial figure, so no expectation here comes from arithmetic on a
filing. Every expectation is a **documented contract written before the run** — the
fixture's own docstring and raise sites in `tests/conftest.py`, which is the
specification for `_no_socket`, not the code under test in either module (that is
`ingestion/claude_extractor.py`). None was read off this run's output.

| Assertion | Expected | Where the expected value came from |
|---|---|---|
| `test_the_network_guard_fires`: `socket.create_connection(("example.invalid", 443))` | raises `AssertionError`, message contains `example.invalid` | contract: `tests/conftest.py:88` ("every other address raises `AssertionError`") and `:103` (`f"a unit test opened a network connection: {address!r}"`). `example.invalid` is not in `LOOPBACK_HOSTS` (`:56`), so `_is_loopback` is false by inspection. |
| `test_the_network_guard_fires`: `sock.connect(("192.0.2.1", 443))` | raises `AssertionError`, message contains `192.0.2.1` | same contract, `tests/conftest.py:93`. `_host_of(("192.0.2.1", 443))` returns `"192.0.2.1"` by the tuple branch at `:67-68`; it is not in `LOOPBACK_HOSTS`. |
| `test_the_network_guard_fires`: `sock.connect_ex(("192.0.2.1", 443))` | raises `AssertionError`, message contains `192.0.2.1` | same contract, `tests/conftest.py:98`. This is the third door; it had no coverage in this module before. |
| `test_the_network_guard_fires`: `_REAL_CALL_LLM(...)` | raises `_NetworkReached` | `no_network`'s own `_block` raises it unconditionally, `tests/unit/test_claude_extractor.py:664`. Assertion pre-existed and is unchanged. |
| `test_the_network_guard_fires`: `genai.Client(api_key="not-a-key")` | raises `_NetworkReached` | `monkeypatch.setattr(genai.Client, "__init__", _block)`, `:669`. Assertion pre-existed and is unchanged. |
| `test_this_module_refuses_an_address_that_leaves_the_machine`: all three doors | raises `AssertionError` naming the address | identical derivation to the three rows above, from `tests/conftest.py:88`, `:93`, `:98`, `:103`. |
| `test_route_a_retry_exhaustion_raises_value_error_on_unconfirmed_scale` | unchanged — 3 calls, and the three message fragments | **Not mine.** I deleted four lines of socket patching above the body and changed nothing it asserts, per assignment step 3. Its expected values are derived in its own docstring (MAX_RETRIES = 2, so 1 + 2 = 3 calls). |

**Two counts, with their units:**

- **Accuracy: 15 of 15 assertions** in the two control tests match an expectation derived
  from `_no_socket`'s written contract before the run — 9 in
  `test_the_network_guard_fires` (3 `pytest.raises` types + 2 message matches on the
  socket roads, over 5 road checks) and 6 in
  `test_this_module_refuses_an_address_that_leaves_the_machine` (3 types + 3 message
  matches). Counting `pytest.raises(..., match=...)` as two assertions, which is what it
  is. Zero mismatches.
- **Coverage: 3 of 3 patched doors, and 2 of 2 branches each.** `_no_socket` patches
  `connect`, `connect_ex` and `create_connection` (`tests/conftest.py:105-107`). Each now
  has its refuse branch exercised from **both** changed modules, and its loopback branch
  from `tests/unit/test_routes.py::test_no_socket_allows_the_loopback_address`
  (`P1b`'s, unedited). `_host_of`'s four shapes (tuple, bytes, str, `repr` fallback) are
  covered by `P1b`'s `test_no_socket_refuses_an_address_it_cannot_read`; I added no
  branch there and claim none. **Module-level coverage**, the number that matters for
  this unit: `_no_socket` setup runs on **34 of 34** tests in
  `test_claude_extractor.py` and **31 of 31** tests that run in
  `test_p14b_note_figures.py`. Before this unit the figure was 0 of 34 and 1 of 31.
- Line coverage of `analysis/` and `models/` was not measured: this unit changes no file
  under either, and the number would be `P1b`'s, not mine.

## What I did not do

- **Did not delete `_NetworkReached`.** Three sites still read it; listed above with line
  numbers. Assignment step 2 asked for exactly that report.
- **Did not touch `tests/unit/test_routes.py`.** Out of scope, and criterion 6 requires it
  unedited. Confirmed by an empty `git diff --stat`.
- **Did not touch items 91 and 40**, the seven dev scripts under `tests/` that run their
  own valuation sequence with the yfinance share count fallback. I opened none of their
  files for any reason. One of them, `tests/test_e2e_all_googl.py:106`, is the fourth
  `BLE001` in the lint count and stays exactly as it was.
- **Did not run the types gate.** Its command covers no path under `tests/`, so it cannot
  observe this unit. Saying "types pass" on the strength of a command that does not read
  my files would be an opinion dressed as a measurement.
- **Did not re-measure the gate before my edits.** I measured the full suite before
  (2 failed / 1136 passed / 5 skipped) and both suites after. The gate is the full suite
  minus the two `*_rule3_red.py` files, so its before-state follows from the full-suite
  before-run and the lead's figure at `1188891`; both agree at 1136.

## Findings for the orchestrator

1. **`_no_socket` was reaching 1 test in `test_p14b_note_figures.py`, not 31, and 0 in
   `test_claude_extractor.py`.** Both now reach every test in their module (34/34 and
   31/31, measured with `--setup-show`). This closes **backlog item 93** and I believe it
   can be marked done. The latent defect the item describes — the next `TestClient` added
   to either module failing on the Windows self-pipe — is now unreachable, because
   neither module can patch a socket.
2. **No third copy of the rule exists anywhere under `tests/`.** Searched for socket
   patching (`socket.socket, "connect"`, `"connect_ex"`, `socket, "create_connection"`),
   for `getaddrinfo`, `urlopen`, `requests.get/post`, `httpx`, and for fixtures named
   `no_network`, `block_network` or `offline`. Only `tests/conftest.py` patches a socket.
   The one surviving `no_network` name is `test_claude_extractor.py`'s model-client
   fixture, which is a different rule and correctly scoped.
3. **The assignment's criterion 6 says "`P1b`'s two contract tests"; there are three.**
   `tests/unit/test_routes.py` holds `test_no_socket_refuses_an_address_that_leaves_the_machine`,
   `test_no_socket_refuses_an_address_it_cannot_read` and
   `test_no_socket_allows_the_loopback_address`. All three pass unedited, so the criterion
   is met either way, but `tests/conftest.py:44-48` also names only two. That comment is
   one test out of date and sits in a file I must not change for content. Low severity;
   worth a one-line fix in a unit that already owns `conftest.py`.
4. **`test_no_socket_allows_the_loopback_address` does not fail when `_no_socket` is
   mutated to a no-op**, and correctly so — it asserts a connection succeeds, which it
   does with no patch at all. It is therefore not a mutation-detecting test on its own.
   The two refusal tests are what hold the contract. This is not a defect; it is a fact
   worth recording so nobody later reads the loopback test as the guard.
5. **Four tests in `test_p14b_note_figures.py` skip on this machine** because the real
   10-K PDFs are absent (`:899` Walmart, `:939` Chipotle, `:963` Okta, `:1007` L3Harris).
   They are 4 of the suite's 5 skips. Nothing in this unit changed that, but it means the
   real-filing assertions in that module are unexercised here and the `--setup-show`
   count for the module will stay at 31 until those PDFs are present.
