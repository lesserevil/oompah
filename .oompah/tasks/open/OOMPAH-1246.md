---
id: OOMPAH-1246
type: task
status: Open
priority: null
title: Revalidate exact forge review evidence before exhausting standalone delivery
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T15:00:01.939071Z'
updated_at: '2026-08-13T15:00:18.727192Z'
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
  creation_marker: 7d3b2549-01ae-4e85-8efb-80b56a2d9519
  request_fingerprint: b2836bda8b9365c832a0da4bc545e530aadd3517de23c2d355a7213e697398dd
oompah.lifecycle_revision: 1
---
## Summary

Scope: prevent bounded standalone_delivery jobs from reaching retry.exhausted when the exact open forge review exists but an early provider projection temporarily lacks immutable head/base identity. Live reproduction: TRICKLE-119 accepted standalone submission head b286f1cf139f992c4d1d2da033076409c7095f70/base bf527cbd46d3f45faf14915a23e4df386f7a2ebb and GitLab MR !7 currently exposes those exact SHAs and matching repositories/branches, but workflow job 16877 exhausted after repeated "waiting for an exact forge effect" and left an action-required alert based on an earlier incomplete review observation. Update the standalone effect verification/retry boundary to perform a fresh exact-review lookup before spending the final attempt or to recognize a later complete exact observation as successor authority that safely rearms the same generation. Preserve fail-closed behavior for missing/mismatched repo, branch, target, head, or base evidence. Relevant code: standalone review matching/adoption, IntegrationWorkflowBackend effect observation, WorkflowController exhaustion authority, and GitLab review normalization. Tests must model incomplete head/base followed by an exact same-review observation and prove natural recovery without duplicate MR or operator action; mismatches must still exhaust. Acceptance: exact MR evidence clears/rearms stale exhaustion and proceeds through quality gate/adoption, while ambiguous evidence remains fenced.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-13 15:00
---
Live exact evidence verified via GitLab API after exhaustion: MR !7 source epic-TRICKLE-117--task-TRICKLE-119 -> main, head b286f1cf139f992c4d1d2da033076409c7095f70, base bf527cbd46d3f45faf14915a23e4df386f7a2ebb, state opened, mergeable, pipeline 62535729 running. The alert is therefore stale provider-observation exhaustion, not an invalid submission.
---
<!-- COMMENTS:END -->
