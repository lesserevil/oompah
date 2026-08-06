---
id: OOMPAH-865
type: bug
status: Open
priority: null
title: Reserve an independent auditor candidate across contributor retry rotation
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-06T19:09:44.116383Z'
updated_at: '2026-08-06T19:10:32.474177Z'
work_branch: epic-OOMPAH-763--task-OOMPAH-865
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: b4dc339f6dba0ade744e546e15885f0eab90407a123aa5eed4782a0efb82241e
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 8bbd84ae-12a2-4801-97d6-dfe57083f3ec
  claim_owner: d499f6a6-5717-4e4a-8ad7-bc38cc47251d
  claimed_at: '2026-08-06T19:10:11.945003+00:00'
  claim_expires_at: '2026-08-06T19:40:11.945003+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 7af2d87e-b4e7-4db7-8a3a-1f06ae4f41c3
oompah.work_branch: epic-OOMPAH-763--task-OOMPAH-865
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-763--task-OOMPAH-865
  base_branch: epic-OOMPAH-763
  base_sha: 03563661c1b8998cfe5d081edddbe7313b62d10c
  updated_at: '2026-08-06T19:10:25.577168+00:00'
---
## Summary

Triggered by OOMPAH-858 after its exact full gate passed and integrated: implementation retries consumed every configured provider/model candidate (Claude haiku, sonnet, opus and Codex terra), leaving the terminal auditor selector with 'All candidates are used by contributors' and forcing Needs Human despite healthy transports. Implementation scope: make contributor candidate selection and retry escalation reserve at least one healthy auditor-role provider/model that remains independent for terminal validation, or deterministically select a contributor/auditor allocation that cannot exhaust the independence set. Cover initial dispatch, stalled-agent escalation, provider rotation, continuation/recovery, configured one-candidate impossibility, and dynamic health/config changes. Preserve provider diversity, explicit owner override semantics, contributor identity evidence, and fail-closed auditing. Relevant code: oompah/auditor_candidate_selector.py, orchestrator contributor/provider selection and retry escalation, configuration validation/health observability, terminal transition recovery. Required tests: reproduce OOMPAH-858's multi-provider retry sequence; prove a reserved independent candidate remains dispatchable; prove impossible configurations surface a pre-dispatch actionable configuration alert instead of consuming all candidates and failing only after integration; prove restart and concurrent task dispatch retain reservation correctness. Acceptance: when configuration has at least two eligible independent candidates, no task can consume the final auditor candidate through contributor retries; exact integrated work reaches an independent audit without operator intervention.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-06 19:10
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-06 19:10
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
