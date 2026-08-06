---
id: OOMPAH-865
type: bug
status: Backlog
priority: null
title: Reserve an independent auditor candidate across contributor retry rotation
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-06T19:09:44.116383Z'
updated_at: '2026-08-06T19:09:44.116383Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Triggered by OOMPAH-858 after its exact full gate passed and integrated: implementation retries consumed every configured provider/model candidate (Claude haiku, sonnet, opus and Codex terra), leaving the terminal auditor selector with 'All candidates are used by contributors' and forcing Needs Human despite healthy transports. Implementation scope: make contributor candidate selection and retry escalation reserve at least one healthy auditor-role provider/model that remains independent for terminal validation, or deterministically select a contributor/auditor allocation that cannot exhaust the independence set. Cover initial dispatch, stalled-agent escalation, provider rotation, continuation/recovery, configured one-candidate impossibility, and dynamic health/config changes. Preserve provider diversity, explicit owner override semantics, contributor identity evidence, and fail-closed auditing. Relevant code: oompah/auditor_candidate_selector.py, orchestrator contributor/provider selection and retry escalation, configuration validation/health observability, terminal transition recovery. Required tests: reproduce OOMPAH-858's multi-provider retry sequence; prove a reserved independent candidate remains dispatchable; prove impossible configurations surface a pre-dispatch actionable configuration alert instead of consuming all candidates and failing only after integration; prove restart and concurrent task dispatch retain reservation correctness. Acceptance: when configuration has at least two eligible independent candidates, no task can consume the final auditor candidate through contributor retries; exact integrated work reaches an independent audit without operator intervention.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

