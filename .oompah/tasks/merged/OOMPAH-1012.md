---
id: OOMPAH-1012
type: bug
status: Merged
priority: 1
title: Validate landed epics on the current authoritative target head
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T02:41:11.512382Z'
updated_at: '2026-08-11T08:09:18.899404Z'
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
  creation_marker: o940-landed-epic-current-target-audit
  request_fingerprint: 0adef301dabca05114c817278bc48a556f4dbd8bd838cad0aafd4a246b79b5e1
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-2f6f4aaac39d
    project_id: proj-14849f1b
    task_id: OOMPAH-1012
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: ddef3478f6b42e85cd4a47b2362d49b8f8184e0a4691f0d4bfbe6438b2b64252
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Protected PR #806 and hosted Python 3.11/3.12/3.13 gates are green; deployed
      build 5e2288c47738bcf8b441d0f6f71bbc2ab878ac17 contains merge 62c3cda3ea602b614a3a3dfc92c66468b5c34a4b;
      independent audit verified that every exact reviewed branch change is patch-equivalent
      to or composition-equivalent with the protected merge and no unique branch changes
      remain.'
    created_at: '2026-08-11T08:09:14.555115+00:00'
    selected_ref: origin/OOMPAH-1012
    selected_sha: 616331ef871e875d1549842c3a33856d544bdd0d
    applied: false
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

Triggered by: OOMPAH-940

Triggered by: OOMPAH-940, OOMPAH-971, and OOMPAH-1003.

Problem: the naturally scheduled OOMPAH-940 root-epic Done audit bound selected_sha to the historical epic landing revision 2dd74be288b81265ea4a242d7467ecc1ed9f1435 even though that epic branch is already an ancestor of current main and later post-landing fixes were correctly routed to main. The detached full gate therefore ran pre-OOMPAH-971 test infrastructure and failed with the exact seven task-private-venv runner failures and cold-page fsync timeout that OOMPAH-971 already fixed. Current deployed main passes those runner regressions. A landed root epic can remain permanently Needs CI Fix because terminal validation selects a stale ancestor that cannot contain accepted post-landing repairs.

Scope: when terminalizing an already-landed root or nested epic, preserve the immutable landing revision as containment authority but choose an exact current head from the authoritative live landing target for terminal audit/quality-gate execution, only after proving the landing revision is an ancestor of that refreshed target head and all task/evidence/topology bindings remain current. Do not mutate/reuse the stale landed epic branch; preserve OOMPAH-981 post-landing routing. Fail closed for missing/ambiguous landing facts, non-ancestor or rewritten targets, stale evidence generation, unavailable target refs, or mutable head races. Carry both the original landing revision and selected validation head in durable audit/restart/idempotency evidence.

Relevant code: root/nested epic auto-close terminal transition construction, terminal-audit revision binding/workspace resolution, authoritative quality-gate selection, and landing-target repository proof.

Required tests: reproduce a landed epic branch at A, advance main with an accepted post-landing harness repair B, and prove the Done audit validates exact B while binding A as the contained landing revision; cover target advancement races, force-rewritten/non-ancestor target, missing target, restart/replay, duplicate audit delivery, standalone/non-epic behavior unchanged, and OOMPAH-971 task-private-venv full-gate portability. Acceptance: an OOMPAH-940-shaped parent naturally leaves Needs CI Fix without branch mutation or owner terminal override, validation runs on an exact current authoritative target containing the landing, and focused plus complete Makefile gates and the live rollout check pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-11 02:41
---
Claimed for direct-owner repair from the failed natural OOMPAH-940 audit. Implementation must preserve the immutable landing revision while validating an exact current authoritative target descendant, fail closed on topology/ref races, and leave stale landed epic branches untouched.
---
author: oompah
created: 2026-08-11 03:10
---
Implementation is committed and pushed at exact head 616331ef871e875d1549842c3a33856d544bdd0d. Terminal audits now preserve immutable landing_revision as containment authority while resolving selected_ref/selected_sha to the current authoritative root-main or nested-parent target under repository/project fencing, require ancestry before staging, bind both identities through durable workflow/restart/finalization paths, and preserve historical v1 serialization/hash behavior when landing_revision is absent. Focused validation passed 1,439 tests across quality gates, identity/dispatch/coordinator/store, durable enforcement/finalization/lifecycle, plus terminal mutation scan 21/21. Independent exact-head review is active; the one repository-wide gate remains reserved for the final combined head.
---
author: oompah
created: 2026-08-11 03:14
---
Independent exact-head review ACCEPTED 616331ef871e875d1549842c3a33856d544bdd0d with no authority/security findings. The reviewer verified separate immutable landing witness/current validation SHA, root/nested resolution under the project fence, fail-closed ancestry refresh, propagation through record/attempt/workflow generation/idempotency/restart/checkpoint/dispatch/quality-gate identity, unchanged serialization/hash for old rows, and unchanged ordinary/non-epic routing. Six exact authority/ABA/restart tests also passed. The commit is composed into recovery head ca8382818, where all 1,707 changed-path tests pass.
---
<!-- COMMENTS:END -->
