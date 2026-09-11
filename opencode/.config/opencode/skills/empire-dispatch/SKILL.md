---
name: empire-dispatch
description: Use when working on a task received through Empire or interpreting an Empire dispatch note. Defines the outer-job boundary, acceptance evidence, and escalation behavior.
---

# Empire Dispatch Work

Empire has two layers:

- Hermes owns the outer job: dispatch-note status, attempts, timeout, Telegram,
  and human review.
- Firstmate owns the coding run: crew tasks, worktrees, agent prompts, reviews,
  tests, and artifacts.

## Before working

Read the dispatch note's task, repository, mode, limits, and every acceptance
criterion. Treat acceptance criteria as the definition of done. Do not expand
the task because a related improvement seems useful.

## While working

- Keep changes inside the assigned repository and worktree.
- Use the configured Firstmate and Herdr workflow; do not create an alternate
  supervisor or bypass the task limits.
- Keep iteration and runtime bounded by the dispatch note.
- Ask for clarification when a requirement or acceptance criterion is
  ambiguous.

## Completion report

Report:

1. What changed.
2. How each acceptance criterion was checked.
3. Tests, linters, or manual checks actually run.
4. Artifacts, commits, or PRs produced.
5. Remaining risks and human decisions needed.

Do not silently change the Empire frontmatter. Return the result to Firstmate;
Hermes owns the dispatch note's outer status.
