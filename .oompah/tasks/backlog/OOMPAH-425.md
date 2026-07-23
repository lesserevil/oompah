---
id: OOMPAH-425
type: feature
status: Backlog
priority: 1
title: Auto-scale agent concurrency when configured as zero
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-23T20:45:34.887827Z'
updated_at: '2026-07-23T20:48:48.053781Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Support OOMPAH_MAX_CONCURRENT_AGENTS=0 as automatic capacity mode. Recalculate the effective concurrency cap on every scheduler tick using live CPU and available-memory capacity, while never terminating already-running agents if the calculated cap falls below the current running count. Preserve positive values as fixed caps, expose the effective cap in the runtime snapshot, document the environment setting, and add deterministic regression tests for scaling, tick reevaluation, and no-kill behavior. Run make test.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-23 20:48
---
Implemented auto concurrency mode: configuration value 0 recalculates a conservative CPU/memory-based effective cap at every scheduler tick, never terminates agents when capacity drops, and exposes configured/effective limits in the runtime snapshot. Added regression coverage and ran make test successfully. Host .env has been set to 0 and will be applied on restart.
---
<!-- COMMENTS:END -->
