---
id: OOMPAH-644
type: task
status: Open
priority: null
title: Make native task reads atomic across status-file moves
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T06:46:11.947079Z'
updated_at: '2026-07-31T06:46:52.369635Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 1bb676715f409182ac83e05ff8bfffa52da5656fb7b87cab02dc40fc1e0c7c2a
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 7e236575-564d-4685-8842-3e4a53f8da2e
  claim_owner: d12922aa-baf6-4258-aa45-02da3deea710
  claimed_at: '2026-07-31T06:46:47.861471+00:00'
  claim_expires_at: '2026-07-31T07:16:47.861471+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: c80aa962-3ce2-4ebd-9ac9-56d67a2e7e32
---
## Summary

Live scheduler evidence on 2026-07-31 reproduced a native Markdown tracker race twice: while OOMPAH-621 moved through Open/Ready at 06:03 and OOMPAH-641 moved through Ready at 06:34, a concurrent reader enumerated the old status path and then received ENOENT opening .oompah/tasks/<old-status>/<task>.md. The tracker logged the valid task as corrupt and stated that dispatch would be suppressed, even though the file already existed at its new canonical status path and the task later recovered.

Implementation scope: make OompahMdTracker reads consistent with concurrent CLI/server status transitions and state-branch commits. A fetch that observes ENOENT after enumeration must distinguish an atomic status-file move from true disappearance/corruption, refresh the task index or resolve the identifier across canonical status directories under the tracker write/read synchronization boundary, and retry against one authoritative state-branch generation. Do not restore files by hand or weaken true malformed/missing-file detection. Review fetch_all_issues/fetch_issue_detail path caching, status update rename/commit ordering, state-worktree locking, and scheduler corruption diagnostics.

Required tests: deterministic barrier between path enumeration and file open while another writer moves Open to Ready and Ready to In Progress; concurrent comment plus status update; repeated rapid status changes; state-branch refresh/commit generation change; deleted or malformed file remains an actionable corruption error; multi-process or separate tracker-instance reproduction if production uses separate instances. Acceptance: no transient ENOENT/corrupt warning or dispatch suppression for an intact moved task, readers return either the pre-move or post-move coherent record, true corruption still fails closed, focused native-tracker concurrency tests and terminal mutation scan pass, and make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-31 06:46
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-31 06:46
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
