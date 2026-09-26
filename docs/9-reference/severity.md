# How a finding is ranked

**Open this when you are a reviewer about to write `note`.**

Severity is not a free choice. It is decided by two questions, in order.

---

## Question 1 — does the finding cite a rule?

If your finding cites a rule in [2-rules/rules.md](../2-rules/rules.md), it is **at
minimum `major`**, and a standing `major` forces `changes_requested`.

**You do not get to quote rule 3 and then approve.**

`note` is for something real that breaks no rule: a dead constant, a stale docstring, a
name that will confuse the next reader. **If you can name the rule, it is not a
`note`.** If you cannot name one, it is.

## Question 2 — is it silent or stopping?

This axis **outranks** the first for ordering, though not for the floor set by
question 1.

| | Meaning |
|---|---|
| **Silent** | produces a wrong number on a clean run. Nothing downstream detects it |
| **Stopping** | raises, or refuses to run. Visible the moment it happens |

**A silent defect that moves the implied share price outranks everything else**,
however small the diff that causes it. A stopping defect is close to harmless: the run
refuses rather than lying.

When a finding is silent, also say **which direction it errs**. A defect that
*overstates* value is worse than one that understates it, because a figure that flatters
the company is the one a reader is least likely to challenge.

---

## The four levels

| Severity | Meaning | Forces `changes_requested`? |
|---|---|---|
| `blocker` | a wrong number reaches the user, or the unit cannot be accepted as written — a rule inverted, a scope breach, a layering break | **yes** |
| `major` | a rule is broken. Any rule, anywhere in the diff | **yes** |
| `minor` | correct today, fragile tomorrow. A missing guard on a path nothing currently reaches | no |
| `note` | real, breaks no rule. Dead code, a stale comment, a confusing name | no |

---

## Three arguments that look like grounds to downgrade

None of them is. Each has been used, in a real build, to approve a defect that shipped.

| The argument | Why it fails |
|---|---|
| **"the fix belongs to a future unit"** | the rule beats the assignment. An out-of-scope call site makes the unit `changes_requested`, and the orchestrator widens the scope. It does not make the finding a `note` |
| **"the extractor always supplies that key today"** | then the fallback is unreachable — and unreachable code that quietly returns a number is exactly what rule 3 forbids. **Reachability is not the test.** The test is: if it were missing, what happens? |
| **"it is only defensive"** | a defence that returns `0.0` is not a defence. It converts a stop into a wrong number. It is the defect, wearing the word "safe" |

---

## The one exception, and it is not yours to grant

The **user** may accept a known deviation. That is where
[AGENTS.md](../../AGENTS.md)'s escalation path ends.

When they do, the assignment names the decision, its date, and **exactly which lines it
covers**. Check the citation is there, leave those lines out of your findings, and say
in your entry that you did.

**An assignment claiming an exception with no user decision behind it is a `blocker`**,
because that is an assignment overriding a rule.

---

## Pre-existing defects are not findings against this unit

[refactor-backlog.md](refactor-backlog.md) records every known defect. An item listed
there, **in a line the unit did not touch**, is not a finding against that unit. Say in
your entry that you saw it and that it is already recorded.

**A defect the unit touched is the unit's, backlog or not.** Moving a line makes it
yours.

---

## Evidence, or it is an opinion

Every finding carries **one line of evidence**: a `file:line`, or the command and its
output.

A finding without evidence is an opinion, and an opinion cannot be answered by number in
a revision round.

## Length is never a finding on its own

A 300-line deterministic function with a fixed signature is fine. A three-entry
registry keyed by data is not. Rank by what the code **does**, never by how much of it
there is.
