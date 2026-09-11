---
name: verification
description: Use when checking whether an implementation satisfies a specification, acceptance criteria, or bug fix. Produces evidence instead of relying on an agent's claim that work is complete.
---

# Verification

Translate each acceptance criterion into an observable check before declaring
the task done.

Use the strongest practical evidence:

- automated tests for behavior covered by the suite;
- type checks, linters, and builds for structural correctness;
- focused reproduction for bug fixes;
- manual checks for UI, audio, workflow, or other human-judged behavior.

For every criterion, record `pass`, `fail`, or `not verified` with the command
or observation supporting it. A passing test suite does not prove an
unverified product or user-experience requirement.

Stop and report `blocked` when the required evidence cannot be produced because
of missing data, credentials, hardware, or an unresolved product decision.
