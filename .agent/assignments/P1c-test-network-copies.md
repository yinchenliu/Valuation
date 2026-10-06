---
id: P1c-test-network-copies
phase: 1 — the gate on the Windows machine (part 3)
agent: tester
depends_on: [P1b-windows-gate]
---

# Two copies of the no-network rule still refuse the loopback address (item 93)

## Objective

**The fact.** `P1b-windows-gate` put one `_no_socket` fixture in `tests/conftest.py` and
deleted the four copies that differed only in the words of their message. It allows
`127.0.0.1`, `::1` and `localhost` and refuses every other address. The reason is
measured, not stylistic: on Windows `asyncio.ProactorEventLoop` builds its own self-pipe
with `socket.socketpair()`, which connects a socket to `127.0.0.1`, so a blanket refusal
broke that self-pipe and **thirteen tests failed for a reason that had nothing to do with
the product** (`tests/conftest.py:35-42`).

**Two more copies survive, and both carry the defect `P1b` fixed:**

| Where | What it patches | What it raises |
|---|---|---|
| `tests/unit/test_claude_extractor.py:637-654`, the `no_network` fixture | `socket.socket.connect` **and** `socket.create_connection`, with no loopback exception | `_NetworkReached(BaseException)` |
| `tests/unit/test_p14b_note_figures.py:645-647`, inside one test | `socket.socket.connect`, with no loopback exception | `RuntimeError` |

**Neither fails today.** Neither module builds an event loop, so neither reaches the
Windows self-pipe. That is why this is a latent defect and not a red test.

**What follows.** The rule "a unit test must not reach the network" now has three
definitions in this repository, and two of them are the version that is known to break on
this machine. The next test that adds a `TestClient` to either module will fail for a
reason its author cannot see. When this unit is done, there is one definition.

## What is already true — verify, do not redo

Measured by the overall lead at `1188891`, on the **Windows** machine
(`.venv/Scripts/python.exe`, Python 3.14.4), with `ANTHROPIC_API_KEY= GEMINI_API_KEY=`:

| Fact | Command | Result |
|---|---|---|
| gate | `-m pytest -q --ignore-glob="*_rule3_red.py"` | **1136 passed, 5 skipped, 0 failed** |
| full suite | `-m pytest -q` | **2 failed**, 1136 passed, 5 skipped. The 2 are red on purpose |
| lint | `-m ruff check .` | 4 errors, every one `BLE001` |
| types | the mypy command in `docs/8-build/environment.md`, with `pipeline.py` | 5 errors in 2 files |
| guard | `.claude/check_guard.py` | 48/48 |

**Facts about the code, each read today:**

| Fact | Where |
|---|---|
| The one fixture allows three loopback hosts and refuses everything else | `tests/conftest.py:56`, `LOOPBACK_HOSTS` |
| It patches three doors: `connect`, `connect_ex`, `create_connection` | `tests/conftest.py:51-53` |
| Two tests hold the fixture's contract in place, and without the first a no-op fixture would pass the whole suite | `tests/unit/test_routes.py`, `test_no_socket_refuses_an_address_that_leaves_the_machine` and `test_no_socket_allows_the_loopback_address` |
| Three modules apply the fixture with `pytestmark = pytest.mark.usefixtures("_no_socket")` | `P1b`'s own entry; `tests/unit/test_p3b_pipeline_stops.py:59` is a fourth |
| `no_network` does more than refuse sockets: it deletes two API key variables and replaces `ce._call_gemini` and `genai.Client.__init__` | `tests/unit/test_claude_extractor.py:643-654` |

**The socket patch is the backstop, not the guard**, in both places. The model-client
patches are what actually stop those tests calling a model. Do not delete the model-client
patches.

## What to do

1. **In `tests/unit/test_claude_extractor.py`:** keep the `no_network` fixture's key
   deletion and its two model-client patches. **Delete its two socket patches** and make
   the module use the one `_no_socket` fixture instead. Prefer
   `pytestmark = pytest.mark.usefixtures("_no_socket")` at module level, the shape the
   three other modules use.
2. **If `_NetworkReached` is then read by nothing, delete it.** If something still reads
   it, say what in your entry and leave it.
3. **In `tests/unit/test_p14b_note_figures.py`:** delete the in-test `_block_connect` and
   its `monkeypatch.setattr`. Make the module use `_no_socket` the same way. The test's
   docstring explains what it proves about route A; do not change what it asserts.
4. **Search `tests/` for any further copy** of the rule, not only these two. Report what
   you find, by file and line. A copy you find and leave is a finding; a copy you find and
   fix inside `tests/` is this unit's work.
5. **Prove the fixture is applied** to both changed modules, by execution. `P1b` used
   `-m pytest --setup-show` and counted the setups against the test count. Use the same
   measurement and give both numbers.
6. **Record what you find, do not widen your scope.** Items 91 and 40 (the dev scripts
   that run their own valuation sequence with the yfinance share count fallback) are in
   `tests/` and are **not** this unit's. Name them in your entry if you touch their files
   for any other reason.

## Files in scope

- `tests/unit/test_claude_extractor.py`
- `tests/unit/test_p14b_note_figures.py`
- `tests/conftest.py` — **only** if a changed module needs something the one fixture does
  not already give. Do not write a second fixture.

**Nothing else.** The write guard denies every path outside `tests/`.

## Out of scope

- **Every implementation file.** If a change cannot be made without editing one, that is
  a finding: write it in your entry and stop.
- **`tests/unit/test_routes.py`.** Its two contract tests are `P1b`'s and they must keep
  passing unchanged. That is criterion 6.
