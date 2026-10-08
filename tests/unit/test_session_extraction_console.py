"""The console `session_extraction` prints through: it may not lose a character.

`ingestion/session_extraction.main` puts one error handler, `namereplace`, on
`sys.stdout` and `sys.stderr` before it parses argv
(`name_unencodable_characters`, `ingestion/session_extraction.py:1172-1196`).
Backlog item 113: on a cp1252 console `prompt --filing 0 --pass 2` raised
`UnicodeEncodeError` on the `U+2192 RIGHTWARDS ARROW` the Pass 2 prompt prints in
its two `direction` rules (`ingestion/claude_extractor.py:412-413`), so route B's
reader could not see the prompt at all.

**Where every expected value in this file comes from.** Not one of them was read
off this code's output.

1. **The `namereplace` contract**, from the standard library's error-handler
   table (`codecs`, "Error Handlers"): a character the target encoding cannot hold
   is written as `\\N{` + the character's Unicode name + `}`. The Unicode name of
   `U+2192` is `RIGHTWARDS ARROW`, from the Unicode character database. So
   `'→'.encode('cp1252', 'namereplace')` is `b'\\\\N{RIGHTWARDS ARROW}'` by the two
   specifications together, before anything here runs.
2. **The cp1252 code chart**: `U+2014 EM DASH` is byte `0x97` and
   `U+2026 HORIZONTAL ELLIPSIS` is byte `0x85`. Both are *in* cp1252, so no error
   handler may touch them — that is the whole reason the other five subcommands
   already worked.
3. **The UTF-8 encoding rule**: `U+2192` is `0b0010_0001_1001_0010`, which a
   three-byte UTF-8 sequence carries as `1110_0010 10_000110 10_010010` =
   `b'\\xe2\\x86\\x92'`. A UTF-8 console must therefore still print the arrow itself.
4. **Two identities**, which hold whatever the prompt says:
   - every unencodable character in the prompt appears, named, exactly once in the
     rendered output — nothing is dropped and nothing is doubled;
   - `cmd_prompt` prints five framing lines around the two prompts, so the output
     is `len(system lines) + len(user lines) + 5` lines. A run that stops part way
     through, as item 113's did, cannot satisfy it.
5. **Two digests measured in the tree before this unit existed**
   (`git archive 0bc41a1`, which is `session_extraction.py` at `2730e033…`): the
   Pass 1 and Pass 2 *system* prompts. Both are module constants
   (`_pass1_prompt_pair` / `_pass2_prompt_pair` return `_FINANCIALS_SYSTEM_PROMPT`
   and `_NRI_SYSTEM_PROMPT` unchanged), so one digest each pins the LLM boundary
   for every filing. Each is asserted non-empty before it is compared, because two
   empty results are not a match.

**Where the handler is read, and why that is not after `main()` returns.** Until
`P1e-test-order`, `main()` set a handler on the process-global `sys.stdout` and
never put it back, and `_pytest.capture.CaptureIO` is an `io.TextIOWrapper`
subclass, so an in-process call leaked `errors='namereplace'` into every test
that ran afterwards (backlog item 124). That is closed:
`naming_unencodable_characters` reads each stream's handler, sets `namereplace`
for the body, and restores it in a `finally`. **So this file reads the handler
while the command is running, never after it has finished.** A test that found
`namereplace` on the caller's stream after `main()` returned would be asserting
that item 124 is back; the three tests in section 2 read it from inside instead,
at every write and at the first statement of `main`'s body.

**What each test owns.** Section 2 builds its own `io.TextIOWrapper` over a
`BytesIO` — the class a console stream is, and the class `CaptureIO` is — and
installs it through `monkeypatch`, which puts the real stream back whatever
happens. Sections 3 and 4 run `main` in a **subprocess**, because a subprocess is
the only way to see a *real* console encoding (`PYTHONIOENCODING`) and a real
inherited `sys.stdout`; those tests stay.
`test_main_leaves_a_real_process_stream_as_it_found_it` is a subprocess for the
same reason. No test here leaves a process-global changed, so the order they run
in cannot change a result.

**No test here reaches the API, the network or a real filing.** The session file
and its PDF are built under `tmp_path` by the builders in
`tests/unit/test_session_extraction.py`, and every subprocess is given empty API
keys.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from ingestion.claude_extractor import (
    parse_pass1,
    pass1_prompts,
    pass2_prompts,
    plan_filings,
)
from ingestion.session_extraction import (
    _build_parser,
    main,
    naming_unencodable_characters,
)
from tests.unit.test_session_extraction import COMPANY, TICKER, one_filing, write

REPO_ROOT = Path(__file__).resolve().parents[2]

# Source 1: the Unicode name of U+2192, and the `namereplace` escape format.
ARROW = "→"
NAMED_ARROW = "\\N{RIGHTWARDS ARROW}"

# Source 2: the cp1252 code chart.
CP1252_EM_DASH = b"\x97"
CP1252_ELLIPSIS = b"\x85"

# Source 3: the UTF-8 encoding rule applied to U+2192 by hand.
UTF8_ARROW = b"\xe2\x86\x92"

# Source 5: measured in `git archive 0bc41a1`, the tree without this unit's code.
PASS1_SYSTEM_LENGTH = 11437
PASS1_SYSTEM_SHA256 = "f1ff5987e972f5015305353eb68dd0f26285fe72de2576ccaf008496624f6d67"
PASS2_SYSTEM_LENGTH = 3317
PASS2_SYSTEM_SHA256 = "843ce6e79ea264ca15aee431bae877e2bf78d8c3d9bfb6c387d0325f9c863e7a"
PASS2_SYSTEM_ARROWS = 2

# Source 6: the same error-handler table, for the handler these tests put on a
# stream *before* they hand it to the unit. `xmlcharrefreplace` writes a character
# the encoding cannot hold as `&#<decimal code point>;`, and U+2192 in decimal is
# 2*4096 + 1*256 + 9*16 + 2 = 8192 + 256 + 144 + 2 = 8594, so it renders the arrow
# as `&#8594;`. It is chosen because **nothing in the unit ever sets it**: a stream
# that reads `xmlcharrefreplace` after a call can only have had its handler put
# back, and a byte sequence that spells `&#8594;` can only have been written
# through the caller's own handler.
CALLER_HANDLER = "xmlcharrefreplace"
XMLCHARREF_ARROW = b"&#8594;"


# ===========================================================================
# Helpers. Each test owns the stream it configures.
# ===========================================================================

def wrapper(encoding: str) -> tuple[io.BytesIO, io.TextIOWrapper]:
    """A text stream of this encoding over bytes the test can read back.

    `io.TextIOWrapper` is what `sys.stdout` is on a console and down a pipe, so
    this is the object the unit's `isinstance` test is about — built here, never
    taken from the process.
    """
    raw = io.BytesIO()
    return raw, io.TextIOWrapper(raw, encoding=encoding, newline="\n")


def written(raw: io.BytesIO, stream: io.TextIOWrapper, text: str) -> bytes:
    stream.write(text)
    stream.flush()
    return raw.getvalue()


def owned_stream(encoding: str = "cp1252",
                 handler: str = CALLER_HANDLER) -> io.TextIOWrapper:
    """A text stream this test owns, carrying a handler of the test's choosing.

    The handler is an argument because the question every restore test asks is
    "did the stream leave with what it arrived with", and the answer is only
    readable when the test, not Python and not the unit, decided what that was.
    """
    return io.TextIOWrapper(io.BytesIO(), encoding=encoding, errors=handler,
                            newline="\n")


class RecordingStream(io.TextIOWrapper):
    """A `TextIOWrapper` that records `(encoding, errors)` at every `write`.

    This is what moves the observation **inside** the run. The handler that
    matters is the one in force at the moment a character is encoded — a
    `TextIOWrapper` encodes in `write` — and not the one left on the stream
    afterwards, which is the caller's and which backlog item 124 was about.

    `_pytest.capture.CaptureIO` is an `io.TextIOWrapper` subclass and so is this,
    so the object under the test is the same kind of object a console is.
    """

    def __init__(self, encoding: str) -> None:
        super().__init__(io.BytesIO(), encoding=encoding, errors=CALLER_HANDLER,
                         newline="\n")
        self.states: list[tuple[str, str | None]] = []

    def write(self, text: str) -> int:
        self.states.append((self.encoding, self.errors))
        return super().write(text)


def recording_streams(monkeypatch: pytest.MonkeyPatch,
                      encoding: str) -> tuple[RecordingStream, RecordingStream]:
    """Install a recording stdout and stderr for the length of one test.

    `monkeypatch` puts the real pair back however the test ends, so a broken
    restore inside the unit cannot reach another test even while it is being
    measured.
    """
    out, err = RecordingStream(encoding), RecordingStream(encoding)
    monkeypatch.setattr(sys, "stdout", out)
    monkeypatch.setattr(sys, "stderr", err)
    return out, err


def rendered(stream: RecordingStream) -> bytes:
    """The bytes that reached the buffer under a recording stream."""
    stream.flush()
    raw = stream.buffer
    assert isinstance(raw, io.BytesIO)
    return raw.getvalue()


def handler_spy(
    monkeypatch: pytest.MonkeyPatch,
) -> list[tuple[str | None, str | None]]:
    """Record both handlers at the first statement of `main`'s body.

    `main` evaluates `_build_parser()` and only then `parse_args(argv)`, so a spy
    here reads the two handlers from **inside** the `with` block and **before**
    argv is parsed. It returns the real parser, so the command it is spying on
    runs exactly as it would without it: this is a spy, not a stub.

    `_build_parser` is bound in this module at import, so the name below is still
    the real function after `monkeypatch` has replaced the module's attribute.
    """
    seen: list[tuple[str | None, str | None]] = []

    def spy() -> argparse.ArgumentParser:
        seen.append((sys.stdout.errors, sys.stderr.errors))
        return _build_parser()

    monkeypatch.setattr("ingestion.session_extraction._build_parser", spy)
    return seen


def child(args: list[str], env_overrides: dict[str, str],
          cwd: Path | None = None) -> subprocess.CompletedProcess[bytes]:
    """Run a child Python with the API boundary closed. Bytes, never decoded text.

    `capture_output` gives the child two pipes, so its `sys.stdout` is a
    `TextIOWrapper` exactly as a console is. The output is kept as bytes: the
    question this file asks is what reached the console, and decoding it here
    would hide a lost character.
    """
    env = {**os.environ, "ANTHROPIC_API_KEY": "", "GEMINI_API_KEY": "",
           **env_overrides}
    return subprocess.run(
        [sys.executable, *args],
        cwd=str(cwd or REPO_ROOT), env=env, capture_output=True, check=False,
    )


RECORD_STREAMS = (
    "import json, sys\n"
    "from ingestion.session_extraction import main\n"
    "before = (sys.stdout.encoding, sys.stderr.encoding)\n"
    "errors_before = [sys.stdout.errors, sys.stderr.errors]\n"
    "argv = json.loads(sys.argv[1])\n"
    "try:\n"
    "    code = main(argv)\n"
    "except SystemExit as exc:\n"
    "    code = exc.code\n"
    "record = {'before': list(before),\n"
    "          'after': [sys.stdout.encoding, sys.stderr.encoding],\n"
    "          'errors_before': errors_before,\n"
    "          'errors': [sys.stdout.errors, sys.stderr.errors],\n"
    "          'code': code}\n"
    "open(sys.argv[2], 'w', encoding='utf-8').write(json.dumps(record))\n"
)


def run_main_and_record(argv: list[str], record: Path,
                        encoding: str) -> dict[str, Any]:
    """Call `main` in a subprocess and read back what it did to that process's streams."""
    result = child(["-c", RECORD_STREAMS, json.dumps(argv), str(record)],
                   {"PYTHONIOENCODING": encoding})
    assert record.exists(), (
        f"the child never got as far as recording: {result.stderr!r}")
    return json.loads(record.read_text(encoding="utf-8"))


