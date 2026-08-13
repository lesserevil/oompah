---
id: OOMPAH-1247
type: task
status: Open
priority: null
title: Capture standalone submission base identity before review adoption
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T15:23:30.972748Z'
updated_at: '2026-08-13T15:37:04.412053Z'
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
  creation_marker: 044a45d0-2dc4-49fb-bbcf-383ced769abe
  request_fingerprint: efb813c451d9d465b70814c784f63f4a5b4b3cbea5a64143614946ff8ad68acd
oompah.lifecycle_revision: 1
---
## Summary

Bug: a standalone Ready-to-Integrate submission can persist integration v2 with head_sha but no base_sha (observed TRICKLE-122 at head 00d343bf, accepted 2026-08-13T15:16:50Z). GitLab MR !9 has complete exact diff_refs, but _standalone_review_matches_submission rejects it with the misleading message that the open review lacks exact head or base identity because expected_base is empty. Scope: trace validation submission/submit persistence and guarantee the accepted target branch base SHA is recorded for standalone submissions; fail closed before Ready if it cannot be captured; distinguish missing accepted-submission base evidence from missing forge MR evidence in diagnostics. Add regression tests covering submit-created records and exact GitLab MR adoption. Acceptance: a freshly submitted standalone task persists full head/base generation identity, MR !9-shaped evidence is accepted, legacy/incomplete records receive a bounded recovery path or precise actionable diagnosis, and focused workflow/integration tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-13 15:37
---
Implemented on PR #869. Root cause: top-level standalone submit omitted the project default target, so exact Git verification could not capture base_sha and later blamed a healthy GitLab MR. Added default-target capture, precise diagnostics, and regression coverage. Focused suite: 550 passed; hosted CI in progress.
---
<!-- COMMENTS:END -->
