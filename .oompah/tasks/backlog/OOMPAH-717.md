---
id: OOMPAH-717
type: task
status: Backlog
priority: null
title: Prevent generated hook collisions from hot-looping and starving epic integration
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-03T13:00:53.157839Z'
updated_at: '2026-08-03T13:00:53.157839Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Live reproduction: NODEVIRT-8 remained Ready to Integrate for more than 3,400 automatic attempts. Its task head tracks .oompah-no-hooks/prepare-commit-msg while the shared epic worktree contains the same Oompah-generated helper as an untracked file. The executor fast-forward therefore fails because the untracked helper would be overwritten. Error selection reports the successful checkout stderr (Already on epic-NODEVIRT-2) instead of the failing merge stderr, classifies the result as an epic-head race, and retries immediately without backoff or an attempt bound. Dependent Ready rows remain at attempts=0.

Implementation scope:
- Treat every Oompah-generated worktree helper path as non-deliverable at submission and integration boundaries, including legacy task heads that already track a helper. Reject with an actionable repair status or sanitize through an explicit safe repair path before mutating the shared epic branch.
- In the integration executor, report stderr from the command that actually failed; successful checkout output must never mask reset or merge failures.
- Distinguish genuine remote epic-head compare-and-swap races from deterministic local preparation/merge failures. Do not classify untracked-file collisions as immediately retryable epic-head races.
- Add bounded retry/backoff and head-of-line protection so one repeatedly failing row cannot hot-loop thousands of times or prevent independent eligible queue groups from progressing.
- Surface an alert/health diagnostic for excessive Ready attempts with the exact task, failing step, real error, next retry, and repair action.

Relevant code: oompah/integration_executor.py, oompah/integration_queue.py, oompah/orchestrator.py integration routing and queue health, ProjectStore generated-helper handling, and dashboard integration diagnostics.

Required tests:
- Reproduce a shared epic worktree with an untracked .oompah-no-hooks/prepare-commit-msg and a submitted task head that tracks that path; prove the real collision is reported and no immediate retry loop occurs.
- Prove successful checkout stderr cannot mask a failing reset or merge.
- Prove a genuine epic compare-and-swap race remains retryable.
- Prove a poisoned row is bounded/backed off and another independent eligible epic/project row advances.
- Prove clean task heads still integrate normally and generated helpers never enter delivered trees.

Acceptance criteria:
- The NODEVIRT-8 reproduction cannot exceed the configured retry budget or monopolize integration processing.
- Operators see the real untracked-file collision and a safe repair path.
- Independent Ready work proceeds while the failed row waits.
- Focused integration executor/queue/orchestrator/ProjectStore tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

