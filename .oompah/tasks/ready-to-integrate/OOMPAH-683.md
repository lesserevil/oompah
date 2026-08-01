---
id: OOMPAH-683
type: task
status: Ready to Integrate
priority: null
title: Make retry recovery snapshots tolerate generated hooks and in-progress rebases
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-01T21:41:35.163259Z'
updated_at: '2026-08-01T22:38:08.866868Z'
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
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-683
  head_sha: bdc4cf5d1fa259b7fa155c1f02aabda34749a103
  submitted_at: '2026-08-01T22:38:03.729346+00:00'
  updated_at: '2026-08-01T22:38:03.729346+00:00'
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
author: oompah
created: 2026-08-01 21:48
---
Understanding: I will trace retry recovery snapshotting, Git/worktree operation-state detection, generated helper cleanup, and submission checks. I will preserve active-operation state and branch identity without interactive Git commands, exclude generated helpers from snapshots/submission, add race-safe cleanup diagnostics, cover the stated reproductions with focused tests, then run the relevant Makefile checks.
---
author: oompah
created: 2026-08-01 21:53
---
Discovery: recovery is concentrated in ProjectStore._preserve_dirty_worktree_locked() and _prepare_existing_worktree(). It stages via git add --all with an exclusion pathspec, requires symbolic-ref HEAD, and therefore rejects the detached HEAD Git intentionally uses during a paused rebase. Generated-hook filtering is ad hoc and submission cleanliness still sees helpers. I will centralize helper filtering/removal, stage only enumerated deliverable paths, checkpoint active operation state without mutating rebase metadata/index beyond legitimate staging, and fence late termination cleanup on the original RunningEntry.
---
author: oompah
created: 2026-08-01 21:59
---
Implementation: recovery now enumerates changed paths and calls git add only for deliverable paths, excluding the .oompah-* generated-helper namespace; helper removal is delayed until the recovery ref is durable. Paused rebase/merge/cherry-pick/sequencer state is inspected read-only, and active operations get a commit-tree checkpoint preserving branch identity, detached HEAD, staged tree, and bounded todo/operation metadata without advancing or aborting Git's operation. Submission checks remove generated helpers before porcelain status, and forced termination skips snapshot/cleanup when a newer worker entry has taken ownership.
---
author: oompah
created: 2026-08-01 22:17
---
Oompah could not durably preserve this worker's task worktree before retry. The worktree was left in place and no reset, clean, or retry was started. Reconcile the workspace and recovery evidence manually before resuming the task. Error: could not stage recovery snapshot for OOMPAH-683: The following paths are ignored by one of your .gitignore files:
.oompah-no-hooks
hint: Use -f if you really want to add them.
hint: Disable this message with "git config set advice.addIgnoredFile false"
---
author: oompah
created: 2026-08-01 22:38
---
Operator-owned recovery complete. The preserved implementation was reviewed, the generated .oompah-no-hooks helper was removed, and the exact task tree was committed and pushed as bdc4cf5d1fa259b7fa155c1f02aabda34749a103.\n\nValidation:\n- Focused recovery/submission/race suite: 181 passed in 28.81s.\n- Full make test: 14857 passed, 7 skipped, 1 xfailed in 402.78s.\n- The first full run had one unrelated one-second tick-lane timeout while another repository-wide gate was contending for resources; that exact test passed alone, the competing gate ended, and the complete make test rerun passed.\n- git diff --check passed.\n- Branch is clean and matches origin/OOMPAH-683.\n\nThis task is itself the canonical fix for the ignored-helper recovery failure that moved it to Needs Human, so no duplicate follow-up was filed.
---
author: oompah
created: 2026-08-01 22:38
---
Operator recovery complete at bdc4cf5d1: ignored generated helpers are excluded, active Git operations receive durable noninteractive checkpoints, stale cleanup is generation-fenced, focused tests pass 181/181, and full make test passes 14857 tests.
---
<!-- COMMENTS:END -->