def session_with_one_filing(tmp_path: Path) -> Path:
    """A session file and its PDF, built by the builders the route B suite already uses."""
    return write(tmp_path, one_filing(tmp_path))


def prompts_for(session_path: Path, index: int, which_pass: int) -> tuple[str, str]:
    """The (system, user) prompt pair route A sends for this filing — built here.

    This is the same pair `cmd_prompt` prints, reached through `claude_extractor`
    directly, so the expected text comes from the prompt module (an input to the
    command) and never from the command's own output.
    """
    data = json.loads(session_path.read_text(encoding="utf-8"))
    plans = plan_filings([(f["fiscal_year"], f["pdf_path"]) for f in data["filings"]])
    if which_pass == 1:
        return pass1_prompts(plans[index])
    own, _ = parse_pass1(
        json.dumps(data["filings"][index]["pass1"]), TICKER, COMPANY)
    return pass2_prompts(plans[index], own)


# ===========================================================================
# 1. The handler itself: what it is, and what it leaves alone
# ===========================================================================

def test_the_handler_is_namereplace_and_the_encoding_does_not_move() -> None:
    """The one thing set is the error handler, and it is the one that names.

    The handler is `namereplace` because it is the only standard handler that
    leaves the reader able to say which character was there: `replace` writes
    `?`, `ignore` writes nothing, `backslashreplace` writes a code point and
    `xmlcharrefreplace` a decimal reference. The encoding is *not* touched, so a
    console keeps printing every character it already holds (the test below).
    """
    from ingestion.session_extraction import name_unencodable_characters

    _, stream = wrapper("cp1252")
    assert stream.encoding == "cp1252"

    assert name_unencodable_characters(stream) is True
    assert stream.errors == "namereplace"
    assert stream.encoding == "cp1252"


