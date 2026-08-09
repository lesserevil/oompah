---
id: OOMPAH-967
type: bug
status: Ready to Integrate
priority: 1
title: Honor retained terminal provenance in canonical workflow decisions
parent: OOMPAH-940
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T18:04:59.855533Z'
updated_at: '2026-08-09T18:43:59.178057Z'
work_branch: OOMPAH-967
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: queue
  task_branch: OOMPAH-967
  base_branch: epic-OOMPAH-940
  base_sha: 2dd74be288b81265ea4a242d7467ecc1ed9f1435
  head_sha: 79192eea194239c24024728de71921256e6553cf
  submitted_at: '2026-08-09T18:38:10.411728+00:00'
  updated_at: '2026-08-09T18:38:10.411728+00:00'
oompah.work_branch: OOMPAH-967
---
## Summary

Triggered by the live OOMPAH-940 rollout at workflow snapshot generation 728: 68 exact-current workflow-managed integration_landing_refresh jobs for legacy Done tasks exhausted because exact landing evidence is unavailable. OOMPAH-871 already provides an authenticated project-owner terminal-provenance retain action for completed records that are intentionally historical, but the universal workflow fact/decision path ignores that durable authority and continues scheduling landing refreshes. Implementation scope: project the current validated provenance-suppression marker into canonical workflow facts; bind it to the exact project/task, schema, owner identity, and authority generation; make a Done task with a healthy retained marker terminal as provenance-only with no delivery effect or status mutation; make malformed/unreadable markers fail closed with a named operator action; ensure an owner-authorized new revision/generation restores ordinary workflow evaluation; and let the existing exact-publication retirement path supersede and retire prior exhausted landing-refresh authority. Do not add SQLite edits, generic mass overrides, or trust unvalidated tracker prose. Relevant files include oompah/orchestrator.py, oompah/workflow_facts.py or the terminal-audit fact adapter, oompah/work_decision.py, workflow runtime/liveness integration, and focused tests. Required tests: retained Done task produces a project/task/generation-bound terminal zero-job decision; incomplete, cross-task, malformed, or unreadable markers do not become delivery proof; new-revision authority resumes normal landing evaluation; an exact exhausted integration_landing_refresh row is retired after publication of the retained zero-job decision; restart preserves the result; unaffected Done tasks still require exact landing evidence. Acceptance: after deployment, apply the supported owner retain action only to the 68 currently exhausted legacy Done records, observe their exact old jobs retire without rerun, reach complete workflow liveness with current divergence=0 and current exhausted=0, pass make workflow-rollout-check, and close OOMPAH-940 without direct database edits or broad status overrides.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 18:05
---
Accepted for direct-owner implementation as the final live OOMPAH-940 rollout blocker.
---
author: oompah
created: 2026-08-09 18:14
---
Root cause and bounded recovery confirmed. The universal workflow fact source ignored OOMPAH-871's authenticated terminal-provenance marker, so historical Done records continued to schedule exact landing refreshes until exhaustion. Current implementation projects a project/task/generation/actor-bound marker into terminal-audit facts; retained Done records produce a terminal zero-job decision, malformed or status-conflicting markers fail closed to a named operator action, and a healthy new-revision marker resumes ordinary evaluation. The existing exact-publication retirement path is exercised end to end, including restart persistence. Live manifest: 6/68 already retained, 57/68 have durable applied owner overrides, OOMPAH-755 has exact ancestry, and OOMPAH-505/523/526/804 require the explicit owner decision that they are historical rather than a false landing claim. Validation: 474 focused provenance/decision/fact/integration/runtime/job tests pass; independent reviews are in progress.
---
author: oompah
created: 2026-08-09 18:26
---
Corrective head 9dc053c7d is pushed. Terminal provenance and audit facts now share one metadata-store instance, preserving exact missing/error semantics while retained authority still short-circuits unrelated audit handling. Verification: 479 focused workflow tests pass (including all terminal-audit shadow regressions), critical Ruff checks pass, and git diff checks pass. Final independent re-review is in progress before submission.
---
author: oompah
created: 2026-08-09 18:27
---
Honor authenticated retained terminal provenance in canonical workflow decisions, fail closed on invalid authority, and fence zero-job publication against authority changes. Head 9dc053c7d is pushed; 479 focused tests and independent review are green.
---
author: oompah
created: 2026-08-09 18:32
---
Submission head superseded by pushed corrective head 6ee361231 after adversarial review. Every present provenance fact now requires boolean retained/malformed flags, non-boolean integer schema versions, and complete project/task/actor/generation/timestamp identity before it can retain or resume delivery. Verification: 487 focused tests pass; independent 92-test re-review reports no blockers; Ruff and diff checks pass. Do not integrate prior head 9dc053c7d.
---
author: oompah
created: 2026-08-09 18:32
---
Corrected exact head 6ee361231 fully validates all retained and non-retained provenance facts fail closed, honors valid retained authority, and fences zero-job publication. 487 focused tests and independent review are green.
---
author: oompah
created: 2026-08-09 18:38
---
Exact submission head superseded again by pushed 79192eea1: persisted provenance marker, terminal-audit envelope, and quarantine versions now require non-boolean integers, preventing True/1.0 from being normalized into trusted version 1 before the decision boundary. Verification: 518 focused tests pass; independent 153-test review reports no blockers; critical Ruff/diff checks pass. Do not integrate prior heads.
---
author: oompah
created: 2026-08-09 18:38
---
Final exact head 79192eea1 honors retained provenance, validates stored and projected authority fail closed, and fences publication races. 518 focused tests plus independent review are green.
---
author: oompah
created: 2026-08-09 18:43
---
Final corrective head e0927912d is pushed: the canonical decision boundary now distinguishes an absent provenance key from explicit null/string/list/bool fact values, which fail closed as terminal.provenance_invalid with zero jobs. Persisted and projected validation is now end-to-end. Verification: 531 focused tests pass; independent 166-test adversarial review reports no blockers; critical Ruff/diff checks pass. Supersedes all prior submitted heads.
---
<!-- COMMENTS:END -->
