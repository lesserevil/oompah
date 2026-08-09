---
id: OOMPAH-939
type: task
status: In Progress
priority: null
title: Continue saturated durable workflow batches without full-sync delay
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T08:54:39.101794Z'
updated_at: '2026-08-09T09:03:37.656565Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Triggered by: OOMPAH-785\n\nProduction regression observed on 2026-08-09 while recovering the legacy Done backlog after OOMPAH-935: WorkflowRuntime._run_due processed exactly the configured 32-job batch cap, left current claimable Oompah jobs queued/due, and then remained idle until the independent 300-second FULL_SYNC safety net. The runtime transition observer wakes only for transition_applied; batches made entirely of retry/superseded/no-transition results emit no wake. _run_due reports processed but no saturation/continuation signal, so bounded work can be stranded for five minutes despite worker.accepting=true.\n\nImplementation scope: preserve bounded batches and project fairness; make the durable runtime report when a batch reaches its cap and may have more eligible work; after the current durable tick publishes its report/metrics, request exactly one coalesced REFRESH_REQUESTED continuation through the production orchestrator event loop. Do not recurse inside the tick and do not spin from raw queued counts because those include paused projects, future retries, and ineligible actions. Suppress continuation during drain/shutdown and expose bounded observability such as batch_saturated/continuation_requested. Relevant files: oompah/workflow_runtime.py, oompah/orchestrator.py, scheduler/runtime tests.\n\nRequired tests: seed more than one batch of current claimable jobs whose handlers complete/retry/supersede without transition events; prove the first production tick processes the cap and posts one coalesced continuation; prove the next tick immediately handles the suffix without FULL_SYNC; prove paused-project, future-retry, and ineligible rows do not cause a loop; preserve multi-project fairness and shutdown/drain fencing.\n\nAcceptance: current eligible work never waits for the five-minute safety net solely because the prior batch hit its cap; each continuation remains bounded/coalesced and non-recursive; no busy loop occurs for non-claimable rows; focused and complete branch gates pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 08:55
---
Accepted as the live batch-continuation regression found during OOMPAH-935 rollout.
---
author: oompah
created: 2026-08-09 09:03
---
Direct-owner fix is committed and pushed at 2bac503b1 on protected-main PR 751. The runtime now reports cap saturation and the production orchestrator posts one coalesced, shutdown-fenced continuation; future-due/ineligible rows do not rearm. Verification: 109 adjacent tests passed plus targeted lint/diff checks. Hosted complete gates are starting.
---
<!-- COMMENTS:END -->
