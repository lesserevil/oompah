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
updated_at: '2026-07-30T21:27:41.061088Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
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
<!-- COMMENTS:END -->
