---
name: empire-dispatch
description: Use when working on a task received through Empire (a Hermes-dispatched headless job) or interpreting an Empire dispatch note. Defines the delivery contract, acceptance evidence, and escalation behavior.
---

# Empire Dispatch Work

Hermes (the Empire controller) dispatches a single headless agent to complete
one job. Hermes owns the outer job: dispatch-note status, attempts, timeout,
notifications, and human review. You own the actual work.

## Before working

Read the dispatch note's task, personality, repository, mode, limits, and every
acceptance criterion. Treat acceptance criteria as the definition of done. Do
not expand the task because a related improvement seems useful.

## While working

- Keep changes inside the assigned repository or run workspace.
- Work within the note's timeout and attempt budget; stop rather than loop.
- Ask for clarification (and report `blocked`) when a requirement or criterion
  is ambiguous.

## Delivery contract

When the work is complete, write two files in your run directory:

- `result.json` — machine-readable; exactly one `criteria` entry per acceptance
  criterion, each with `met` and concrete evidence.
- `report.md` — the human-readable deliverable.

Do not edit the dispatch note. Hermes owns the note's frontmatter, Run Log, and
Result.

## Completion report

Report:

1. What changed.
2. How each acceptance criterion was checked.
3. Tests, linters, or manual checks actually run.
4. Artifacts produced.
5. Remaining risks and human decisions needed.
