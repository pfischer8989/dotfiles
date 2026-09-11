---
name: empire-controller
description: Use when operating Empire as the outer controller for dispatching coding work through Firstmate, Herdr, and OpenCode.
---

# Empire Controller

Hermes owns the outer Empire job. Firstmate owns the inner coding run.

## Outer-job responsibilities

- Watch the configured Empire `Dispatch/` folder for notes with `empire: true`
  and `status: ready`.
- Claim each job exactly once by recording its `job_id`, `attempt`, and
  `claimed_at` before starting work.
- Enforce `max_attempts`, `max_iterations`, and `timeout_minutes`.
- Keep the dispatch note's status authoritative. Do not let Firstmate or a
  crewmate independently rewrite its frontmatter.
- Notify Telegram only for `done`, `blocked`, or `failed` outcomes.

## Pilot execution path

The initial pilot runs on one Mac Mini:

```text
dispatch note → Firstmate primary → Herdr backend → OpenCode crewmates
```

Start one Firstmate home/session and give it the task, repository, mode, limits,
and acceptance criteria from the dispatch note. Do not launch individual
crewmates directly when Firstmate is available.

## Ownership boundary

Firstmate owns decomposition, isolated worktrees, crew prompts, implementation,
reviews, tests, and artifacts. Hermes owns job state, outer timeout, attempts,
the dispatch note, Telegram, and escalation.

## Escalate instead of guessing

Set the job to `blocked` and notify the captain when requirements conflict,
credentials are missing, the repository is unavailable, an acceptance criterion
is ambiguous, or Firstmate needs a product decision. Set it to `failed` for a
timeout, crash, or exhausted retry budget. Never silently retry indefinitely.

## Completion report

Before marking a job `done`, require a result containing:

- changed files or artifacts;
- acceptance evidence for every criterion;
- tests and checks actually run;
- remaining risks;
- decisions requiring human review.
