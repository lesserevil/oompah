---
id: OOMPAH-926
type: bug
status: Backlog
priority: 1
title: Do not invalidate shadow qualification during a mixed-mode graceful restart
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-08T21:02:52.502402Z'
updated_at: '2026-08-08T21:02:52.502402Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Live staged rollout regression on 2026-08-08 at bdabac3ff. After a five-minute all-shadow production canary passed (31 samples), implementation was promoted to enforce in a mixed read-only map and its canary passed. The next make graceful, promoting review, quiesced during an active full-sync reconcile. WorkflowRuntime.drain timed out/fenced that reconcile and persisted a failed review shadow sweep. Startup then failed closed with WorkflowRolloutGateError: review: latest shadow sweep did not succeed, stopped the service, and the generic error watcher incorrectly deduplicated the separate failure into OOMPAH-924. Rolling .env back to all-shadow and make restart restored service. Implementation scope: make graceful shutdown/cancellation neutral to per-domain rollout qualification so operator-requested quiesce cannot turn a previously successful shadow sample into a failed sample; preserve genuine reconcile failures; ensure bounded drain/ack remains safe; and classify rollout gate startup rejection separately from Orchestrator thread crashes. Relevant code: oompah/workflow_runtime.py reconcile/shadow sweep recording, oompah/workflow_jobs.py rollout evidence, oompah/orchestrator.py drain, and oompah/__main__.py error watching. Required tests: active mixed-mode reconcile plus graceful drain retains latest successful shadow evidence; genuine reconcile failure still invalidates promotion; sequential implementation then review promotion can restart; startup gate rejection is reported as its own actionable issue and does not deduplicate OOMPAH-924. Acceptance: repeat staged rollout without qualification poisoning or service outage, focused tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