def test_an_unencodable_character_is_written_as_its_unicode_name() -> None:
    """cp1252 has no U+2192, so the stream must name it, byte for byte.

    Expected, from the `namereplace` contract and the Unicode name of U+2192:
        'costs → remove'  ->  b'costs \\N{RIGHTWARDS ARROW} remove'
    every other character being ASCII, which cp1252 writes unchanged.
    """
    from ingestion.session_extraction import name_unencodable_characters

    raw, stream = wrapper("cp1252")
    name_unencodable_characters(stream)

    assert written(raw, stream, f"costs {ARROW} remove") == (
        b"costs \\N{RIGHTWARDS ARROW} remove")


def test_the_handler_chosen_is_not_one_that_loses_the_character() -> None:
    """Four other handlers also finish the write. Each loses something; none may pass.

    The rendered bytes are compared against what each of the four would have
    produced for the same input, computed here with `str.encode` — the stdlib
    codec, not the unit under test. `ignore` is the dangerous one: it deletes the
    character outright and an exit-code test stays green.
    """
    from ingestion.session_extraction import name_unencodable_characters

    text = f"costs {ARROW} remove"
    raw, stream = wrapper("cp1252")
    name_unencodable_characters(stream)
    rendered = written(raw, stream, text)

    assert rendered != text.encode("cp1252", "ignore")            # b'costs  remove'
    assert rendered != text.encode("cp1252", "replace")           # b'costs ? remove'
    assert rendered != text.encode("cp1252", "backslashreplace")  # b'costs \\u2192 remove'
    assert rendered != text.encode("cp1252", "xmlcharrefreplace")  # b'costs &#8594; remove'
    # And it says which character it was, in the one form a human reads as a name.
    assert b"RIGHTWARDS ARROW" in rendered


def test_a_character_the_console_already_holds_is_written_unchanged() -> None:
    """The em dash and the ellipsis are in cp1252, so the handler may not reach them.

    Expected, from the cp1252 code chart: U+2014 is 0x97, U+2026 is 0x85. This is
    the assertion that fails if a future fix reaches a working console by forcing
    `encoding='utf-8'` onto one that is not.
    """
    from ingestion.session_extraction import name_unencodable_characters

    raw, stream = wrapper("cp1252")
    name_unencodable_characters(stream)

    assert written(raw, stream, "— …") == (
        CP1252_EM_DASH + b" " + CP1252_ELLIPSIS)


