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

**Why nothing here calls `main()` in this process.** `main()` sets a handler on
the process-global `sys.stdout` and never restores it, and
`_pytest.capture.CaptureIO` is an `io.TextIOWrapper` subclass, so an in-process
call would leak `errors='namereplace'` into every test that ran afterwards
(backlog item 124). Every test below either builds its own `TextIOWrapper` over a
`BytesIO` it owns, or runs `main` in a **subprocess** whose streams die with it.
No test here reads or writes `sys.stdout`, `sys.stderr` or any other global, so
the order they run in cannot change a result.

**No test here reaches the API, the network or a real filing.** The session file
and its PDF are built under `tmp_path` by the builders in
`tests/unit/test_session_extraction.py`, and every subprocess is given empty API
keys.
"""

from __future__ import annotations

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
    "argv = json.loads(sys.argv[1])\n"
    "try:\n"
    "    code = main(argv)\n"
    "except SystemExit as exc:\n"
    "    code = exc.code\n"
    "record = {'before': list(before),\n"
    "          'after': [sys.stdout.encoding, sys.stderr.encoding],\n"
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
# 2. `main` wires both streams, before it parses argv
# ===========================================================================

@pytest.mark.parametrize("encoding", ["cp1252", "utf-8"])
def test_main_sets_the_handler_on_stdout_and_stderr_and_moves_neither_encoding(
    tmp_path: Path, encoding: str,
) -> None:
    """Both streams, because `cmd_prompt` sends `parse_pass1`'s table to stderr.

    Run in a subprocess: `main` mutates process-global streams and never restores
    them (backlog item 124), so calling it here would leak the handler into every
    later test in this process.
    """
    record = run_main_and_record(
        ["check", str(tmp_path / "no-such-session.json")],
        tmp_path / "record.json", encoding)

    assert record["errors"] == ["namereplace", "namereplace"]
    assert record["after"] == record["before"] == [encoding, encoding]
    # The session file does not exist, so the command stops: exit 2, by P9a step 9.
    assert record["code"] == 2


def test_main_sets_the_handler_before_it_parses_argv(tmp_path: Path) -> None:
    """argv that argparse rejects still leaves both streams safe.

    This is what makes one call site cover all six subcommands: the handler is on
    the stream before anything decides which subcommand is running, so `plan`,
    `locate`, `text`, `prompt` and `check` are covered by construction — and so is
    argparse's own usage message, which prints to stderr.
    """
    record = run_main_and_record(
        ["no-such-subcommand"], tmp_path / "record.json", "cp1252")

    assert record["errors"] == ["namereplace", "namereplace"]
    assert record["code"] == 2  # argparse's exit code for an unparsable argv


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
