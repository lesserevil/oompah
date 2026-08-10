---
id: OOMPAH-1004
type: bug
status: In Progress
priority: 1
title: Resolve current dependency status in universal workflow facts
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-10T19:36:11.713277Z'
updated_at: '2026-08-10T20:27:35.693854Z'
work_branch: OOMPAH-1004
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: dependency-facts-resolve-native-status-v1
  request_fingerprint: 7e9eaed0dfd97d85c04dd29c6a82ef37b84d987156a190ca74e6b12e65a27a9c
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1004
  head_sha: 5d4439b495f17b3dc324d9bf339ccf57457af84a
  submitted_at: '2026-08-10T20:27:25.399860+00:00'
  updated_at: '2026-08-10T20:27:25.399860+00:00'
oompah.work_branch: OOMPAH-1004
---
## Summary

Triggered by: OOMPAH-1001

Problem: native Markdown task adapters materialize blocked_by/start_blocked_by as BlockerRef values without state, while WorkflowFactCollector serializes those references directly. canonicalize_status(None) becomes Backlog, so Ready to Integrate tasks can be held indefinitely even when the state-branch dependency is Merged; OOMPAH-1001 depending on OOMPAH-1000 reproduces this. Scope: make universal fact collection resolve every dependency from the same project-scoped authoritative tracker generation (or fail closed as unavailable), preserve generation/CAS consistency, and avoid N+1 or stale-cache races. Relevant files: oompah/workflow_facts.py, oompah/workflow_controller.py/orchestrator integration, native Markdown tracker behavior, and work-decision tests. Required tests: a native Markdown Ready to Integrate task with a Merged hard-start dependency is runnable for integration; an Open dependency remains blocked; missing/error/cross-project dependencies fail closed; a concurrent dependency state move cannot publish a mixed generation; bounded full/shadow scans agree after restart. Acceptance: no dependency is reported as Backlog merely because BlockerRef.state is absent, OOMPAH-1001-shaped integration proceeds naturally, and focused plus complete Makefile gates pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-10 20:27
---
Implementation is complete and pushed at exact head 5d4439b495f17b3dc324d9bf339ccf57457af84a. Dependency states now come from one canonical same-generation project corpus; missing, cross-project, and ambiguous dependencies fail closed; canonical alias collisions are rejected; cache invalidation is serialized with record/status materialization; and publication globally supersedes dependency-target changes while preserving scoped exclusion for unrelated audit churn. Validation: 563 focused tests plus 9 independent adversarial regressions passed, with terminal mutation, secret, diff, and attribution checks green.
---
author: oompah
created: 2026-08-10 20:27
---
Resolve dependency status from authoritative same-generation workflow facts
---
<!-- COMMENTS:END -->
