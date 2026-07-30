---
id: OOMPAH-622
type: task
status: Open
priority: null
title: Reject verdict-incapable Codex CLI auditor sessions
parent: OOMPAH-585
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T21:26:15.242500Z'
updated_at: '2026-07-30T21:28:05.734545Z'
work_branch: epic-OOMPAH-585--task-OOMPAH-622
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 358500985d6afae0d9aaba6843d1b29f02c968a20ef02191175e51dc8c18d628
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: fe2a434b-9130-4515-a5cb-ff56a95389ef
  claim_owner: c1f4a4cb-217d-4c2a-aad6-f768a3cdbb4b
  claimed_at: '2026-07-30T21:27:58.434340+00:00'
  claim_expires_at: '2026-07-30T21:57:58.434340+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 14998750-cea7-4ee8-8c45-87ff796c2c29
oompah.work_branch: epic-OOMPAH-585--task-OOMPAH-622
oompah.integration:
  version: 1
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-585--task-OOMPAH-622
  base_branch: epic-OOMPAH-585
  base_sha: 58915e5f0b116cf4269f6bb882dd81aa4010ec03
  updated_at: '2026-07-30T21:28:03.768318+00:00'
---
## Summary

Implementation scope: eliminate the terminal-audit dispatch race in which a subscription-backed Codex native CLI session can be selected as a completion auditor even though that transport cannot expose submit_audit_result, leaving a reviewed task permanently In Validation and triggering repeated auditor attempts. Filter only ACP Codex providers using subscription billing from terminal-auditor candidates until that transport has a real verdict channel; preserve Codex API/token-backed auditors and all capable Claude/OpenCode candidates. Independently force every completion-auditor ACP session into read-only mode, including native Codex sandbox/network/additional-directory options, while leaving implementation sessions unchanged. Return an actionable no-capable-candidate diagnostic instead of silently cycling when every configured auditor lacks verdict transport. Relevant files: oompah/auditor_candidate_selector.py, oompah/orchestrator.py, oompah/acp_backends/codex.py as needed, and focused auditor/ACP tests. Tests: reproduce mixed-candidate selection, subscription-only exhaustion, token-backed Codex eligibility, auditor read-only propagation, native CLI sandbox/network behavior, and unchanged implementation dispatch. Acceptance criteria: no verdict-incapable provider is launched as an auditor; all auditor sessions are read-only; capable candidates continue to submit terminal verdicts; focused tests and the combined-tree gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 21:26
---
Claimed directly by the operator Codex session because the bug itself prevents subscription-backed Codex auditors from completing terminal validation. I will implement, test, push, submit, and prune the temporary worktree.
---
author: oompah
created: 2026-07-30 21:28
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-30 21:28
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
