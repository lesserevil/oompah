---
id: OOMPAH-663
type: task
status: Open
priority: null
title: Canonicalize integrated-task fingerprints for owner overrides
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T13:52:05.961085Z'
updated_at: '2026-07-31T14:00:32.630459Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 9c360850b6c5b27e660228b90dfb195a9e618c097840d9bc4e5d7613b84d84cf
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 4fae4798-f5b7-4d7c-a99d-71784f2ae4d8
  claim_owner: 660099b4-9353-48a0-9b6d-9b3e8f3b8896
  claimed_at: '2026-07-31T14:00:24.505696+00:00'
  claim_expires_at: '2026-07-31T14:30:24.505696+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: cd436e5a-c0f6-4cc3-8afc-7b0258555ee2
---
## Summary

Bug reproduction: OOMPAH-660 was integrated at 793bcc7969d39634dab560ed0a10b9dcad7a9716, but its integration-staged Done audit fingerprinted the epic branch and a git-branch contributor while the API owner-override path recomputed evidence from the normalized task issue. The legitimate project-owner override therefore failed with HTTP 409 until a duplicate Done request was restaged with the API fingerprint. Implementation scope: define one canonical evidence snapshot/fingerprint path for integrated-task terminal audit creation, API and ACP owner overrides, and restart recovery. Preserve auditor-independence provenance separately if it must not be part of the canonical task evidence. Relevant files include oompah/orchestrator.py, oompah/server.py, oompah/acp_tools.py, oompah/terminal_audit.py, and terminal-transition tests. Add regression coverage that stages an integrated task audit, routes it to Needs Human for no independent candidate, and applies an authorized owner override without restaging; also verify a genuinely changed integration SHA still fails closed. Acceptance criteria: the first valid override succeeds and retires the audit alert, no duplicate terminal request is needed, stale evidence remains rejected, and focused plus full Makefile gates pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-31 14:00
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-31 14:00
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
