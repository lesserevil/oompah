---
id: OOMPAH-825
type: task
status: Ready to Integrate
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
updated_at: '2026-08-05T12:30:55.059213Z'
work_branch: OOMPAH-825
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/721
review_number: '721'
review_head: 74c4b71cfab349bc782fff71188c97651f54f519
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-825
  head_sha: 74c4b71cfab349bc782fff71188c97651f54f519
  submitted_at: '2026-08-05T12:19:21.829561+00:00'
  updated_at: '2026-08-05T12:19:21.829561+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/721
oompah.review_number: '721'
oompah.work_branch: OOMPAH-825
oompah.target_branch: main
oompah.review_head: 74c4b71cfab349bc782fff71188c97651f54f519
---
## Summary

Live post-OOMPAH-823 state has 46 bounded/exhausted terminal lifecycle rows and action_required=true, but the warning is mostly false classification. Root cause: OompahMarkdownTracker normalization yields Issue(project_id=None), and reconcile_lifecycle_batch neither attaches the source project_id nor installs the current all-issues snapshot as recovery context before _validate_terminal_transition/_resolve_parent_epic. OOMPAH-739 added snapshot recovery only around recover_pending_audits, not the later background batch. Persisted conflict recovery is also stale/narrow: Archived tasks OOMPAH-452/453/455/456 have current PASS/Archived evidence but conflict resume requires PASS/Done; parent/target-relative landing evidence is absent from failure_fingerprint; and structurally Done-only OOMPAH-660/662 have matching applied project-owner Done overrides that recovery ignores. Scope: project-scope every batch Issue and supply a complete project snapshot; revalidate persisted conflicts against current terminal/audit facts; treat current PASS/Archived as superseding stale Merged repair; incorporate parent and target-relative durable LandingFact plus a classifier version into retry fingerprints; accept a matching applied authorized Done override for structurally Done-only maintenance; migrate/rearm v1 exhausted rows exactly once; preserve fail-closed intent checkpoints, row isolation, cross-project isolation, restart idempotence, and bounded persistence. Live migration groups: 4 stale Archived no-ops (452/453/455/456); 31 valid Merged rows with terminal parent evidence; 9 target-relative/patch-equivalent landed rows including OOMPAH-589/590/597/601/602/603/766 and EXOCOMP-129/185; 2 owner-override repairs (660/662 Merged to Done). Required tests: native Issue(project_id=None) parity; OOMPAH-739 background-batch snapshot parity with deleted refs; stale conflict plus PASS/Archived; one-time fingerprint reopen on changed landing evidence but not outage/restart; nested target-relative PRs and rebased parent PR chains; matching owner Done override one-write repair while missing evidence remains exhausted; live-shaped 46-row v1 migration yielding 44 not_needed plus 2 reconciled; cross-project isolation; restart idempotence and bounded writes. Acceptance: deploy on main without hand-editing service_state or task files; only OOMPAH-660/662 require tracker status writes; the ledger converges to exhausted=0 and action_required=false; no valid terminal state is weakened or auto-trusted without authoritative current evidence.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-05 09:53
---
Implemented the authoritative lifecycle-ledger recovery at clean pushed exact head b741e5372. It scopes alias-complete project snapshots, parses strict landing facts, distinguishes forge outage from negative evidence, rejects stale/retired authority, performs fresh under-lock tri-state validation before durable intent/status repair, and makes the one-time v1 migration restart/race safe. Live-shaped 46-row migration coverage proves 44 not-needed + 2 owner-authorized Done repairs; provider, parent-landing, child-state, and persistence races fail closed. Verification: 390 focused tests pass (terminal enforcement 78, SCM 304, compatibility 8); terminal mutation scan 8/8; secret/diff checks pass; independent exact-head review PASS; canonical trailer and remote synchronization verified. Holding submission only to serialize against OOMPAH-816's active canonical gate.
---
author: oompah
created: 2026-08-05 12:13
---
Rebased the reviewed lifecycle recovery implementation onto deployed OOMPAH-824 main c14ca03f59078e6df06871488cf78f04477acb11. New exact clean pushed head 74c4b71cfab349bc782fff71188c97651f54f519 has that exact parent, one canonical commit, and the same five-path delta. Rebase had zero conflicts/manual adaptations. Validation lease construction and top-level/health validation_resources projections coexist with lifecycle landing evidence, tri-state SCM observation, locked finality revalidation, and v1 migration; no workflow-shadow/job fields leaked. Nine-file combined lifecycle/SCM/validation/orchestrator suite: 983 passed. Terminal scan 8/8, secret scan, diff checks, trailer, upstream cleanliness all pass. Independent exact-head review is in progress before submission.
---
author: oompah
created: 2026-08-05 12:19
---
Independent exact-head review PASS at 74c4b71cfab349bc782fff71188c97651f54f519: one exact parent c14ca03f5, clean/pushed; patch-identical rebase; validation arbitration preserved; project-scoped fingerprints and tri-state SCM fail closed; exhausted rows rearm only on authoritative evidence changes; v1 migration marker is outage/restart durable; fresh complete snapshot is revalidated under the project write lock; live-shaped 46-row migration converges 44 no-op + exactly 2 authorized Done repairs; no workflow-shadow leakage; tests and trailer valid.
---
author: oompah
created: 2026-08-05 12:19
---
Authoritative lifecycle-ledger recovery rebased onto deployed validation arbitration at exact reviewed head 74c4b71cfab349bc782fff71188c97651f54f519. 983 focused tests and required scans pass; independent review PASS.
---
author: oompah
created: 2026-08-05 12:30
---
Branch quality gate passed for `74c4b71cfab349bc782fff71188c97651f54f519` using `make test` in 630.6s. Review creation may proceed.
---
<!-- COMMENTS:END -->
