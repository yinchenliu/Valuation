"""Run every offline test suite and report a single pass/fail.

None of these hit an API or the network — they run from the committed extraction
pickles with synthetic price data, so they are safe to run on every change.

Usage:
    python tests/run_all.py
"""

from __future__ import annotations

import importlib
import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

SUITES = [
    ("golden regression", "tests.test_regression_golden"),
    ("agent tools", "tests.test_agent_tools"),
    ("agent loop", "tests.test_agent_loop"),
    ("web smoke", "tests.test_web_smoke"),
]


def main() -> int:
    results: list[tuple[str, int, str]] = []

    for label, module_name in SUITES:
        module = importlib.import_module(module_name)
        buffer = io.StringIO()
        try:
            with redirect_stdout(buffer):
                code = module.main()
        except Exception as exc:  # noqa: BLE001
            code = 1
            buffer.write(f"\n{type(exc).__name__}: {exc}")
        results.append((label, code, buffer.getvalue()))
        print(f"  {'PASS' if code == 0 else 'FAIL'}  {label}")

    failed = [(label, out) for label, code, out in results if code != 0]

    print()
    if failed:
        for label, out in failed:
            print("=" * 70)
            print(f"OUTPUT — {label}")
            print("=" * 70)
            print(out)
        print(f"FAILED: {len(failed)} of {len(SUITES)} suite(s)")
        return 1

    print(f"All {len(SUITES)} suites passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
