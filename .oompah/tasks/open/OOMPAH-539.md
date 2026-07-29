---
id: OOMPAH-539
type: task
status: Open
priority: null
title: Keep Open-task duplicate-screening board state synchronized with live workers
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-29T00:43:25.964028Z'
updated_at: '2026-07-29T02:13:01.046283Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 7ec666279170df02c313e16207813bf4b9b572e4924eef4bcfaada25dfd17744
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 70934619-4a85-4309-b28f-faadfdbe9fdd
  claim_owner: 5d80b10c-0ace-4fc9-8e33-587cf319fe4d
  claimed_at: '2026-07-29T02:12:55.143967+00:00'
  claim_expires_at: '2026-07-29T02:42:55.143967+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: bda0bdf0-412e-412b-a93c-05616cd942d7
---
## Summary

Production observation on 2026-07-29 while OOMPAH-538 was being screened. The live /api/v1/state payload correctly reported OOMPAH-538 with work_kind=duplicate_screening and duplicate_preflight=true, but /api/v1/issues continued to serialize the same Open task as duplicate_screening.state=unchecked for roughly the active run. Near completion the inverse occurred: the board snapshot reported running after the live worker had exited and the canonical state-branch record already contained a checked no_duplicate verdict. This makes operators believe no Open tasks are being screened.\n\nImplementation scope:\n- Invalidate and refresh the issue-board snapshot when a duplicate-preflight claim is acquired, renewed/released, or completed.\n- Broadcast the refreshed canonical issue data after the tracker mutation, while retaining the separate live running-agent chip.\n- Preserve the task's Open column placement and do not optimistically mark preflight as In Progress.\n- Avoid a stale payload-before-refresh ordering that can overwrite a newer screening badge.\n\nRequired tests:\n- Claim acquisition changes an Open card from unchecked to running promptly in the issues payload/WebSocket update.\n- Completion changes running to checked (or duplicate candidate/retry) promptly and cannot regress to an older snapshot.\n- Worker state and issue summary agree through start, renewal, completion, and failure races.\n- Normal implementation optimistic movement remains unchanged. Run focused dashboard/server snapshot tests and make test.\n\nAcceptance criteria:\nDuring a live Open-task preflight, both the running-agent chip and the Open card/detail panel show screening; after exit, all surfaces show the final canonical verdict within the normal UI refresh window; no stale update can reverse the displayed lifecycle; and the task never appears In Progress solely because of screening.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 02:12
---
Duplicate screening dispatched (profile: standard, task remains Open)
---
author: oompah
created: 2026-07-29 02:12
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
