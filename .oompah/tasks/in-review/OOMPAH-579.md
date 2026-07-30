---
id: OOMPAH-579
type: task
status: In Review
priority: null
title: Prune branchless terminal legacy epic-task worktrees
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T03:54:54.485192Z'
updated_at: '2026-07-30T04:03:12.613877Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 8ccb18c9f5940ac30b5b05d69de5e8b93464e2e2b55f3bb6bda3cac6cd52d40a
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-30T03:57:15.515900+00:00'
  matched_identifiers: []
  evidence: 'Focus handoff: duplicate_detector


    Duplicate preflight verdict: no_duplicate


    Matches: none


    Evidence: OOMPAH-578 and OOMPAH-561 are terminal historical tasks. Active OOMPAH-576,
    OOMPAH-459, OOMPAH-489, OOMPAH-281, and OOMPAH-282 cover distinct integration,
    auditing, CI, or migration concerns.'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 0f81df32-5dec-411c-99ac-8eae3640cda0
oompah.task_costs:
  total_input_tokens: 835929
  total_output_tokens: 3294
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 835929
      output_tokens: 3294
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 835643
    output_tokens: 3233
    cost_usd: 0.0
    recorded_at: '2026-07-30T03:57:15.514800+00:00'
  - profile: default
    model: haiku
    input_tokens: 286
    output_tokens: 61
    cost_usd: 0.0
    recorded_at: '2026-07-30T04:03:11.012705+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-579__20260730T035552Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-579
    source_sha: 98c6189d302507cd77248d1fd54ad723e0166fde
    completed_at: '2026-07-30T03:57:15.524576+00:00'
---
## Summary

Triggered by live verification of OOMPAH-578. Implementation scope: when a Merged/Archived non-epic task has no work_branch metadata, detect the old Oompah layout only if its exact managed epic-<same-task-identifier> worktree directory exists; use that exact branch/worktree as the cleanup candidate. Do not infer arbitrary branches, shared parent epic branches, or unregistered paths. Relevant code: oompah/projects.py and tests/test_projects.py. Tests: run the real bare-remote legacy cleanup scenario both with explicit legacy branch metadata and with branch_name omitted; prove worktree/local/remote refs are removed, while shared-parent and arbitrary branches remain rejected. Acceptance criteria: archived OOMPAH-310-style workspaces are pruned on the normal cleanup pass without widening ownership beyond exact managed same-identifier paths; focused tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 03:55
---
Live reproduction confirmed OOMPAH-310 is Archived with work_branch unset while its exact managed epic-OOMPAH-310 worktree and branch remain. Implemented same-identifier managed-path fallback only; testing explicit and absent metadata paths against a real bare remote.
---
author: oompah
created: 2026-07-30 03:55
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-30 03:55
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-30 03:57
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 13
- Tokens: 835.6K in / 3.2K out [838.9K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 28s
- Log: OOMPAH-579__20260730T035552Z.jsonl
---
author: oompah
created: 2026-07-30 03:57
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-30 03:57
---
Focus: Refactoring Specialist
---
author: oompah
created: 2026-07-30 04:00
---
The full gate reproduced the unrelated 1-second maintenance-lane wall-clock flake fixed at OOMPAH-459 commit 95581aca5 (13,618 other tests passed). Carried the identical structural 60s-vs-15s stabilization so this branch can pass its required gate now; repeated the formerly flaky test 10/10 successfully and kept the structural non-blocking assertion unchanged.
---
author: oompah
created: 2026-07-30 04:03
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 0, Tool calls: 17
- Tokens: 286 in / 61 out [347 total]
- Cost: $0.0000
- Exit: terminated, Duration: 5m 46s
- Log: OOMPAH-579__20260730T035729Z.jsonl
---
<!-- COMMENTS:END -->
