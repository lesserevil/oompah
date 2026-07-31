---
id: OOMPAH-663
type: task
status: Backlog
priority: null
title: Canonicalize integrated-task fingerprints for owner overrides
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T13:52:05.961085Z'
updated_at: '2026-07-31T13:52:05.961085Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Bug reproduction: OOMPAH-660 was integrated at 793bcc7969d39634dab560ed0a10b9dcad7a9716, but its integration-staged Done audit fingerprinted the epic branch and a git-branch contributor while the API owner-override path recomputed evidence from the normalized task issue. The legitimate project-owner override therefore failed with HTTP 409 until a duplicate Done request was restaged with the API fingerprint. Implementation scope: define one canonical evidence snapshot/fingerprint path for integrated-task terminal audit creation, API and ACP owner overrides, and restart recovery. Preserve auditor-independence provenance separately if it must not be part of the canonical task evidence. Relevant files include oompah/orchestrator.py, oompah/server.py, oompah/acp_tools.py, oompah/terminal_audit.py, and terminal-transition tests. Add regression coverage that stages an integrated task audit, routes it to Needs Human for no independent candidate, and applies an authorized owner override without restaging; also verify a genuinely changed integration SHA still fails closed. Acceptance criteria: the first valid override succeeds and retires the audit alert, no duplicate terminal request is needed, stale evidence remains rejected, and focused plus full Makefile gates pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

