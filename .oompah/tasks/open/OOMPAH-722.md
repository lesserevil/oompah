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
updated_at: '2026-08-03T14:57:07.747533Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 7a28edd5a432e6f041d92c0b6bd5d119ba4c047ec7ed01a178487eb095cf0e10
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 986590a4-646e-4c57-a76f-095758bdf1a2
  claim_owner: 2dcc53e1-cdcd-4522-a08d-de6ce4222a8c
  claimed_at: '2026-08-03T14:56:13.642413+00:00'
  claim_expires_at: '2026-08-03T15:26:13.642413+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 87f91e64-f60b-4ca0-b8f3-bfaede93d3ab
oompah.task_costs:
  total_input_tokens: 50481
  total_output_tokens: 603
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 50481
      output_tokens: 603
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 50481
    output_tokens: 603
    cost_usd: 0.0
    recorded_at: '2026-08-03T14:57:05.476175+00:00'
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

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-03 14:56
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-03 14:56
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-03 14:57
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 50.5K in / 603 out [51.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 46s
- Log: OOMPAH-722__20260803T145628Z.jsonl
---
<!-- COMMENTS:END -->
