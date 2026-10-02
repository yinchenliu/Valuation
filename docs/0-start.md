# Start here

**Every agent reads this file first, whatever tool it runs in.** Claude Code loads
[../CLAUDE.md](../CLAUDE.md) automatically. Codex, OpenCode and the other tools that
follow the `AGENTS.md` convention load [../AGENTS.md](../AGENTS.md) instead. Both send
you here, so both start from one text and neither can go stale against the other.

Web and CLI DCF valuation. An LLM extracts figures from 10-K/10-Q PDFs; deterministic
Python does everything after that.

---

## The reading order

| Read this | When |
|---|---|
| [2-rules/rules.md](2-rules/rules.md) | **always, first.** Six rules. They override every other instruction, including this file |
| [INDEX.md](INDEX.md) | **always, second.** The map. Its "Open it when" column tells you which document to open — and which to leave shut |
| [../STATUS.md](../STATUS.md) | before claiming anything about the build. Measured, never planned |
| [../AGENTS.md](../AGENTS.md) | you are dispatching, reviewing or logging a work unit |
| [9-reference/refactor-backlog.md](9-reference/refactor-backlog.md) | before reporting a defect as new |

## The one command you need

```bash
.venv/Scripts/python.exe -m uvicorn app:app --reload    # Windows
.venv/bin/python -m uvicorn app:app --reload            # macOS
```

**Never a bare `python`.** The repository runs on a Windows machine and a macOS machine,
and the venv puts the interpreter under `Scripts` on one and `bin` on the other.
[8-build/environment.md](8-build/environment.md) owns the interpreter, the gates and the
setup.

## Four facts that change how you read the code

1. **The LLM extracts and nothing else.** No margin, no growth rate, no assumption comes
   from a model. [2-rules/llm-boundary.md](2-rules/llm-boundary.md).
2. **Every money figure is in millions.** Share prices are per share. Form values arrive
   as percentages and are divided by 100 once, at the route boundary.
   [4-conventions/units-and-signs.md](4-conventions/units-and-signs.md).
3. **A valuation that runs proves nothing.** Every money field defaults to `0.0`, so the
   pipeline renders a share price from an extraction that returned nothing at all. Name
   an input that came from a filing. [2-rules/rules.md](2-rules/rules.md), Rule 3.
4. **No gate passes today.** `pytest` cannot even collect. That is the starting
   position, not a regression. [../STATUS.md](../STATUS.md).

## Do not read the whole `docs/` folder

The map tells you which file owns your subject. A file that owns a subject is the only
one that states it; the others link. If you find the same fact in two files, one of them
is stale — report it.

---

## Why this file repeats four facts it does not own

[INDEX.md](INDEX.md) forbids a file from repeating another, because a fact with two
homes goes stale in one of them. **This file is the one exception, and it is narrow.**
An agent meets these four facts here, before it has read the file that owns them, and
too late is the only way to meet them. Each repeat above names its owner.

**Change the owner first. Then change this card.** A card that disagrees with its owner
is worse than no card.
