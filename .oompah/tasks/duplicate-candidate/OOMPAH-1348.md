---
id: OOMPAH-1348
type: task
status: Duplicate Candidate
priority: null
title: Correct GitLab merge queue semantics and stale Trickle MR handling
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-08-27T19:24:45.971039Z'
updated_at: '2026-08-27T19:43:12.999694Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: c4a5fea4-ee7a-4e35-980b-d645cc7fe1bc
  request_fingerprint: 2e238e02d703ed4a78539419ad2cf2e826aeea5fee8830e699ccd13c3a4f9aa0
oompah.lifecycle_revision: 1
---
## Summary

Investigate and fix the GitLab review/merge path exposed by the Trickle project. Current evidence: Trickle has merge_pipelines_enabled=true and merge_trains_enabled=true in GitLab, while Oompah project merge_queue_enabled=false; several stale task MRs still target main even though current accepted queue metadata targets shared epic branches; GitLab ReviewRequest normalization does not populate auto_merge_enabled or mergeable_state; GitLabProvider does not override enable_auto_merge_exact; and direct merge mode can bypass GitLab merge trains. Scope: define provider-specific queue capability/semantics, make GitLab exact-head enqueue/merge behavior explicit and fail closed, normalize GitLab queue state, prevent stale/wrong-target MRs from entering merge actions, reconcile or close superseded MRs safely, and update misleading UI/docs. Relevant files include oompah/scm.py, oompah/review_workflow_adapter.py, oompah/orchestrator.py, oompah/models.py, docs/project-bootstrap.md, tests/test_scm.py, tests/test_merge_queue.py, tests/test_gitlab_review_flows.py, and standalone delivery tests. Required tests: GitLab exact-head CAS, merge-train/MWPS behavior, queue-state observation, target/head mismatch, and a Trickle-shaped regression with old main-target MRs plus current shared-epic queue records. Acceptance: no GitLab MR is directly merged when project policy requires a merge train; no unfenced auto-merge request is used; stale/wrong-target reviews cannot mutate lifecycle state; dashboard state reflects actual GitLab queue/auto-merge state; focused and full project gates pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-27 19:43
---
Duplicate task created when the CLI request timed out after the server had committed it. Canonical investigation/fix task: OOMPAH-1350. Do not dispatch or implement this duplicate.
---
<!-- COMMENTS:END -->
