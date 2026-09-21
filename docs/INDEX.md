# The map

**Read this file, then open only the ones you need.** Every document is small on
purpose. Nothing here repeats what another file says; where two files touch the same
subject, one of them owns it and the other links.

Three columns matter. **Owns** is the single question that document answers.
**Open it when** tells you whether to open it at all — if your task is not listed,
do not open the file.

---

## 0. Start here

| File | Owns | Open it when |
|---|---|---|
| [0-start.md](0-start.md) | the reading order, the interpreter command, and the four facts that change how you read the code | **always, before this file.** Both entry points send you here |

## 1. What this is

| File | Owns | Open it when |
|---|---|---|
| [1-overview/pipeline.md](1-overview/pipeline.md) | one valuation end to end, step by step, with the file that owns each step | you need to know where your piece sits in the sequence |
| [1-overview/glossary.md](1-overview/glossary.md) | the finance terms, each defined once | you meet a term you cannot define — FCFF, NOPAT, WACC, NWC, ERP |

## 2. The rules

**These bind every agent and every file. If an instruction conflicts with one, the
rule wins.**

| File | Owns | Open it when |
|---|---|---|
| [2-rules/rules.md](2-rules/rules.md) | the six rules, in full | **always. Before anything else** |
| [2-rules/llm-boundary.md](2-rules/llm-boundary.md) | what the model may and may not return, and where the line sits in code | you are touching `ingestion/`, or reviewing a change to a prompt |

## 3. Architecture

| File | Owns | Open it when |
|---|---|---|
| [3-architecture/data-contract.md](3-architecture/data-contract.md) | the `models/` dataclasses, what each field means, and which are derived | you are reading or writing a `FinancialStatements` |
| [3-architecture/extraction.md](3-architecture/extraction.md) | the two passes, the providers, the multi-PDF year routing | you are changing `ingestion/claude_extractor.py` |
| [3-architecture/valuation-math.md](3-architecture/valuation-math.md) | every formula: normalisation, assumptions, CAPM, WACC, FCFF, DCF | you are writing or checking arithmetic |
| [3-architecture/entry-points.md](3-architecture/entry-points.md) | the web routes, the CLI, and where the two duplicate each other | you are changing `api/`, `templates/` or `cli.py` |

## 4. Conventions

| File | Owns | Open it when |
|---|---|---|
| [4-conventions/units-and-signs.md](4-conventions/units-and-signs.md) | millions, percentages, and the sign of every cash-flow field | **before you write any arithmetic.** This is where the three-orders-of-magnitude errors come from |

## 5. Testing

| File | Owns | Open it when |
|---|---|---|
| [5-testing/strategy.md](5-testing/strategy.md) | what a test here must do, where an expected value may come from, and why `tests/` holds none today | you are writing a test, or judging one |

## 8. Building it

| File | Owns | Open it when |
|---|---|---|
| [8-build/environment.md](8-build/environment.md) | the interpreter, the virtual environment, the three gates, the API keys | setting up, or a command failed |
| [8-build/phases.md](8-build/phases.md) | the build order and every done-criterion | starting any unit of work |

## 9. Reference

| File | Owns | Open it when |
|---|---|---|
| [9-reference/refactor-backlog.md](9-reference/refactor-backlog.md) | every known defect, with its evidence and what it costs | before reporting a defect as new, and when writing an assignment |
| [9-reference/severity.md](9-reference/severity.md) | how a finding is ranked, and why that is not a free choice | you are a reviewer about to write `note` |

---

## Outside this folder

**Two files are entry points. Which one your session loaded depends on the tool.**

| File | Loaded automatically by | Owns |
|---|---|---|
| `../CLAUDE.md` | Claude Code, in every session | the pointer a Claude session starts from. It delegates to [0-start.md](0-start.md) |
| `../AGENTS.md` | Codex, OpenCode, and the other tools that follow the `AGENTS.md` convention | who does the work and how they hand off. It delegates to [0-start.md](0-start.md) |
| `../STATUS.md` | nothing. An agent opens it | how far the build has got. **Measured, never planned** |
| `../README.md` | nothing. A human opens it | what this repository is, for a human arriving at it |

**Neither entry point owns an orientation fact.** Both send you to
[0-start.md](0-start.md) for the reading order, the interpreter command and the four
facts. Put a new orientation fact in `0-start.md`. A fact added to one entry point and
not the other is a fact that half the tools never see, and no gate detects that.

Claude Code does not load `AGENTS.md`. Measured at version 2.1.278: its `agents-md`
plugin is off by default, and its default mode loads `AGENTS.md` only in a project that
has no `CLAUDE.md`. This project has one.

---

## `docs/` holds documents. It never holds data

| Folder | Holds | Does **not** hold |
|---|---|---|
| `docs/` | rules, contracts, formulas, conventions | any company's figures |
| `10K_filings/` | the source PDFs | anything derived from them |
| `cache/`, `tests/*.pkl` | pickled extraction output | anything to be trusted as a reference |

**Why the split.** A document states a rule and changes when the rule changes. A data
file states a fact about one company and changes when a new filing arrives. Putting
them in one folder means a reviewer cannot tell which kind of change they are looking
at.

---

## Rules for this folder itself

1. **One subject per file.** If a file answers two questions, split it.
2. **No file repeats another.** Link instead. A fact with two homes goes stale in one
   of them, and nothing detects it. **[0-start.md](0-start.md) is the only exception**,
   and it is narrow: it repeats four facts so that an agent meets them before it can
   reach the file that owns them. Each repeat there names its owner. Change the owner
   first, then the card.
3. **A file that states a measurement names the commit it was measured at.** A number
   with no commit beside it is not a measurement.
4. **Keep every file under about 500 lines.** A file an agent cannot hold in context
   is a file it will skim.
5. **Update this index when you add a file.** An unlisted file does not exist, because
   nobody opens it.
