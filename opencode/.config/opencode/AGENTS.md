# OpenCode Worker Defaults

These are user-wide defaults for OpenCode across all machines. They apply to
interactive sessions and to Empire-dispatched (headless) jobs alike.

## Empire-dispatched jobs

- Read the complete task and acceptance criteria before changing files.
- Keep the work inside the assigned repository and stated scope.
- Do not merge, publish, release, send messages, or spend money without explicit
  authorization from the dispatcher.
- Treat tests and static checks as evidence. Report what was actually run and
  what was not.
- If requirements conflict, files are missing, or an action needs approval,
  stop and report `blocked` instead of guessing.
- Return a concise result containing the outcome, changed files, checks run,
  remaining risks, and decisions needed.

Use the relevant skills for dispatch context, repository workflow, and
verification. Do not edit generated agent configuration files directly.