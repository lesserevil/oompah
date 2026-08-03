---
id: OOMPAH-717
type: task
status: Open
priority: null
title: Prevent generated hook collisions from hot-looping and starving epic integration
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-03T13:00:53.157839Z'
updated_at: '2026-08-03T13:01:13.036195Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: d8ace93bf4e88a08c6506eeec48f53bb3de7feb3979aff430a84719b449ac79f
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 8912f7db-63b8-4e76-928b-a9354c53e33d
  claim_owner: 2dcc53e1-cdcd-4522-a08d-de6ce4222a8c
  claimed_at: '2026-08-03T13:01:06.494950+00:00'
  claim_expires_at: '2026-08-03T13:31:06.494950+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: e1122226-469d-4ad0-81d6-0ef4633edb82
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

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-03 13:01
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-03 13:01
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
