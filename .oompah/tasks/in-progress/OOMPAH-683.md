---
id: OOMPAH-683
type: task
status: In Progress
priority: null
title: Make retry recovery snapshots tolerate generated hooks and in-progress rebases
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-01T21:41:35.163259Z'
updated_at: '2026-08-01T21:48:09.804620Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 3114887b63299d36a0155e1dc831ca696d01549ed766eaa53b8d839fe5273e51
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-01T21:47:17.723740+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector  \nDuplicate preflight verdict: no_duplicate\
    \  \nMatches: none  \nEvidence: Active tasks OOMPAH-281 and OOMPAH-282 are unrelated.\
    \ Archived OOMPAH-268/270 cover Git lock retries, while OOMPAH-204/235 cover native-tracker\
    \ rebase recovery; none address retry recovery snapshots, generated helpers, or\
    \ detached in-progress rebases. No active duplicate was found."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 9454ca3e-2248-46d2-8a80-66bd0eea1d36
oompah.task_costs:
  total_input_tokens: 431343
  total_output_tokens: 2396
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 431343
      output_tokens: 2396
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 431343
    output_tokens: 2396
    cost_usd: 0.0
    recorded_at: '2026-08-01T21:47:17.711768+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-683__20260801T214545Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-683
    source_sha: 3d50e86c334e8a6318b767b281bc254fa6d93cc2
    completed_at: '2026-08-01T21:47:17.738461+00:00'
---
## Summary

Live recovery failures on 2026-08-01 stranded EXOCOMP-145 and OOMPAH-682 because the retry snapshot attempted to stage the generated/ignored .oompah-no-hooks helper, and stranded EXOCOMP-184 because its preserved worktree was detached during an active rebase. In all cases Oompah correctly left the worktree untouched but moved the task to Needs Human, requiring manual reconciliation.

Implementation scope:
- Treat .oompah-no-hooks and all other Oompah-generated worktree helpers as non-deliverable recovery artifacts. Snapshot tracked, staged, and legitimate untracked task work without passing ignored helper paths to git add.
- Detect active rebase/merge/cherry-pick state and detached HEAD before snapshotting. Preserve branch identity, index, operation metadata, and reachable commits without invoking an interactive Git command or losing conflict resolutions.
- If an operation can be safely completed or checkpointed non-interactively, do so through an explicit bounded path; otherwise leave the worktree and branch fully recoverable with precise evidence and no destructive reset.
- Ensure retry cleanup never deletes generated helpers until all task changes are durably reachable, and remove helpers before cleanliness/submission checks.
- Add operator-visible diagnostics that distinguish ignored-helper exclusion, active-operation preservation, and genuine unrecoverable corruption.

Relevant code: orchestrator worker-exit/retry recovery snapshot paths, workspace/project Git helpers, generated hook installation, git_noninteractive policy, and retry tests.

Required tests:
- A dirty task worktree containing ignored .oompah-no-hooks/prepare-commit-msg snapshots successfully without adding the helper.
- A detached HEAD in an active rebase retains the branch/ref, staged conflict resolution, todo state, and commits across recovery.
- A generated helper is absent from submitted branch history and cannot make an otherwise-clean worktree fail submission.
- Late/concurrent retry cleanup cannot overwrite a newer worker generation or remove unsnapshotted changes.
- No recovery path launches an editor or interactive Git command.

Acceptance criteria:
- The EXOCOMP-145/OOMPAH-682 ignored-helper and EXOCOMP-184 detached-rebase reproductions recover automatically without Needs Human or lost work.
- Recovered branches remain pushable and task submission sees the exact intended head.
- Focused recovery/workspace tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-01 21:45
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-01 21:45
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-01 21:47
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 9
- Tokens: 431.3K in / 2.4K out [433.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 36s
- Log: OOMPAH-683__20260801T214545Z.jsonl
---
author: oompah
created: 2026-08-01 21:48
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-01 21:48
---
Focus: Callback Auth Validation Specialist
---
<!-- COMMENTS:END -->
