---
id: OOMPAH-647
type: task
status: Open
priority: null
title: Make merge-conflict rebase continuation noninteractive and deadlock-safe
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T07:09:27.752943Z'
updated_at: '2026-07-31T07:09:54.855771Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 68fcb9c97245c8ffaa75c53536a9ffa3c84fea1bb8ec55c467315ac0a4a26565
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 3ccaf8fa-ba3f-42ff-a0f4-db8841e126bd
  claim_owner: d12922aa-baf6-4258-aa45-02da3deea710
  claimed_at: '2026-07-31T07:09:45.978655+00:00'
  claim_expires_at: '2026-07-31T07:39:45.978655+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: cf80fb4f-be29-4cd9-86d1-77f7aa70023d
---
## Summary

Live deadlock on 2026-07-31 while recovering OOMPAH-643/PR #610: the Merge Conflict Resolver correctly resolved and staged terminal_transition_coordinator.py, then ran 'git add ... && git rebase --continue'. Git spawned /usr/bin/vi on .git/worktrees/OOMPAH-643/COMMIT_EDITMSG and the ACP tool call blocked from 07:05:37 until the operator terminated only the editor PID at 07:08:40; the same agent then resumed and completed the rebase at 2b3a967c8. Implementation scope: ensure every server-generated merge/rebase continuation path is explicitly noninteractive (for example GIT_EDITOR=true/GIT_SEQUENCE_EDITOR=true or git -c core.editor=true as appropriate), preserves the original commit message and required attribution trailer, and cannot inherit an interactive editor from the host. Add bounded command monitoring so an unexpected editor/prompt is terminated and reported/retried without discarding staged conflict resolution. Cover resolver prompts, command wrappers/MCP policy, retry/recovery, and any automated rebase helpers. Required tests: real repository conflict with an unset editor; hostile EDITOR pointing to a blocking executable that must never be invoked; continuation success and preserved message/trailers; unexpected prompt timeout retains recoverable rebase state; repeated recovery is idempotent. Acceptance: OOMPAH-643-style rebase continuation completes unattended, no vi/editor child can deadlock an agent slot, focused conflict-resolver/process tests and terminal mutation scan pass, and make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-31 07:09
---
Duplicate screening dispatched (profile: standard, task remains Open)
---
author: oompah
created: 2026-07-31 07:09
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
