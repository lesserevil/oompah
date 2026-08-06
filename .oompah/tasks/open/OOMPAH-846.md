---
id: OOMPAH-846
type: bug
status: Open
priority: 1
title: Enforce validation-resource leases for every spawned worker command path
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-06T04:12:19.034116Z'
updated_at: '2026-08-06T04:12:35.723528Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Live regression on 2026-08-06 after OOMPAH-816 reached Done: while the exact OOMPAH-831 gate owned the sole validation-resource slot, the OOMPAH-808 worker launched raw focused pytest and the OOMPAH-844 worker launched a raw make test process outside the durable lease. OOMPAH-844 make test remained alive when the scheduler started OOMPAH-791 exact gate, recreating the host saturation that OOMPAH-816 promised to prevent. OOMPAH-784/O845 commands used the mediated path and waited, proving command-path-dependent enforcement. Implementation scope: trace every spawned provider/native worker shell path (Codex/Claude/OpenCode/API/ACP) and install one fail-closed validation-resource guard before process launch; classify full Make targets and substantial pytest commands consistently; ensure exact gates own priority, queue time does not consume runtime deadline, cancellation/restart/fencing are preserved, and no environment/path variation can bypass the guard. Reuse OOMPAH-816 validation_resource_lease rather than building a parallel lock. Surface normal waits as informational and make bypass attempts observable without leaking command contents. Required tests: provider-native command execution from every backend while an exact gate owns capacity; raw make test, python -m pytest, uv run pytest, multi-file and compound commands; bounded node/small-file policy; cancellation/restart/owner death; prove at the process table boundary that no heavyweight child is spawned until lease acquisition; exact gate begins immediately after an earlier worker release. Acceptance: at configured capacity 1, no combination of server-spawned worker/auditor commands and exact gates can produce two concurrent heavyweight pytest trees, and all existing OOMPAH-816 security, timeout, fairness, and evidence-reuse tests remain green.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

