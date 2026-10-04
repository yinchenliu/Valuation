"""Locks backlog item 46: which value of a credential wins, and how it is labelled.

`P13c-env-override` (committed at `5b03600`) changed `config.py` so that:

* `.env` is read ONCE, with `dotenv_values`, and only names ABSENT from the
  environment are filled from it. A name that is set, even to the empty string,
  is left alone. So a value set before `config` loads wins over the file, and an
  empty value is the off switch.
* `config.credential_origin(name)` compares the value in use with the file's
  value at call time: equal gives `<NAME> (.env file)`; different, or a name the
  file does not hold, gives `<NAME> (shell or parent process, not .env)`. An
  unknown name, and a name unset or blank, raise `ValueError` naming the field.

The contract is `.agent/assignments/P13c-env-override.md` (round 3 amendment) and
`docs/8-build/environment.md` section 3. Every expected value below is read off
those two documents and off the invented values this file writes into its own
`.env`. **No expected value was obtained by running the code.**

## Never the real `.env`, never a real key

The repository's `.env` holds a live key. No test here reads it or sees its value:

* **Subprocess tests** (`_run_in_sandbox`) copy the shipped `config.py`, byte for
  byte, into a temporary directory beside a `.env` this file writes, and import it
  in a fresh interpreter whose environment is built from nothing but `PATH` and
  `PYTHONPATH`. `config.BASE_DIR` is `Path(__file__).parent`, so the copy reads the
  temporary `.env` through the real `dotenv_values`, exactly as the shipped module
  reads the real one. No credential the pytest process holds reaches the child.
* **In-process tests** (`_fresh_config`) execute the real `config.py` file under a
  private module name, with `dotenv.dotenv_values` replaced by a function that
  records the path it is asked for and reads this file's temporary `.env` instead.
  Every credential name is removed from `os.environ` first (and restored after),
  so a real key that another test's `import config` put there is not visible.

Nothing here calls `resolve_provider`, a model client, or the network.

## Deliberately NOT asserted

* The round 3 review's F5: a value set INSIDE a process after `config` loaded reads
  `(shell or parent process, not .env)`. That is a recorded note, not a decision,
  so no test here sets a credential after load and then reads its label. In the
  spawn test that passes a parent-chosen value, only the CHILD's label is read.
* The round 3 review's F6 (a value equal to the file's apart from whitespace).
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import dotenv
import pytest

REPO = Path(__file__).resolve().parents[2]
CONFIG_SRC = REPO / "config.py"

# The single name the contract labels (assignment, step 1; config.CREDENTIAL_NAMES).
# Written out here, not imported, so the test does not take its expectation from
# the module under test.
GEMINI = "GEMINI_API_KEY"
CREDENTIALS = (GEMINI,)

# The two label suffixes, word for word from the round 3 amendment.
FROM_FILE = "(.env file)"
NOT_FILE = "(shell or parent process, not .env)"

# Invented values. None of them is, or resembles, a real key.
FILE_GEMINI = "file-gemini-p13c-invented"
FILE_OTHER = "file-other-p13c-invented"
OTHER = "P13C_PROBE_NON_CREDENTIAL"

# The temporary .env. It holds Gemini, and one non-credential name.
ENV_TEXT = (
    f"{GEMINI}={FILE_GEMINI}\n"
    f"{OTHER}={FILE_OTHER}\n"
)

REPORTED = (*CREDENTIALS, OTHER)


# ---------------------------------------------------------------------------
# Subprocess sandbox: the shipped config.py, a fresh interpreter, our .env
# ---------------------------------------------------------------------------

# Imported by every child. Prints one JSON line: where config came from, what the
# environment holds for each reported name, and each credential's label (or the
# ValueError it raised). Only invented values can appear in it.
_REPORT_MODULE = f"REPORTED = {REPORTED!r}\nCREDENTIALS = {CREDENTIALS!r}\n" + '''
import json
import os


def report():
    import config
    labels = {}
    for name in CREDENTIALS:
        try:
            labels[name] = config.credential_origin(name)
        except ValueError as exc:
            labels[name] = "ValueError: " + str(exc)
    return {
        "config_file": config.__file__,
        "present": {n: n in os.environ for n in REPORTED},
        "values": {n: os.environ[n] for n in REPORTED if n in os.environ},
        "labels": labels,
    }


def spawn_target(queue):
    queue.put(report())


def main():
    print(json.dumps(report()))
'''

# The parent for the process-boundary tests. It imports config FIRST (so the fill
# from .env has happened in the parent), then starts one child, and prints the
# parent's report and the child's report.
_PARENT_MODULE = '''
import json
import multiprocessing
import os
import subprocess
import sys

import config  # the parent's fill from .env happens here
import p13c_report


def child_by_subprocess(env):
    out = subprocess.run(
        [sys.executable, "-c", "import p13c_report; p13c_report.main()"],
        env=env, capture_output=True, text=True, check=True, timeout=60,
    )
    return json.loads(out.stdout)


def child_by_spawn():
    # multiprocessing "spawn" is the mechanism uvicorn's reloader uses
    # (round 1 review, F1): the child inherits os.environ at start.
    ctx = multiprocessing.get_context("spawn")
    queue = ctx.Queue()
    proc = ctx.Process(target=p13c_report.spawn_target, args=(queue,))
    proc.start()
    result = queue.get(timeout=60)
    proc.join(timeout=60)
    return result


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "inherit-subprocess":
        parent = p13c_report.report()
        child = child_by_subprocess(dict(os.environ))
    elif mode == "inherit-spawn":
        parent = p13c_report.report()
        child = child_by_spawn()
    elif mode == "parent-chosen-subprocess":
        parent = p13c_report.report()
        child = child_by_subprocess({**os.environ, sys.argv[2]: sys.argv[3]})
    elif mode == "parent-chosen-spawn":
        # The parent's own label after this line would be the F5 case; it is
        # taken BEFORE the parent sets the value, and only the child's is new.
        parent = p13c_report.report()
        os.environ[sys.argv[2]] = sys.argv[3]
        child = child_by_spawn()
    else:
        raise SystemExit("unknown mode " + mode)
    print(json.dumps({"parent": parent, "child": child}))
'''


def _sandbox(tmp_path: Path, env_text: str | None = ENV_TEXT) -> Path:
    """A directory holding a byte copy of the shipped config.py and our own .env."""
    box = tmp_path / "box"
    box.mkdir()
    shutil.copyfile(CONFIG_SRC, box / "config.py")
    if env_text is not None:
        (box / ".env").write_text(env_text, encoding="utf-8")
    (box / "p13c_report.py").write_text(_REPORT_MODULE, encoding="utf-8")
    (box / "p13c_parent.py").write_text(_PARENT_MODULE, encoding="utf-8")
    return box


def _clean_env(box: Path, preset: dict[str, str]) -> dict[str, str]:
    """An environment built from nothing: PATH, PYTHONPATH and the preset names.

    Nothing the pytest process holds (including any real key that another test's
    `import config` filled into os.environ) is passed on.
    """
    env = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": str(box),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
    }
    if "SYSTEMROOT" in os.environ:  # Windows needs it to start an interpreter
        env["SYSTEMROOT"] = os.environ["SYSTEMROOT"]
    env.update(preset)
    return env


def _run(box: Path, args: list[str], preset: dict[str, str]) -> dict:
    out = subprocess.run(
        [sys.executable, *args],
        cwd=box,
        env=_clean_env(box, preset),
        capture_output=True,
        text=True,
        timeout=120,
        check=False,  # a failure is asserted below, with the child's stderr
    )
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])


def _run_in_sandbox(box: Path, preset: dict[str, str]) -> dict:
    report = _run(box, ["-c", "import p13c_report; p13c_report.main()"], preset)
    # The child imported the copy in the sandbox, so it read the sandbox's .env.
    assert Path(report["config_file"]).resolve() == (box / "config.py").resolve()
    return report


def _run_parent(box: Path, preset: dict[str, str], *mode: str) -> dict:
    both = _run(box, ["p13c_parent.py", *mode], preset)
    for side in ("parent", "child"):
        assert Path(both[side]["config_file"]).resolve() == (box / "config.py").resolve()
    return both


# ---------------------------------------------------------------------------
# Step 1 — the order: set before load wins; empty stays empty; absent is filled
# ---------------------------------------------------------------------------


def test_the_sandbox_copy_is_the_shipped_config(tmp_path: Path) -> None:
    # The subprocess tests are only as good as this: the module they import is
    # byte-identical to the one in the repository.
    box = _sandbox(tmp_path)
    assert (box / "config.py").read_bytes() == CONFIG_SRC.read_bytes()


def test_a_value_set_before_config_loads_wins_over_the_file(tmp_path: Path) -> None:
    # Expected: the preset value, unchanged. The file's value for the same name
    # (FILE_GEMINI) must not replace it. This is the line that override=True
    # broke (backlog item 46).
    box = _sandbox(tmp_path)
    report = _run_in_sandbox(box, {GEMINI: "shell-gemini-p13c-invented"})
    assert report["values"][GEMINI] == "shell-gemini-p13c-invented"
    assert report["labels"][GEMINI] == f"{GEMINI} {NOT_FILE}"


def test_an_empty_value_set_before_config_loads_stays_empty(tmp_path: Path) -> None:
    # The off switch: `GEMINI_API_KEY= ...`. The name is present, so it is not
    # filled; its value stays "", and there is no credential to label.
    box = _sandbox(tmp_path)
    report = _run_in_sandbox(box, {GEMINI: ""})
    assert report["present"][GEMINI] is True
    assert report["values"][GEMINI] == ""
    assert report["labels"][GEMINI].startswith("ValueError: ")
    assert GEMINI in report["labels"][GEMINI]


def test_an_absent_name_is_filled_from_the_file(tmp_path: Path) -> None:
    # No name preset: every name the file holds is filled with the file's value,
    # the credential and the non-credential alike (load_dotenv(override=False)).
    box = _sandbox(tmp_path)
    report = _run_in_sandbox(box, {})
    assert report["values"][GEMINI] == FILE_GEMINI
    assert report["values"][OTHER] == FILE_OTHER
    assert report["labels"][GEMINI] == f"{GEMINI} {FROM_FILE}"


def test_a_name_the_file_does_not_hold_is_not_invented(tmp_path: Path) -> None:
    # Our .env holds only OTHER; GEMINI is in neither the environment nor the file:
    # it stays absent, and its label stops naming it.
    box = _sandbox(tmp_path, env_text=f"{OTHER}={FILE_OTHER}\n")
    report = _run_in_sandbox(box, {})
    assert report["present"][GEMINI] is False
    assert report["labels"][GEMINI].startswith("ValueError: ")
    assert GEMINI in report["labels"][GEMINI]


def test_the_order_is_per_name(tmp_path: Path) -> None:
    # One run, two names, two treatments: Gemini preset empty (stays off),
    # the non-credential absent (filled from .env).
    box = _sandbox(tmp_path)
    report = _run_in_sandbox(
        box, {GEMINI: ""},
    )
    assert report["values"][GEMINI] == ""
    assert report["values"][OTHER] == FILE_OTHER


def test_no_env_file_fills_nothing_and_a_set_value_is_not_the_file(tmp_path: Path) -> None:
    # A missing .env reads as no names (config.py docstring; load_dotenv did the
    # same). A value set in the environment is then, by the rule, "not .env".
    box = _sandbox(tmp_path, env_text=None)
    report = _run_in_sandbox(box, {GEMINI: "shell-gemini-p13c-invented"})
    assert report["present"][OTHER] is False
    assert report["labels"][GEMINI] == f"{GEMINI} {NOT_FILE}"


# ---------------------------------------------------------------------------
# Step 3 — the two process-boundary failures from review rounds 1 and 2
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("mode", ["inherit-subprocess", "inherit-spawn"])
def test_a_child_labels_a_value_inherited_from_the_files_fill_as_the_file(
    tmp_path: Path, mode: str,
) -> None:
    # Round 1 review F1: the parent filled GEMINI from .env, the child inherited
    # it, and round 1 labelled it "shell environment" in the child. The value the
    # child uses IS the file's value, so by the round 3 rule both say (.env file).
    box = _sandbox(tmp_path)
    both = _run_parent(box, {}, mode)
    assert both["parent"]["labels"][GEMINI] == f"{GEMINI} {FROM_FILE}"
    assert both["child"]["values"][GEMINI] == FILE_GEMINI
    assert both["child"]["labels"][GEMINI] == f"{GEMINI} {FROM_FILE}"


@pytest.mark.parametrize("mode", ["parent-chosen-subprocess", "parent-chosen-spawn"])
def test_a_child_labels_a_value_its_parent_chose_as_not_the_file(
    tmp_path: Path, mode: str,
) -> None:
    # Round 2 review F4: the parent imported config (and so filled GEMINI from
    # .env), then handed the child a value of its own. Round 2 trusted an inherited
    # marker and labelled it (.env file). The value differs from the file's, so the
    # child must say NOT_FILE. The parent's label is taken before it chose a value.
    box = _sandbox(tmp_path)
    both = _run_parent(box, {}, mode, GEMINI, "parent-chosen-p13c-invented")
    assert both["parent"]["labels"][GEMINI] == f"{GEMINI} {FROM_FILE}"
    assert both["child"]["values"][GEMINI] == "parent-chosen-p13c-invented"
    assert both["child"]["labels"][GEMINI] == f"{GEMINI} {NOT_FILE}"


# ---------------------------------------------------------------------------
# Step 2 — the two labels and the two stops, in process
# ---------------------------------------------------------------------------


def _fresh_config(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    preset: dict[str, str],
    env_text: str = ENV_TEXT,
) -> ModuleType:
    """Execute the real config.py afresh, reading OUR .env, under `preset`.

    Every credential name, and every name our .env holds, is first registered
    with monkeypatch (set, then deleted), so whatever the fresh module fills into
    os.environ is removed again when the test ends.
    """
    env_file = tmp_path / "our.env"
    env_file.write_text(env_text, encoding="utf-8")
    real_dotenv_values = dotenv.dotenv_values
    for name in {*CREDENTIALS, *real_dotenv_values(env_file)}:
        monkeypatch.setenv(name, "registered-for-restore")
        monkeypatch.delenv(name)
    for name, value in preset.items():
        monkeypatch.setenv(name, value)

    asked_for: list[Path] = []

    def read_our_file_instead(path: object = None, *args: object, **kwargs: object) -> dict:
        asked_for.append(Path(str(path)))
        return real_dotenv_values(env_file)

    # config.py does `from dotenv import dotenv_values`, which reads this attribute
    # when the module body runs.
    monkeypatch.setattr(dotenv, "dotenv_values", read_our_file_instead)
    spec = importlib.util.spec_from_file_location("_config_p13c_under_test", CONFIG_SRC)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # The shipped code asked for BASE_DIR / ".env" exactly once ("read .env once").
    assert asked_for == [REPO / ".env"]
    return module


def test_a_value_equal_to_the_files_reads_env_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    # Set before load to the file's own value: equal, so (.env file). The doc says
    # so explicitly ("A shell value that equals the file's value reads (.env file)").
    cfg = _fresh_config(monkeypatch, tmp_path, {GEMINI: FILE_GEMINI})
    assert cfg.credential_origin(GEMINI) == f"{GEMINI} {FROM_FILE}"


def test_a_value_filled_from_the_file_reads_env_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    cfg = _fresh_config(monkeypatch, tmp_path, {})
    assert os.environ[GEMINI] == FILE_GEMINI
    assert cfg.credential_origin(GEMINI) == f"{GEMINI} {FROM_FILE}"


def test_a_value_that_differs_from_the_files_reads_not_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    cfg = _fresh_config(monkeypatch, tmp_path, {GEMINI: "shell-gemini-p13c-invented"})
    assert cfg.credential_origin(GEMINI) == f"{GEMINI} {NOT_FILE}"


def test_a_name_the_file_does_not_hold_reads_not_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    # Our .env has no GEMINI line.
    cfg = _fresh_config(
        monkeypatch, tmp_path, {GEMINI: "shell-gemini-p13c-invented"},
        env_text=f"{OTHER}={FILE_OTHER}\n",
    )
    assert cfg.credential_origin(GEMINI) == f"{GEMINI} {NOT_FILE}"


def test_an_unknown_name_stops_and_names_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    # ANTHROPIC_API_KEY is an unknown name (not in CREDENTIAL_NAMES);
    # set here to an invented value so the stop is on the name, not on absence.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-p13c-invented")
    cfg = _fresh_config(monkeypatch, tmp_path, {})
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        cfg.credential_origin("ANTHROPIC_API_KEY")


@pytest.mark.parametrize("blank", ["", "   "])
def test_a_blank_value_stops_and_names_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, blank: str,
) -> None:
    cfg = _fresh_config(monkeypatch, tmp_path, {GEMINI: blank})
    assert os.environ[GEMINI] == blank  # set, so not filled (the off switch)
    with pytest.raises(ValueError, match=GEMINI):
        cfg.credential_origin(GEMINI)


def test_an_unset_name_stops_and_names_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    # GEMINI: not preset, not in our .env.
    cfg = _fresh_config(monkeypatch, tmp_path, {}, env_text=f"{OTHER}={FILE_OTHER}\n")
    assert GEMINI not in os.environ
    with pytest.raises(ValueError, match=GEMINI):
        cfg.credential_origin(GEMINI)


def test_a_name_with_no_value_in_the_file_is_neither_filled_nor_labelled(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    # A bare `GEMINI_API_KEY` line (no `=`) reads as None: not filled, not kept
    # (config.py docstring, matching load_dotenv). So it is unset, and stops.
    cfg = _fresh_config(
        monkeypatch, tmp_path, {}, env_text=f"{OTHER}={FILE_OTHER}\n{GEMINI}\n",
    )
    assert GEMINI not in os.environ
    with pytest.raises(ValueError, match=GEMINI):
        cfg.credential_origin(GEMINI)
    assert os.environ[OTHER] == FILE_OTHER
