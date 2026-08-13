---
id: OOMPAH-1233
type: task
status: Open
priority: null
title: Recognize landed standalone submissions after source branch deletion
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T10:25:26.660518Z'
updated_at: '2026-08-13T10:26:00.565280Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: oompah
  operation_kind: api_task_create
  creation_marker: 6b34eecc-c88d-485e-86a2-e62b75d7493a
  request_fingerprint: aa782013cdbafb0b5c541f0295c2ecb65e5297e67b4c97a81dbdd9875bbac022
oompah.lifecycle_revision: 1
---
## Summary

Bug reproduced live on TRICKLE-140. A standalone task reached Ready to Integrate with accepted immutable head 6d089ed666372e2fe5a4c732e4da6dbfae68d3c4 already contained by the configured target branch, while the GitLab source branch had been deleted after merge. Standalone delivery checks get_branch_head_sha first, emits an actionable missing-branch alert, retries five times, and exhausts before invoking the existing immutable-head containment/no-op terminalization path. Implementation scope: when the accepted submission head is present but the source branch is absent, prove the exact accepted head against a freshly fetched configured target branch; if contained, persist canonical standalone integrated/no-op evidence and enter terminal audit without creating a review; if not contained or proof is unavailable, preserve the current fail-closed actionable missing-branch behavior. Fence every proof and tracker write with the exact standalone delivery authority/generation and do not infer containment from review state alone. Required tests: deleted source plus exact head contained terminalizes without forge review; deleted source plus head not contained alerts; target fetch/proof failure alerts; authority changes during containment cannot write; replay/restart is idempotent; unrelated missing branches retain current behavior. Acceptance: TRICKLE-140-shaped already-landed work cannot exhaust delivery solely because the forge deleted its source branch, while genuinely undelivered or ambiguous work remains blocked, and focused standalone delivery/workflow job tests plus the complete Makefile gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-13 10:26
---
Claimed directly by the operator agent while the Oompah project remains paused. Reproduced on TRICKLE-140: accepted head is already on target, but standalone delivery exhausts at the earlier source-branch existence check. Implementing on branch OOMPAH-1233 with exact-head containment and authority-fencing regressions.
---
<!-- COMMENTS:END -->
