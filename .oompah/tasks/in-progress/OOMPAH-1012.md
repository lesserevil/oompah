---
id: OOMPAH-1012
type: bug
status: In Progress
priority: 1
title: Validate landed epics on the current authoritative target head
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T02:41:11.512382Z'
updated_at: '2026-08-11T02:42:22.582766Z'
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
<!-- COMMENTS:END -->
