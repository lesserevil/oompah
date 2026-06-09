---
id: TASK-402.4
title: Represent lifecycle labels as Backlog statuses
status: Done
assignee:
  - oompah
created_date: '2026-06-01 19:20'
updated_date: '2026-06-09 00:34'
labels:
  - task
dependencies:
  - TASK-402.1
parent_task_id: TASK-402
priority: high
ordinal: 16000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Convert lifecycle concepts currently encoded as labels or derived review state into Backlog.md statuses.

Context:
- Several labels are really task states: asking_question, human-only, decomposed, duplicate-candidate, ci-fix, merge-conflict, merged, archive:yes.
- Dispatch currently checks these labels in _should_dispatch and related flows.
- The new model should use Backlog status as the source of truth for task lifecycle.

Required status mapping:
- asking_question label -> Needs Answer status
- human-only label -> Needs Human status
- decomposed label + deferred status -> Decomposed status
- duplicate-candidate label -> Duplicate Candidate status
- ci-fix label -> Needs CI Fix status
- merge-conflict label -> Needs Rebase status
- closed issue with open review -> In Review status
- merged label -> Merged status
- archive:yes label -> Archived status

Work required:
- Update orchestrator transitions to write statuses instead of adding lifecycle labels.
- Update dispatch gates to check status categories instead of lifecycle labels.
- Update focus/routing logic so Needs CI Fix and Needs Rebase still select the correct agent focus.
- Update question answer flow so a human comment moves Needs Answer back to Open when appropriate.
- Update merge/webhook paths so merged work becomes Merged, not Done plus a label.
- Keep type/skill labels such as bug, feature, epic, needs:frontend, needs:backend, and needs:test as labels.

Files to inspect first:
- oompah/orchestrator.py
- oompah/server.py
- oompah/landing_gate.py
- oompah/templates/dashboard.html
- tests/test_ask_question.py
- tests/test_asking_questions.py
- tests/test_orchestrator_duplicate_detection.py
- tests/test_orchestrator_merged.py
- tests/test_scm.py
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 asking_question, human-only, decomposed, duplicate-candidate, ci-fix, merge-conflict, merged, and archive:yes are no longer required as lifecycle labels.
- [ ] #2 Dispatch decisions are based on status categories, not lifecycle labels.
- [ ] #3 CI-fix and rebase/conflict work still route to the proper specialist behavior.
- [ ] #4 Merged PR/MR or merge-queue success transitions the task to Merged.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Build a small status helper or predicates for dispatchable, waiting, review, and terminal statuses.
2. Update each lifecycle transition one at a time with focused tests.
3. Remove label-based dispatch gates after equivalent status tests pass.
4. Keep routing labels only where they describe type/capability, not lifecycle.
5. Run focused orchestrator/server tests.
<!-- SECTION:PLAN:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Completed as part of the Backlog-only tracker migration. Removed Beads/bd runtime paths where applicable, moved lifecycle behavior to canonical Backlog.md statuses, updated UI/API/tests/docs for Backlog-only behavior, and verified with make test: 3677 passed.
<!-- SECTION:FINAL_SUMMARY:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Focused lifecycle transition tests pass.
- [ ] #2 Existing type/capability labels remain supported.
<!-- DOD:END -->