- **Items 91 and 40**, the seven dev scripts. Recorded, not this unit's.
- **Items 94 to 100.** Each is recorded in the backlog.

## Done-criteria

Run every command with `ANTHROPIC_API_KEY= GEMINI_API_KEY=` and
`.venv/Scripts/python.exe`. Never a bare `python`.

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | One definition of the rule | every match is in `tests/conftest.py` | `grep -rn "socket.socket, .connect\|socket, .create_connection\|socket.socket, .connect_ex" tests/` |
| 2 | The model-client guard survives | `_call_gemini` and `genai.Client` are still patched in `test_claude_extractor.py` | `grep -n "_call_gemini\|genai.Client" tests/unit/test_claude_extractor.py` |
| 3 | The fixture is applied to both changed modules | the setup count equals the test count, for each module | `-m pytest --setup-show <module>`, as `P1b` measured it |
| 4 | The gate is green | **1136 passed, 5 skipped, 0 failed**, or more passed if you add a test. **No new failing name** | `-m pytest -q --ignore-glob="*_rule3_red.py"` |
| 5 | The full suite shows only the two deliberate failures | 2 failed | `-m pytest -q` |
| 6 | `P1b`'s two contract tests still pass, unedited | 2 passed, and `git diff` shows no change to them | `-m pytest -q tests/unit/test_routes.py -k no_socket` and `git diff tests/unit/test_routes.py` |
| 7 | A no-op fixture is still reported | making `_no_socket` return without patching turns `test_no_socket_refuses_an_address_that_leaves_the_machine` red | the mutation, in a scratch copy; restore and prove it byte-identical |
| 8 | The two changed modules still refuse a real address | a test in each module that tries to connect to a non-loopback address fails | write one throwaway check, or exercise it through an existing test, and record the command |
| 9 | Lint | 4 errors, every one `BLE001`, and your changed files lint clean | `-m ruff check .` and `-m ruff check <your files>` |
| 10 | Nothing outside `tests/` changed | every path starts with `tests/` | `git status --porcelain` |

**Every criterion is a measurement, never an opinion.** Criterion 4 is a set comparison,
not a count: save the failing names before and after.

## Citations

- `.claude/agents/tester.md` — your role card, and the trap it opens with.
- `tests/conftest.py:23-49` — the one fixture, and the measured reason for the loopback
  exception.
- `docs/9-reference/refactor-backlog.md`, item 93 — the defect and its evidence.
- `.agent/journal/2026-10-05T1550-tester-P1b-windows-gate.md` — how `P1b` measured that
  the fixture was applied.

## Known open items

- Backlog item 75: the write guard reads text inside a Bash command as a file path and
  refuses a `>` or a heredoc. Write files with the Write tool.
- The suite takes about 135 seconds. Measure once, not after every edit.
- Backlog item 98: `runpy.run_path` executes a module into a fresh namespace, so a patch
  on that module object is not the name the fresh copy binds. Do not introduce one.

---

## Overall lead review, 2026-10-05

**Accepted.** The tester returned `pass`. I re-ran its measurements rather than reading
them, on the Windows machine with `ANTHROPIC_API_KEY= GEMINI_API_KEY=`:

| Criterion | My result |
|---|---|
| 1, one definition of the rule | `grep` over `tests/` gives three matches, all in `tests/conftest.py:105-107`. No socket patch survives anywhere else |
| 2, the model-client guard survives | `ce._call_gemini` and `genai.Client.__init__` are still patched, `tests/unit/test_claude_extractor.py:668-669` |
| 3, the fixture is applied | `--setup-show` counts **34 `_no_socket` setups against 34 tests** in `test_claude_extractor.py`, and **31 against 31 tests that run** in `test_p14b_note_figures.py`. Before this unit the counts were 0 and 1 |
| 4, gate | **1137 passed, 5 skipped, 0 failed.** The one extra pass over 1136 is the control test this unit added |
| 5, full suite | **2 failed**, and the two names are the two red on purpose |
| 9, lint | 4 errors, every one `BLE001` |
| 10, scope | `git status --porcelain` names `tests/unit/test_claude_extractor.py` and `tests/unit/test_p14b_note_figures.py` only. `git diff --stat tests/conftest.py` is empty, so the one fixture is untouched |

**Findings 1 to 3 accepted as reported.** `_NetworkReached` stays because three sites
still read it, and it is a `BaseException`, so no `except Exception` in `ingestion/` can
swallow it. That property belongs to the model-client rule, not to the socket rule.

**Findings 4 and 5 are recorded as backlog item 102.** The comment at
`tests/conftest.py:44-48` names two contract tests and there are three, and
`test_no_socket_allows_the_loopback_address` does not detect a fixture turned into a
no-op, because a loopback connection succeeds with no patch at all. Both are text, not
behaviour, and `tests/` is outside my own write scope.

**Finding 6 is not what it looked like, and I measured it.** The tester reported four
skips in `test_p14b_note_figures.py` as "real 10-K PDFs absent". For Chipotle and Okta
that is true: this machine holds ABBV, LHX and WMT only, nine PDFs. **For Walmart it is
false.** `tests/unit/test_p14b_note_figures.py:80` names
`10K_filings/Walmart/Walmart Inc._10-K_2026-01-31_English.pdf`, and the folder on this
machine is `10K_filings/WMT/`, which holds that exact file name. So a `skipif` guard
disables the real-filing check on a machine that holds the filing. `_REAL_LHX_PDF` misses
for a second reason: it names `..._10-K_2026-01-02_English.pdf` and the file on disk is
`..._10-K_2025_English.pdf`. Recorded as backlog item **101**, and it is the more serious
of the two: a test that skips reports neither pass nor fail.
