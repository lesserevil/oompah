---
id: OOMPAH-722
type: task
status: Open
priority: null
title: Treat read-only git rev-list audit inspection as recoverable
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-03T14:55:24.661073Z'
updated_at: '2026-08-03T14:55:36.851270Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Triggered by: EXOCOMP-241 terminal audit audit-5d7ea8997801, attempt attempt-767b1eb65fd7 on 2026-08-03.

Production evidence: the Opus completion auditor independently verified HEAD, origin/main, and origin/epic-EXOCOMP-132 all equal 4e01311060eee5be3c1d18d86d809f4007664497 using allowed git rev-parse and git log commands. It then requested the demonstrably read-only inspections `git rev-list --left-right --count origin/main...origin/epic-EXOCOMP-132`, `git rev-list --count origin/main..origin/epic-EXOCOMP-132`, and the reverse count. The deployed authority policy returned the generic fatal denial instead of the stable recoverable validation marker, consumed the policy-denial budget, terminated an otherwise healthy auditor, rotated the candidate, and raised terminal_audit_health:policy_incompatibility. OOMPAH-713 and OOMPAH-716 cover harmless compound syntax, awk/sed, and git merge-base, but not git rev-list.

Implementation scope:
- Treat worktree-scoped git rev-list inspection as read-only. At minimum, support or recoverably reject --left-right --count and --count with ordinary revision/range operands.
- Prefer a structured git-subcommand capability table so future read-only git inspection commands do not require one-off fatal-denial fixes.
- Unsupported but non-mutating rev-list syntax must return the existing recoverable auditor_read_only_shell_syntax validation response with safe alternatives and must not consume the fatal denial budget.
- Keep state-changing git commands, shell escapes, output redirection, credential/path escape, and command composition fail-closed.
- Clear policy-incompatibility health after a healthy retry/override and preserve exact candidate/running counters.

Required tests:
- Replay all three exact EXOCOMP-241 rev-list forms and prove none invokes the fatal denial callback or rotates the candidate.
- Prove the auditor can verify zero divergence and submit an accepted verdict after each allowed/recoverable response.
- Cover malformed ranges, shell metacharacters, redirects, git push/merge/reset/commit, path escape, provider rotation, and alert clearing.
- Run focused authority-boundary, auditor-contract, ACP backend, provider-retirement, terminal-audit health, and dashboard suites plus make test.

Acceptance criteria:
- An EXOCOMP-241-style completion audit reaches submit_audit_result without candidate rotation caused by read-only git rev-list.
- No write-capable command is admitted.
- Policy incompatibility is reported only while unresolved and clears after successful recovery.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