def test_a_utf8_console_is_not_degraded() -> None:
    """On UTF-8 the handler never runs: the arrow is written as the arrow.

    Expected, from the UTF-8 encoding rule applied to U+2192 by hand:
    b'\\xe2\\x86\\x92'. An error handler only runs for a character the encoding
    cannot hold, and UTF-8 holds every one.
    """
    from ingestion.session_extraction import name_unencodable_characters

    raw, stream = wrapper("utf-8")
    assert name_unencodable_characters(stream) is True
    assert stream.encoding == "utf-8"

    rendered = written(raw, stream, f"costs {ARROW} remove")
    assert rendered == b"costs " + UTF8_ARROW + b" remove"
    assert b"\\N{" not in rendered


def test_a_stream_that_cannot_lose_a_character_keeps_every_character() -> None:
    """An `io.StringIO` performs no encode step, so there is nothing to set on it.

    The load-bearing assertion is the second one: the arrow survives. The unit
    returns False here rather than raising, and that is not a defaulted figure —
    there is no missing input to stop on, and no character can be lost in a stream
    that never encodes.
    """
    from ingestion.session_extraction import name_unencodable_characters

    stream = io.StringIO()
    assert name_unencodable_characters(stream) is False
    stream.write(f"costs {ARROW} remove")
    assert stream.getvalue() == f"costs {ARROW} remove"


def test_a_detached_stream_is_not_swallowed() -> None:
    """A stream that cannot be reconfigured is broken, not absent: it must stop.

    A `TextIOWrapper` whose buffer is gone can neither be configured nor written
    to. Returning False here would hand the caller a stream that silently drops
    everything; the error has to reach the caller.
    """
    from ingestion.session_extraction import name_unencodable_characters

    _, stream = wrapper("cp1252")
    stream.detach()
    with pytest.raises(ValueError, match="detach"):
        name_unencodable_characters(stream)


# ===========================================================================
# 2. `main` wires both streams, before it parses argv — read from inside the run
# ===========================================================================

@pytest.mark.parametrize("encoding", ["cp1252", "utf-8"])
def test_main_sets_the_handler_on_stdout_and_stderr_and_moves_neither_encoding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, encoding: str,
) -> None:
    """Both streams carry `namereplace` for the whole command, and keep their encoding.

    **The reading moved inside the block, and that is the repair.** This test used
    to read `sys.stdout.errors` after `main()` had returned and require
    `namereplace` there. `main()` now puts the caller's handler back
    (`P1e-test-order`, backlog item 124), so that reading *is* the leak and
    asserting it would re-state the defect. The subject is unchanged and is
    `P14f`'s: the handler is `namereplace` on **both** streams while the command
    runs, and the encoding is not touched.

    Four expected values, not one of them this code's output:

    * `namereplace` on both streams, from `P14f`: the one standard handler that
      leaves a reader able to say which character was there;
    * the encoding is `encoding` before, at every write, and after — because that
      is what this test built the stream with, and the fix is in the handler;
    * the handler after the block is `CALLER_HANDLER`, because that is what this
      test put there and these streams are the caller's, not the module's;
    * exit 2, because the session file does not exist (P9a step 9).
    """
    out, err = recording_streams(monkeypatch, encoding)
    inside = handler_spy(monkeypatch)

    code = main(["check", str(tmp_path / "no-such-session.json")])

    # Inside the block, on both streams, before argv is parsed.
    assert inside == [("namereplace", "namereplace")]
    # And at every write the command made, which is where it decides a character's
    # bytes. Non-empty first: a command that printed nothing proves nothing.
    assert out.states
    assert set(out.states) == {(encoding, "namereplace")}
    # The encoding never moved: built with it, written with it, left with it.
    assert (out.encoding, err.encoding) == (encoding, encoding)
    # Both handlers are back, so an in-process caller keeps what it had.
    assert (out.errors, err.errors) == (CALLER_HANDLER, CALLER_HANDLER)
    assert code == 2


