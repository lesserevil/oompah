---
id: OOMPAH-825
type: task
status: Open
priority: null
title: Scope and reclassify exhausted lifecycle reconciliation rows from authoritative
  landing evidence
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-05T08:24:12.278010Z'
updated_at: '2026-08-05T08:24:16.282762Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Live post-OOMPAH-823 state has 46 bounded/exhausted terminal lifecycle rows and action_required=true, but the warning is mostly false classification. Root cause: OompahMarkdownTracker normalization yields Issue(project_id=None), and reconcile_lifecycle_batch neither attaches the source project_id nor installs the current all-issues snapshot as recovery context before _validate_terminal_transition/_resolve_parent_epic. OOMPAH-739 added snapshot recovery only around recover_pending_audits, not the later background batch. Persisted conflict recovery is also stale/narrow: Archived tasks OOMPAH-452/453/455/456 have current PASS/Archived evidence but conflict resume requires PASS/Done; parent/target-relative landing evidence is absent from failure_fingerprint; and structurally Done-only OOMPAH-660/662 have matching applied project-owner Done overrides that recovery ignores. Scope: project-scope every batch Issue and supply a complete project snapshot; revalidate persisted conflicts against current terminal/audit facts; treat current PASS/Archived as superseding stale Merged repair; incorporate parent and target-relative durable LandingFact plus a classifier version into retry fingerprints; accept a matching applied authorized Done override for structurally Done-only maintenance; migrate/rearm v1 exhausted rows exactly once; preserve fail-closed intent checkpoints, row isolation, cross-project isolation, restart idempotence, and bounded persistence. Live migration groups: 4 stale Archived no-ops (452/453/455/456); 31 valid Merged rows with terminal parent evidence; 9 target-relative/patch-equivalent landed rows including OOMPAH-589/590/597/601/602/603/766 and EXOCOMP-129/185; 2 owner-override repairs (660/662 Merged to Done). Required tests: native Issue(project_id=None) parity; OOMPAH-739 background-batch snapshot parity with deleted refs; stale conflict plus PASS/Archived; one-time fingerprint reopen on changed landing evidence but not outage/restart; nested target-relative PRs and rebased parent PR chains; matching owner Done override one-write repair while missing evidence remains exhausted; live-shaped 46-row v1 migration yielding 44 not_needed plus 2 reconciled; cross-project isolation; restart idempotence and bounded writes. Acceptance: deploy on main without hand-editing service_state or task files; only OOMPAH-660/662 require tracker status writes; the ledger converges to exhausted=0 and action_required=false; no valid terminal state is weakened or auto-trusted without authoritative current evidence.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

