---
id: OOMPAH-671
type: task
status: Needs Human
priority: null
title: Recover terminal audits when historical work branches were deleted
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T23:31:12.705782Z'
updated_at: '2026-07-31T23:31:27.639287Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Fix terminal-audit dispatch for terminal or auto-archive audits whose persisted work_branch references a branch that was deleted after merge. Live reproduction: EXOCOMP-75/76/77/88/89/90/91/92/99/100/101/102/103/104/105 were canonically Merged and queued for aged-Merged auto-archive; each auditor attempt failed during git worktree add with 'invalid reference: origin/epic-EXOCOMP-2', then exhausted attempts and was incorrectly surfaced as no_independent_candidate in Needs Human. Implementation scope: trace terminal-audit workspace selection and checkout creation in oompah/orchestrator.py and oompah/projects.py; select a safe, immutable audited revision or verified default-branch fallback when the historical work branch no longer exists; fail closed when the audited evidence is ambiguous or unreachable; classify checkout/source-reference failures separately from auditor-provider availability; and provide an idempotent retry/rearm path that does not reopen terminal tasks for implementation dispatch. Required tests: deleted merged epic branch with evidence reachable from default branch; unreachable/ambiguous evidence fails closed; aged-Merged Archived audit; correct error classification; retry idempotency across restart; project isolation; no normal implementation dispatch. Acceptance: affected audits can be retried against the intended evidence, no false no-independent_candidate alert is emitted for a deleted historical branch, Exocomp tasks remain out of implementation flow, and alert state retires after successful audit or explicit durable terminal disposition. Run focused terminal-audit tests and the full Makefile gate.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-31 23:31
---
Claimed for direct operator implementation at the project owner's request. Needs Human will be used only as a scheduler-control hold while I implement and verify the fix; do not dispatch a worker for this task.
---
author: oompah
created: 2026-07-31 23:31
---
Moved to Needs Human from the dashboard/API. Human action required: inspect OOMPAH-671 (Recover terminal audits when historical work branches were deleted), add the specific decision, missing information, or manual fix needed, then move the task back to Open when it is ready for agents again.
---
<!-- COMMENTS:END -->
