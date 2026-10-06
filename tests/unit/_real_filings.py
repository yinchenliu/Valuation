"""Find a real 10-K PDF the way this repository stores one: `10K_filings/<TICKER>/`.

`10K_filings/` is git-ignored, so the set of filings differs from machine to
machine. A test that reads one is guarded by `@pytest.mark.skipif`, and that
guard has to be right twice: it must *find* a filing this machine holds, and
its skip reason must name what it looked for when it does not.

Until P1d four literal paths stood here instead, one per company, and one of
them read `10K_filings/Walmart/...` where the folder on disk is
`10K_filings/WMT/`. The file name was exactly right; only the folder was the
company name instead of the ticker. So the one test check B1 has against a real
Walmart 10-K skipped on a machine that holds that very file, and `pytest -q`
printed `5 skipped` with nothing to say that four of them were a typing error.
A skipped test reports neither pass nor fail. That is backlog item 101.

One literal per filing goes stale the next time a filing is added; the
convention stated once does not. `RealFiling` holds the convention
(`10K_filings/<TICKER>/<pattern>`), reports whether this machine holds the
file, and builds the skip reason from the pattern it tried.

**Exactly one match counts as found.** Two files matching a pattern means the
pattern does not name one document, and a test that reads "whichever sorted
first" is not reading a filing it can cite. That case is a miss, and the reason
says how many matched.

Nothing here opens a network socket or reads an API key.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

#: The repository root, from this file, so the lookup does not depend on the
#: working directory pytest was started in.
REPO_ROOT = Path(__file__).resolve().parents[2]

#: Where this repository keeps filings. One folder per ticker.
FILINGS_ROOT = REPO_ROOT / "10K_filings"


@dataclass(frozen=True)
class RealFiling:
    """One filing, named by its ticker folder and a file-name pattern.

    `pattern` is a `glob` pattern, matched inside `10K_filings/<ticker>/`. Pass
    a whole file name when you mean one document, which is the usual case: a
    wildcard that matches three fiscal years names no document in particular.
    """

    ticker: str
    pattern: str

    @property
    def folder(self) -> Path:
        return FILINGS_ROOT / self.ticker

    @property
    def tried(self) -> str:
        """The path this lookup tried, as it reads in the skip reason."""
        return f"10K_filings/{self.ticker}/{self.pattern}"

    def matches(self) -> list[Path]:
        """Every file under the ticker folder matching the pattern, sorted."""
        if not self.folder.is_dir():
            return []
        return sorted(p for p in self.folder.glob(self.pattern) if p.is_file())

    @property
    def path(self) -> Path | None:
        """The one matching file, or `None` when zero or several match."""
        found = self.matches()
        return found[0] if len(found) == 1 else None

    @property
    def found(self) -> bool:
        return self.path is not None

    @property
    def skip_reason(self) -> str:
        """Why the test skipped, naming the pattern that missed.

        A reader of `pytest -q -rs` can tell a filing this machine does not
        hold from a pattern that names no single document.
        """
        found = self.matches()
        if not found:
            return f"no file on this machine matches {self.tried}"
        return (
            f"{len(found)} files match {self.tried}, so it names no one document: "
            + ", ".join(p.name for p in found)
        )

    def read_bytes(self) -> bytes:
        """The filing's bytes, or a stop that names the pattern that missed."""
        path = self.path
        if path is None:
            raise FileNotFoundError(self.skip_reason)
        return path.read_bytes()
