---
id: OOMPAH-631
type: bug
status: In Progress
priority: 1
title: Restore validation ownership when terminal retries coalesce
parent: OOMPAH-584
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T00:08:00.758352Z'
updated_at: '2026-07-31T00:08:03.777963Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Implementation scope: repair explicit terminal-transition retries that coalesce with an existing pending or in-progress audit while the task has drifted out of In Validation. A successful explicit retry must atomically restore nonterminal task state to In Validation under the project transition lock, and the API/CLI response must report the actual staged state rather than claiming In Validation when no tracker write occurred. Preserve idempotent audit IDs and do not regress already terminal or Archived tasks. Relevant code: oompah/terminal_transition_coordinator.py and terminal status API/CLI interfaces. Tests: reproduce a pending Done audit whose task was raced to Needs Human, retry the identical transition, and prove the same audit is retained, status is repaired, status_repaired/status_staged are truthful, no duplicate queued comment is posted, and concurrent calls remain serialized. Acceptance criteria: an operator retry cannot leave a pending audit stranded outside In Validation; focused coordinator/interface tests and the complete Makefile gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-31 00:08
---
Claimed directly by the operator Codex session because this bug is the live deadlock preventing OOMPAH-590 from re-entering validation. Implementation will begin after OOMPAH-630's exact head finishes its currently active integration gate, avoiding a moving-head race.
---
<!-- COMMENTS:END -->
