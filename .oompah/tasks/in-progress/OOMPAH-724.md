---
id: OOMPAH-724
type: task
status: In Progress
priority: null
title: Fence accepted submissions against post-handoff worktree mutation
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-03T15:25:39.369981Z'
updated_at: '2026-08-03T16:02:27.675375Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: dcbd5d87fe68bddd5fcdc16f34435f3f30551cc4aec892e771bb7cfba0ffefee
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-03T16:00:01.945694+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: OOMPAH-724 addresses a race condition in the submission\
    \ handoff pipeline where post-acceptance worktree mutations can cause integration\
    \ failures and unnecessary task reruns. The core issue is generation-fencing and\
    \ race-free transitions from accepted submission \u2192 worker retirement \u2192\
    \ integration eligibility. Reviewed the authoritative project task corpus (OOMPAH-724\
    \ is the only Open task; all peers are Archived terminal states). Related archived\
    \ task OOMPAH-160 (\"Make native task writes atomic and block intake reimports\
    \ for corrupt tasks\") addresses atomic writes and corruption detection in the\
    \ GitHub intake path, but not submission handoff race conditions. No active duplicate\
    \ exists.\nFocus handoff: duplicate_detector\n\nDuplicate preflight verdict: no_duplicate\n\
    \nMatches: none\n\nEvidence: OOMPAH-724 addresses a race condition in the submission\
    \ handoff pipeline where post-acceptance worktree mutations can cause integration\
    \ failures and unnecessary task reruns. The core issue is generation-fencing and\
    \ race-free transitions from accepted submission \u2192 worker retirement \u2192\
    \ integration eligibility. Reviewed the authoritative project task corpus (OOMPAH-724\
    \ is the only Open task; all peers are Archived terminal states). Related archived\
    \ task OOMPAH-160 (\"Make native task writes atomic and block intake reimports\
    \ for corrupt tasks\") addresses atomic writes and corruption detection in the\
    \ GitHub intake path, but not submission handoff race conditions. No active duplicate\
    \ exists."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 860b894d-1f4a-4903-93e7-86ebd408bd57
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 908
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 908
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 908
    cost_usd: 0.0
    recorded_at: '2026-08-03T16:00:01.945373+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-724__20260803T155909Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-724
    source_sha: d510748342777dd4748070d83391ffb0eae40091
    completed_at: '2026-08-03T16:00:01.957108+00:00'
---
## Summary

Live reproduction: EXOCOMP-172 submitted clean pushed head 113a7337cbb9efa1b07b3f23c627b477bc9ac7a5. After submission acceptance but before worker retirement completed, the managed worktree acquired a formatter-only change. Worker cleanup correctly preserved it as recovery checkpoint 9390df29c8ddb92abd66847b7767b37104313918. Integration then rejected the task because local HEAD differed from the published submitted head, moved the task back to implementation, and required another agent even though the preservation system prevented data loss.

Implementation scope:
- Make the transition from accepted worker submission to worker retirement and integration eligibility generation-fenced and race-free.
- Revoke further task mutation authority when submission is accepted, quiesce the complete managed process tree, and perform a final branch/head/cleanliness check before enqueuing integration.
- If task-owned changes appear after the accepted evidence, preserve them exactly once and reopen the task with explicit recovery context before integration is attempted; do not emit a transient Ready row that can only fail with worktree_recovery.
- Define a safe bounded path for a clean Oompah-created recovery checkpoint that is a linear descendant of the accepted pushed head. Do not silently publish or integrate unreviewed content, and never reset or discard the snapshot.
- Preserve same-head resubmission idempotency, authority-generation fencing, cleanup safety, and cross-task isolation.

Relevant code: oompah/server.py submission authority lock and persistence, oompah/orchestrator.py worker exit and submission handoff, oompah/projects.py recovery snapshots, oompah/integration_executor.py worktree recovery checks, and task CLI evidence capture.

Required tests:
- Reproduce EXOCOMP-172 with a clean pushed submit followed by a late tracked formatter change before worker exit.
- Prove integration is not attempted against stale submitted evidence and the task is reopened exactly once with the preserved checkpoint available to the next worker.
- Cover late staged, unstaged, and untracked changes; background child exit; simultaneous submit and teardown; restart recovery; repeat submit; snapshot failure; and no-change normal submission.
- Prove no task content is reset, auto-pushed, or integrated without explicit resubmission.
- Run focused submission, recovery, worker lifecycle, integration executor, and authority-race suites plus make test.

Acceptance criteria:
- An EXOCOMP-172-style late mutation cannot churn through Ready to Integrate and an integration worktree-recovery failure.
- Accepted evidence becomes integration-eligible only after the worker generation is quiescent and the final worktree state matches it.
- Late work remains durably recoverable and receives one actionable retry without data loss or duplicate dispatch.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-03 15:59
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-03 15:59
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-03 16:00
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 908 out [918 total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 0s
- Log: OOMPAH-724__20260803T155909Z.jsonl
---
author: oompah
created: 2026-08-03 16:02
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-03 16:02
---
Focus: Refactoring Specialist
---
<!-- COMMENTS:END -->
