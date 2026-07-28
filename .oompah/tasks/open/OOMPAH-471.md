---
id: OOMPAH-471
type: feature
status: Open
priority: 1
title: Collect stable evidence for Done completion audits
parent: OOMPAH-458
children: []
blocked_by:
- OOMPAH-462
- OOMPAH-468
- OOMPAH-457
labels: []
assignee: null
created_at: '2026-07-28T13:06:12.016068Z'
updated_at: '2026-07-28T22:21:10.766320Z'
work_branch: epic-OOMPAH-458
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: bbf8d5e5edc4870aa540fcedc17ec12f41dd5cf9ba613de0e62272d322e74cdb
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: a03f2a8e-7b0e-4b46-a46a-321da5fe1de9
  claim_owner: 8e692a0c-71f6-4607-8341-3faedd0fb344
  claimed_at: '2026-07-28T22:18:46.852021+00:00'
  claim_expires_at: '2026-07-28T22:48:46.852021+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 20696b8e-d5b7-4d43-9f9a-6c12e5aea086
oompah.work_branch: epic-OOMPAH-458
---
## Summary

Implementation scope

Build a read-only DoneEvidenceCollector. Resolve the correct workspace/worktree, intended work or epic branch, source SHA, base/target branch, requirements text and digest, diff/stat with bounded excerpts, changed files, commit/push status, configured test commands, latest relevant CI/test evidence, comments/handoffs, children, and contributor identities. For tasks, require committed and pushed work on the intended branch plus coverage of the description and acceptance criteria. For epics, include every direct/nested child audit result and prove required child commits are contained in the epic revision. Return typed unavailable/invalid evidence rather than guessing.

Tests

Use Git fixtures for standalone tasks, shared epic children, nested epics, clean and dirty worktrees, unpushed commits, missing branches, changed requirements, test evidence, incomplete children, and bounded/redacted prompt payloads. Run focused tests and make test.

Acceptance criteria

The auditor receives a deterministic stable snapshot sufficient to judge completion; missing or unstable evidence is explicit and cannot be mistaken for a passing case.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 22:18
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-28 22:18
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 22:19
---
**Understanding:** I am conducting a duplicate investigation for OOMPAH-471 (Collect stable evidence for Done completion audits). The task calls for building a read-only DoneEvidenceCollector that gathers evidence for task/epic completion audits including: workspace/worktree info, source SHA, branch info, requirements/digest, diff/stat excerpts, changed files, commit/push status, test commands, CI/test evidence, comments/handoffs, children, and contributor identities. Will search the task graph, plans, and source for existing similar implementations or duplicates.
---
author: oompah
created: 2026-07-28 22:21
---
**Discovery:** Comprehensive duplicate screening complete. OOMPAH-471 is NOT a duplicate.\n\nSearch scope:\n- All .oompah/tasks directories (archived, merged, open, backlog): 281+ task files searched\n- Source code (oompah/, tests/): searched for DoneEvidenceCollector, Collector, evidence collection patterns\n- Plans and docs: terminal-transition-coordinator.md, terminal-transition-coordinator-api.md, WORKFLOW.md, README.md\n- Git history: no prior implementations\n\nFindings:\n- OOMPAH-462 (Merged): Defines terminal-audit records/enums/fingerprints — different scope (audit types, not evidence collection)\n- OOMPAH-463-467 (Merged): Terminal-audit coordinator and enforcement — infrastructure for queueing/applying audits\n- OOMPAH-468 (Done): Persist worker/epic contributor provenance — supplies contributor identities, not evidence collection\n- OOMPAH-469 (Open): Reserved auditor focus/prompt contract — supplies auditor interface, not evidence collection\n- OOMPAH-470 (Open): Auditor role selection and candidate filtering — independent candidate selection, not evidence collection\n- No existing DoneEvidenceCollector, EvidenceCollector, or similar collector classes in codebase\n\nScope confirmation: OOMPAH-471 uniquely builds a read-only DoneEvidenceCollector that gathers task/epic completion evidence (workspace, branch, SHAs, requirements, diff/stat, changed files, commit/push status, test commands, CI evidence, comments, children, contributors). This is required by auditors but not yet implemented.\n\nConclusion: OOMPAH-471 is a unique, original feature task. No duplicate found.
---
<!-- COMMENTS:END -->