def test_main_sets_the_handler_before_it_parses_argv(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """argv that argparse rejects still prints through a handler that names.

    This is what makes one call site cover all six subcommands: the handler is on
    the stream before anything decides which subcommand is running, so `plan`,
    `locate`, `text`, `prompt` and `check` are covered by construction — and so is
    argparse's own usage message, which prints to stderr.

    Measured two ways, both from inside the run, because the old reading (the
    handler still on the stream after `main()` returned) is backlog item 124:

    * the spy reads both handlers at `_build_parser()`, which `main` evaluates
      before `parse_args(argv)`;
    * argparse's error message echoes the rejected subcommand, and the name given
      here holds `U+2192`, which cp1252 cannot encode. By the codecs
      error-handler table that message reaches the console as
      `\\N{RIGHTWARDS ARROW}` under `namereplace`, and as `&#8594;` under the
      `xmlcharrefreplace` this test put on the stream itself. So the bytes say
      which handler was in force at a write argparse made before any subcommand
      existed — and they would have said `&#8594;` had the handler been set after
      argv was parsed, or not at all.
    """
    out, err = recording_streams(monkeypatch, "cp1252")
    inside = handler_spy(monkeypatch)

    with pytest.raises(SystemExit) as stop:
        main([f"pass{ARROW}"])

    assert stop.value.code == 2  # argparse's exit code for an unparsable argv
    assert inside == [("namereplace", "namereplace")]
    assert err.states
    assert set(err.states) == {("cp1252", "namereplace")}

    message = rendered(err)
    assert NAMED_ARROW.encode("ascii") in message
    assert XMLCHARREF_ARROW not in message
    # argparse leaves through `SystemExit`, which is not an `Exception`: the
    # restore is in a `finally` and covers it.
    assert (out.errors, err.errors) == (CALLER_HANDLER, CALLER_HANDLER)


def test_plan_and_locate_go_through_the_block_too(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The two dispatch arms no other test reaches through `main`.

    "One `with` covers every subcommand" is a claim about `main`'s dispatch, and
    the test above proves only that the handler is on before the dispatch happens.
    `check` and `prompt` are run through it above; `plan` and `locate` are the two
    arms nothing else runs through `main` at all, so they are run here and asked
    the same two questions: every write happened at `namereplace`, and the
    caller's handler came back.

    Exit 0 twice, because both commands succeed: the skeleton is written to a path
    that does not exist yet, and the PDF `locate` reads is the one the session file
    records the hash of.
    """
    session_path = session_with_one_filing(tmp_path)
    data = json.loads(session_path.read_text(encoding="utf-8"))
    pdf_path = data["filings"][0]["pdf_path"]

    out, err = recording_streams(monkeypatch, "cp1252")
    plan_code = main(
        ["plan", pdf_path, "-t", TICKER, "-o", str(tmp_path / "skeleton.json")])
    locate_code = main(["locate", str(session_path), "--filing", "0"])

    assert (plan_code, locate_code) == (0, 0)
    assert out.states
    assert set(out.states) == {("cp1252", "namereplace")}
    assert (out.errors, err.errors) == (CALLER_HANDLER, CALLER_HANDLER)


@pytest.mark.parametrize("encoding", ["cp1252", "utf-8"])
def test_main_prints_through_both_streams_with_the_handler_on(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, encoding: str,
) -> None:
    """`prompt --pass 2` writes to stdout *and* stderr, and both name the arrow.

    `main` wraps stderr because `cmd_prompt` sends `parse_pass1`'s arithmetic
    table there. The test above proves the handler is on stderr; this one proves
    stderr is written to, on the one command backlog item 113 was about, with the
    handler recorded at each of those writes.

    Expected values: the arrow count is taken from the prompt pair built here out
    of `claude_extractor`, the command's own input; its rendering is the
    `namereplace` contract on cp1252 and the UTF-8 encoding rule on utf-8, both
    stated at the head of this file. Exit 0 because the command succeeds.
    """
    session_path = session_with_one_filing(tmp_path)
    system, user = prompts_for(session_path, 0, 2)
    arrows = (system + user).count(ARROW)
    assert arrows == PASS2_SYSTEM_ARROWS  # not a vacuous run

    out, err = recording_streams(monkeypatch, encoding)
    code = main(["prompt", str(session_path), "--filing", "0", "--pass", "2"])

    assert code == 0
    assert out.states and err.states  # both streams really were printed through
    assert set(out.states) == {(encoding, "namereplace")}
    assert set(err.states) == {(encoding, "namereplace")}

    printed = rendered(out)
    if encoding == "cp1252":
        assert printed.count(NAMED_ARROW.encode("ascii")) == arrows
        assert UTF8_ARROW not in printed
    else:
        assert printed.count(UTF8_ARROW) == arrows
        assert b"\\N{" not in printed

    assert (out.encoding, err.encoding) == (encoding, encoding)
    assert (out.errors, err.errors) == (CALLER_HANDLER, CALLER_HANDLER)


def test_main_puts_both_handlers_back_when_a_subcommand_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An exception `main` does not catch still leaves the caller's streams as they were.

    `main` catches `ValueError` and `FileNotFoundError` and renders them as
    `ERROR: …`; anything else leaves through the two `with` blocks. The restore is
    in a `finally`, so the property is "whatever leaves, the handler is back", and
    the expected handler is the one this test installed — never a value read off a
    run.

    The stand-in subcommand also records the two handlers at the moment it is
    called, which is the deepest point inside the block, so this test says the
    handler was on *and* that it did not stay on.
    """
    seen: list[tuple[str | None, str | None]] = []

    def explode(path: Path) -> int:
        seen.append((sys.stdout.errors, sys.stderr.errors))
        raise RuntimeError("a subcommand failing in a way main does not catch")

    monkeypatch.setattr("ingestion.session_extraction.cmd_check", explode)
    out, err = recording_streams(monkeypatch, "cp1252")

    with pytest.raises(RuntimeError, match="does not catch"):
        main(["check", str(tmp_path / "any.json")])

    assert seen == [("namereplace", "namereplace")]
    assert (out.errors, err.errors) == (CALLER_HANDLER, CALLER_HANDLER)


@pytest.mark.parametrize("encoding", ["cp1252", "utf-8"])
def test_main_leaves_a_real_process_stream_as_it_found_it(
    tmp_path: Path, encoding: str,
) -> None:
    """The same restore, on the `sys.stdout` and `sys.stderr` Python itself builds.

    The tests above hand `main` a stream this file constructed. This one gives it
    a child process's real inherited pair, at the console encoding
    `PYTHONIOENCODING` sets, and asks an identity rather than a value: `main()`
    does not own those streams, so whatever handler they carried in, they carry
    out. That holds whatever Python's defaults happen to be, so no part of the
    expectation comes from a run.

    **This is the assertion backlog item 124 fails.** Before `P1e-test-order` the
    child read `namereplace` on both streams here, on a call that set it and never
    put it back.
    """
    record = run_main_and_record(
        ["check", str(tmp_path / "no-such-session.json")],
        tmp_path / "record.json", encoding)

    assert record["errors"] == record["errors_before"]
    # Not vacuous: `sys`'s documentation gives a piped stdout `strict` and a piped
    # stderr `backslashreplace`, so neither end of that identity reads
    # `namereplace` unless this module set it and left it there.
    assert "namereplace" not in record["errors_before"]
    assert record["after"] == record["before"] == [encoding, encoding]
    # The session file does not exist, so the command stops: exit 2, by P9a step 9.
    assert record["code"] == 2


# ===========================================================================
# 2b. `naming_unencodable_characters`: the block, and what it puts back
# ===========================================================================

def test_inside_the_block_the_handler_names_and_after_it_the_caller_s_handler_is_back(
) -> None:
    """Set for the body, put back on the way out — proved by bytes, not by an attribute.

    The same text is written twice, inside the block and after it, and the two
    renderings are the two the codecs error-handler table gives for `U+2192`:
    `\\N{RIGHTWARDS ARROW}` under `namereplace`, `&#8594;` under the
    `xmlcharrefreplace` this test put on the stream. A restore that only reset the
    attribute, or one that never ran, cannot produce that pair.
    """
    stream = owned_stream("cp1252", CALLER_HANDLER)
    raw = stream.buffer
    assert isinstance(raw, io.BytesIO)

    with naming_unencodable_characters(stream) as was_set:
        assert was_set is True
        assert stream.errors == "namereplace"
        assert stream.encoding == "cp1252"
        stream.write(f"inside {ARROW}\n")
        stream.flush()
        inside_bytes = raw.getvalue()

    assert stream.errors == CALLER_HANDLER
    assert stream.encoding == "cp1252"
    stream.write(f"after {ARROW}\n")
    stream.flush()
    after_bytes = raw.getvalue()[len(inside_bytes):]

    assert inside_bytes == b"inside " + NAMED_ARROW.encode("ascii") + b"\n"
    assert after_bytes == b"after " + XMLCHARREF_ARROW + b"\n"


def test_the_caller_s_handler_is_back_when_the_body_raises() -> None:
    """The body failing is not a reason to keep a handler the caller did not set."""
    stream = owned_stream("cp1252", CALLER_HANDLER)

    with pytest.raises(RuntimeError, match="the body failed"), \
            naming_unencodable_characters(stream):
        assert stream.errors == "namereplace"
        raise RuntimeError("the body failed")

    assert stream.errors == CALLER_HANDLER


def test_the_caller_s_handler_is_back_on_systemexit() -> None:
    """argparse's exit path, at the level of the block itself.

    `SystemExit` derives from `BaseException` and not from `Exception`, so a
    restore written as `except Exception` would miss it and every rejected argv
    would leak a handler. The restore is a `finally`, which does not.
    """
    stream = owned_stream("cp1252", CALLER_HANDLER)

    with pytest.raises(SystemExit) as stop, naming_unencodable_characters(stream):
        assert stream.errors == "namereplace"
        raise SystemExit(2)

    assert stop.value.code == 2
    assert stream.errors == CALLER_HANDLER


def test_a_stream_that_does_not_encode_is_yielded_through_with_nothing_set() -> None:
    """No encode step means nothing can be lost, so there is nothing to set or restore.

    This is not a defaulted figure and there is no missing input to stop on: an
    object that keeps `str` cannot drop a character, which is the only thing the
    handler protects. What the test does lock is that the block is a pass-through
    for such an object — it yields `False`, and it does not reach for
    `reconfigure` on the way in or on the way out.
    """
    class NotAnEncoder:
        def __init__(self) -> None:
            self.reconfigured: list[dict[str, Any]] = []
            self.text = ""

        def reconfigure(self, **kwargs: Any) -> None:
            self.reconfigured.append(kwargs)

        def write(self, text: str) -> int:
            self.text += text
            return len(text)

    stream = NotAnEncoder()

    with naming_unencodable_characters(stream) as was_set:
        assert was_set is False
        assert stream.reconfigured == []        # nothing set on the way in
        stream.write(f"costs {ARROW} remove")

    assert stream.reconfigured == []            # and nothing restored on the way out
    assert stream.text == f"costs {ARROW} remove"


def test_a_handler_that_is_not_a_name_stops_and_names_the_value_and_the_stream() -> None:
    """Rule 3. `reconfigure(errors=None)` means "leave the handler alone".

    So a stream whose `errors` does not read as a handler name is one the block
    could set `namereplace` on and never put back — backlog item 124 wearing a
    quieter face, and silent. It must stop before it sets anything.

    The exception type is part of the requirement, not decoration: `main` catches
    `ValueError` and renders it as an ordinary `ERROR: …` with exit 2, so a
    `ValueError` here would be indistinguishable from a bad session file.
    """
    class HandlerIsNotAName(io.TextIOWrapper):
        def __init__(self) -> None:
            super().__init__(io.BytesIO(), encoding="cp1252", newline="\n")
            self.reconfigured: list[dict[str, Any]] = []

        @property
        def errors(self) -> str | None:
            return None

        def reconfigure(self, **kwargs: Any) -> None:
            self.reconfigured.append(kwargs)

    stream = HandlerIsNotAName()

    with pytest.raises(TypeError) as stop, naming_unencodable_characters(stream):
        pytest.fail("the body must not run when the handler cannot be put back")

    assert not isinstance(stop.value, ValueError)  # `main` would have swallowed one
    message = str(stop.value)
    assert "None" in message                       # the value it read
    assert "error handler" in message              # what that value was supposed to be
    assert "HandlerIsNotAName" in message          # the stream it read it from
    assert stream.reconfigured == []               # it stopped before it set anything


def test_the_outer_stream_is_restored_when_the_inner_one_stops() -> None:
    """`main` nests two of these blocks. The first must not be left changed by the second.

    stdout is entered, then stderr; if stderr cannot be restored afterwards the
    whole call fails, and stdout — already set — has to come back. Otherwise the
    rule 3 stop would itself leak a handler.
    """
    class HandlerIsNotAName(io.TextIOWrapper):
        @property
        def errors(self) -> str | None:
            return None

    outer = owned_stream("cp1252", CALLER_HANDLER)
    inner = HandlerIsNotAName(io.BytesIO(), encoding="cp1252", newline="\n")

    # The two blocks are entered in `main`'s order: stdout, then stderr.
    with pytest.raises(TypeError), naming_unencodable_characters(outer), \
            naming_unencodable_characters(inner):
        pytest.fail("neither body may run")

    assert outer.errors == CALLER_HANDLER


# ===========================================================================
# 3. `prompt --pass 2` end to end, on a console that cannot hold the arrow
# ===========================================================================

def test_prompt_pass2_prints_the_whole_prompt_on_a_cp1252_console(
    tmp_path: Path,
) -> None:
    """Item 113's exact case: the command finishes, and every line arrives.

    Two expected values, both identities:

    * the output is `len(system lines) + len(user lines) + 5` lines, the five
      being `cmd_prompt`'s framing — one system header, a blank line and a user
      header, and a blank line and one closing instruction. A run that stops at
      the arrow, as this one did at `HEAD`, cannot satisfy it;
    * every line of either prompt that holds an unencodable character arrives with
      that character named, and the count of named arrows equals the count of
      arrows in the prompts. Nothing dropped, nothing doubled.

    The prompts are built here from `claude_extractor`, the command's input.
    """
    session_path = session_with_one_filing(tmp_path)
    system, user = prompts_for(session_path, 0, 2)
    # Guard against a vacuous pass: the prompt must actually hold the character
    # whose rendering this test is about (two of them, at claude_extractor.py:412-413).
    assert (system + user).count(ARROW) == PASS2_SYSTEM_ARROWS

    result = child(["-m", "ingestion.session_extraction", "prompt",
                    str(session_path), "--filing", "0", "--pass", "2"],
                   {"PYTHONIOENCODING": "cp1252"})

    assert result.returncode == 0, result.stderr.decode("cp1252")
    assert b"charmap" not in result.stdout + result.stderr

    text = result.stdout.decode("cp1252").replace("\r\n", "\n")
    assert text.endswith("\n")
    assert len(text.split("\n")) - 1 == (
        len(system.split("\n")) + len(user.split("\n")) + 5)

    assert text.count(NAMED_ARROW) == (system + user).count(ARROW)
    for line in (system + "\n" + user).split("\n"):
        if ARROW in line:
            assert line.replace(ARROW, NAMED_ARROW) in text


def test_prompt_pass2_output_holds_no_silent_substitute(tmp_path: Path) -> None:
    """The same run, asked the question the exit code cannot answer.

    Under `replace` the two `direction` rows read `costs ? remove`; under `ignore`
    they read `costs  remove` and nothing at all says a character was there. Both
    exit 0. This test takes each prompt line that holds the arrow, renders it the
    way those two handlers would, and requires that neither spelling is what the
    console received.
    """
    session_path = session_with_one_filing(tmp_path)
    system, user = prompts_for(session_path, 0, 2)
    arrow_lines = [line for line in (system + "\n" + user).split("\n")
                   if ARROW in line]
    assert len(arrow_lines) == PASS2_SYSTEM_ARROWS

    result = child(["-m", "ingestion.session_extraction", "prompt",
                    str(session_path), "--filing", "0", "--pass", "2"],
                   {"PYTHONIOENCODING": "cp1252"})
    assert result.returncode == 0, result.stderr.decode("cp1252")
    text = result.stdout.decode("cp1252")

    for line in arrow_lines:
        assert line.replace(ARROW, "?") not in text          # `replace`
        assert line.replace(ARROW, "") not in text           # `ignore`
        assert line.replace(ARROW, "\\u2192") not in text    # `backslashreplace`
        assert line.replace(ARROW, "&#8594;") not in text    # `xmlcharrefreplace`
        assert line.replace(ARROW, NAMED_ARROW) in text      # `namereplace`


def test_prompt_pass2_on_a_utf8_console_prints_the_arrow_itself(
    tmp_path: Path,
) -> None:
    """The same command where the console can hold the character: nothing is escaped.

    Expected from the UTF-8 encoding rule: the arrow's own three bytes are in the
    output, and no `\\N{` escape is, because the handler never runs.
    """
    session_path = session_with_one_filing(tmp_path)
    system, user = prompts_for(session_path, 0, 2)

    result = child(["-m", "ingestion.session_extraction", "prompt",
                    str(session_path), "--filing", "0", "--pass", "2"],
                   {"PYTHONIOENCODING": "utf-8"})

    assert result.returncode == 0, result.stderr.decode("utf-8")
    assert result.stdout.count(UTF8_ARROW) == (system + user).count(ARROW)
    assert b"\\N{" not in result.stdout

    text = result.stdout.decode("utf-8").replace("\r\n", "\n")
    assert len(text.split("\n")) - 1 == (
        len(system.split("\n")) + len(user.split("\n")) + 5)


# ===========================================================================
# 4. The subcommands that already worked are unmoved
# ===========================================================================

def test_prompt_pass1_on_a_cp1252_console_is_whole_and_unescaped(
    tmp_path: Path,
) -> None:
    """Pass 1's prompt holds no unencodable character, so nothing may be escaped.

    Its headers print the em dash, which cp1252 holds as 0x97. The line-count
    identity is the same one Pass 2 is held to.
    """
    session_path = session_with_one_filing(tmp_path)
    system, user = prompts_for(session_path, 0, 1)
    assert (system + user).count(ARROW) == 0

    result = child(["-m", "ingestion.session_extraction", "prompt",
                    str(session_path), "--filing", "0", "--pass", "1"],
                   {"PYTHONIOENCODING": "cp1252"})

    assert result.returncode == 0, result.stderr.decode("cp1252")
    assert b"\\N{" not in result.stdout
    assert CP1252_EM_DASH in result.stdout  # the two `=== … ===` headers

    text = result.stdout.decode("cp1252").replace("\r\n", "\n")
    assert len(text.split("\n")) - 1 == (
        len(system.split("\n")) + len(user.split("\n")) + 5)


def test_check_on_a_cp1252_console_still_prints_the_characters_it_holds(
    tmp_path: Path,
) -> None:
    """`check` printed an ellipsis before this unit and must still print one.

    `cmd_check` abbreviates each PDF hash with `U+2026`, which cp1252 holds as
    0x85. If the handler had been reached by changing the encoding instead, this
    byte would have become a UTF-8 sequence and a cp1252 console would show
    mojibake.
    """
    session_path = session_with_one_filing(tmp_path)

    result = child(["-m", "ingestion.session_extraction", "check",
                    str(session_path)], {"PYTHONIOENCODING": "cp1252"})

    assert result.returncode == 0, result.stderr.decode("cp1252")
    assert CP1252_ELLIPSIS in result.stdout
    assert b"\\N{" not in result.stdout


# ===========================================================================
# 5. The LLM boundary: no prompt byte moved
# ===========================================================================

def test_the_two_system_prompts_are_byte_for_byte_what_they_were() -> None:
    """The fix is in the stream, so not one byte of either system prompt may move.

    Both digests were measured in `git archive 0bc41a1`, the tree whose
    `session_extraction.py` is `2730e033…` — before this unit's code existed.
    Both constants are asserted non-empty before they are compared: two empty
    strings hash alike, and a comparison of two nothings is not a match.
    """
    from ingestion.claude_extractor import (
        _FINANCIALS_SYSTEM_PROMPT,
        _NRI_SYSTEM_PROMPT,
    )

    assert _FINANCIALS_SYSTEM_PROMPT
    assert _NRI_SYSTEM_PROMPT

    assert len(_FINANCIALS_SYSTEM_PROMPT) == PASS1_SYSTEM_LENGTH
    assert hashlib.sha256(
        _FINANCIALS_SYSTEM_PROMPT.encode("utf-8")).hexdigest() == PASS1_SYSTEM_SHA256

    assert len(_NRI_SYSTEM_PROMPT) == PASS2_SYSTEM_LENGTH
    assert hashlib.sha256(
        _NRI_SYSTEM_PROMPT.encode("utf-8")).hexdigest() == PASS2_SYSTEM_SHA256

    # And the two arrows item 113 is about are still in it, un-rewritten: the fix
    # was not allowed to reach a working console by editing the prompt.
    assert _NRI_SYSTEM_PROMPT.count(ARROW) == PASS2_SYSTEM_ARROWS


def test_the_prompts_the_command_prints_are_the_prompts_route_a_sends(
    tmp_path: Path,
) -> None:
    """The printed prompt is the prompt module's own string, not a copy of it.

    The digests above pin the module. This pins what `prompt --pass 2` prints to
    that module, through the UTF-8 run where no escaping happens at all, so the
    two together say the console fix changed nothing route A sends.
    """
    session_path = session_with_one_filing(tmp_path)
    system, user = prompts_for(session_path, 0, 2)
    assert system and user

    result = child(["-m", "ingestion.session_extraction", "prompt",
                    str(session_path), "--filing", "0", "--pass", "2"],
                   {"PYTHONIOENCODING": "utf-8"})

    assert result.returncode == 0, result.stderr.decode("utf-8")
    text = result.stdout.decode("utf-8").replace("\r\n", "\n")
    assert system in text
    assert user in text
