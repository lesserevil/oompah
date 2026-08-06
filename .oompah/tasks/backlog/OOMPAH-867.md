---
id: OOMPAH-867
type: task
status: Backlog
priority: null
title: Use canonical epic branches for terminal-audit workspace resolution
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-06T22:21:55.244164Z'
updated_at: '2026-08-06T22:21:55.244164Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Live release-blocking regression reproduced on OOMPAH-768 at 2026-08-06 22:15 UTC: terminal-audit evidence fingerprinting resolves the canonical standalone epic branch epic-OOMPAH-768, but Orchestrator._create_workspace_for_auditor independently builds candidates from source_branch/work_branch/integration.task_branch/branch_name and tries only origin/OOMPAH-768. The published origin/epic-OOMPAH-768 revision is therefore reported as having no safely resolvable revision; two infrastructure attempts exhaust and move the completed parent epic to Needs Human, hard-start blocking OOMPAH-809 and OOMPAH-811. OOMPAH-746 added canonical epic branch resolution to fingerprinting but did not unify detached audit workspace selection. Implementation scope: define one typed, ordered terminal-audit revision candidate resolver consumed by both evidence fingerprinting and detached workspace creation; include immutable SHA precedence, explicit work/source/integration branches, canonical standalone epic branch, nested shared parent branch then private epic fallback, and only the already-authorized merged/archive default fallback. Persist/compare the exact selected revision and SHA so fingerprint and workspace cannot diverge across tracker refresh or restart. Never substitute a branch tip when immutable evidence was recorded. Relevant files: oompah/terminal_audit.py, oompah/orchestrator.py _create_workspace_for_auditor, project branch helpers, tests/test_terminal_audit.py, tests/test_parallel_epic_children.py, and restart audit tests. Required tests: exact OOMPAH-768 standalone epic with no work_branch resolves origin/epic-OOMPAH-768; nested epic shared/private ordering; absent/unavailable candidates fail closed; immutable missing SHA never falls back; fingerprint/workspace parity; restart/retry uses the same exact candidate; ordinary tasks unchanged. Acceptance: completed standalone/nested epics with published canonical branches can enter terminal audit without Needs Human infrastructure exhaustion, and every workspace revision is the same authority represented by the evidence fingerprint.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

