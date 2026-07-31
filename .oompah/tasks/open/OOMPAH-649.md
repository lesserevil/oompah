---
id: OOMPAH-649
type: task
status: Open
priority: null
title: Preserve dirty task worktrees across worker termination and retry
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T07:19:33.053515Z'
updated_at: '2026-07-31T07:19:57.690100Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 34b7218c890759bfab1fc1575e53815c1060649d03e9dae5e880401024c8464e
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 913e3cb4-4f87-48df-9661-5d7b878c5efc
  claim_owner: d12922aa-baf6-4258-aa45-02da3deea710
  claimed_at: '2026-07-31T07:19:49.635543+00:00'
  claim_expires_at: '2026-07-31T07:49:49.635543+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 8c89fc06-7400-475f-adc1-ccca7397ed24
---
## Summary

Live data-loss reproduction on 2026-07-31: OOMPAH-645's first worker produced and focused-tested 317 lines across terminal_audit_health.py, orchestrator.py, dashboard.html, and three test files; the operator verified those modifications in the managed worktree. The healthy pytest child was then false-stall terminated with cleanup=False at 07:13:42. Before retry launch, managed worktree reflog recorded 'HEAD@{07:14:19}: reset: moving to HEAD'; the second agent started on a clean 1dc3f53e5 tree with no task commit or stash and had to reimplement the work. OOMPAH-644 similarly entered retry after a reset and reconstructed preserved intent. Implementation scope: worker retry preparation must never discard staged, unstaged, or untracked task-owned changes. Before any reset/sync/rebase, detect dirtiness and preserve it durably via a task-scoped recovery commit/ref or equivalent atomic snapshot; preferably reuse the dirty worktree directly when the branch/head authority still matches. A new attempt must receive explicit recovery context and the exact prior filesystem state. Fail closed on snapshot failure and route to Needs Human rather than running reset --hard. Terminal cleanup may remove a worktree only after committed/pushed/merged evidence or an explicit owner-approved disposition. Relevant files: Projects.ensure/create/reset worktree paths, retry dispatch, agent termination cleanup, branch synchronization, recovery metadata, and hygiene classification. Required tests: abrupt worker termination with staged, unstaged, and untracked edits; cleanup=False retry; process restart before retry; base branch advances; snapshot failure; repeated retry idempotency; terminal cleanup; cross-task isolation. Acceptance: an OOMPAH-645-style retry exposes byte-identical prior edits to the next agent with durable recovery evidence, no task work is silently reset, focused worktree/retry tests and terminal mutation scan pass, and make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-31 07:19
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-31 07:19
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
