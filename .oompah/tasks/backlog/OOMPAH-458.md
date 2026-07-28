---
id: OOMPAH-458
type: epic
status: Backlog
priority: 1
title: Dispatch independent auditor agents and evaluate target-specific evidence
parent: null
children:
- OOMPAH-468
- OOMPAH-469
- OOMPAH-470
- OOMPAH-471
- OOMPAH-472
- OOMPAH-473
- OOMPAH-474
- OOMPAH-475
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-28T13:03:46.047976Z'
updated_at: '2026-07-28T13:06:16.086104Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Goal

Add the reserved auditor focus and the model-selection, evidence, prompt, result-submission, retry, and scheduling machinery that performs terminal audits using a model independent from all models that contributed to the audited revision.

Required behavior

- Auditor selection prefers a different provider and requires a different model. It may use the same provider only when an explicitly different model is provable.
- Epic audits exclude every recorded contributing provider/model, respect the project provider whitelist, and fail closed when no independent candidate remains.
- Auditor agents are read-only with respect to source, Git history, reviews, and task status. They may inspect files, run tests, and submit one structured verdict through an auditor-only tool.
- Done audits verify completion and acceptance criteria; Merged audits verify correct target landing; Archived audits verify safe retirement.
- Auditors consume ordinary global concurrency, use a priority audit lane, and serialize with workers sharing the same task or epic branch.
- Transient failures rotate candidates and retry; exhausted candidates produce actionable Needs Human instructions.

Constraints

Build on the terminal-audit coordinator epic. Do not let the auditor directly set status, commit, push, merge, or create repair work. Persist safe provider/model identifiers but never credentials or full untrusted model output. All code changes require tests.

Acceptance criteria

A persisted In Validation request can be recovered after restart, dispatched to an eligible independent auditor, evaluated against a stable evidence fingerprint, and completed through the coordinator. Multi-provider, multi-model, epic, retry, and no-candidate scenarios are covered by tests and make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

