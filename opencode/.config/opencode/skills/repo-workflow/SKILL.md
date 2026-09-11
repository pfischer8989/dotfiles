---
name: repo-workflow
description: Use when implementing, debugging, reviewing, or investigating code in a repository. Keeps agent changes isolated, scoped, and reviewable.
---

# Repository Workflow

## Inspect first

- Identify the repository root and current branch/worktree.
- Read local instructions such as `AGENTS.md`, `CLAUDE.md`, and contribution
  guidance before editing.
- Inspect the relevant code, tests, and recent history.

## Make focused changes

- Prefer the smallest correct change.
- Preserve unrelated user changes.
- Do not rewrite or delete work you did not create.
- Keep generated files and dependencies out of the change unless required.

## Verify

- Run the repository's documented formatter, linter, and tests where relevant.
- Re-run focused checks after fixing failures.
- Report commands and outcomes, including skipped checks and why they were
  skipped.

Do not merge, push, publish, or release unless the task explicitly authorizes
that action. Firstmate owns worktree and delivery mechanics.
