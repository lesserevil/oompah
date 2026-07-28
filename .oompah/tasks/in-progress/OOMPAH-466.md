---
id: OOMPAH-466
type: feature
status: In Progress
priority: 1
title: Apply audit verdicts and route failures without fail-open behavior
parent: OOMPAH-457
children: []
blocked_by:
- OOMPAH-465
labels: []
assignee: null
created_at: '2026-07-28T13:05:08.204164Z'
updated_at: '2026-07-28T19:55:16.250628Z'
work_branch: epic-OOMPAH-457
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 310715ad-27ac-4a75-a8f1-dba49637df2a
oompah.work_branch: epic-OOMPAH-457
oompah.task_costs:
  total_input_tokens: 390282
  total_output_tokens: 5073
  total_cost_usd: 0.0
  by_model:
    sonnet:
      input_tokens: 390282
      output_tokens: 5073
      cost_usd: 0.0
  runs:
  - profile: standard
    model: sonnet
    input_tokens: 390282
    output_tokens: 5073
    cost_usd: 0.0
    recorded_at: '2026-07-28T19:52:43.775139+00:00'
---
## Summary

Implementation scope

Add coordinator result handling with compare-and-set checks for audit ID, target, fingerprint, and current In Validation state. PASS records safe evidence, posts a result comment, and applies only the audited target before advancing the next chain item. Map FAIL classifications centrally: incomplete/missing tests/unpushed/missing evidence to Open; CI failure to Needs CI Fix; conflict/out-of-date to Needs Rebase; healthy unmerged review to In Review; ambiguous requirements/external capability/no auditor to Needs Human; unsafe archive restores the recorded pre-audit state unless another class is more specific. NEEDS_HUMAN comments must end with explicit instructions or questions. Never honor an error, timeout, unparseable verdict, or retry ceiling as a pass.

Tests

Table-test every verdict/classification/status, stale result rejection, duplicate result idempotency, chained pass behavior, failed comment/status writes, unsafe archive restoration, actionable Needs Human endings, and absence of all fail-open paths. Run focused tests and make test.

Acceptance criteria

Only a matching PASS reaches the requested terminal state; every failure has a deterministic repair state and durable actionable explanation; malformed or infrastructure results leave the item nonterminal.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 19:49
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-28 19:50
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-07-28 19:52
---
Agent completed successfully in 168s (395355 tokens)
---
author: oompah
created: 2026-07-28 19:52
---
Run #1 [attempt=1, profile=standard, role=standard -> Codex/gpt-5.6-terra]
- Turns: 1, Tool calls: 29
- Tokens: 390.3K in / 5.1K out [395.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 48s
- Log: OOMPAH-466__20260728T195001Z.jsonl
---
author: oompah
created: 2026-07-28 19:52
---
Agent completed without closing this issue (168s (395355 tokens)). Escalating from 'standard' to 'deep'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-28 19:53
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-28 19:53
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-07-28 19:55
---
Understanding: This task implements coordinator result-handling per OOMPAH-457's terminal-transition-coordinator design. The staging half (OOMPAH-465) landed; the verdict-application half is missing. Plan: (1) add an AuditResult submission surface with an idempotency attempt_id; (2) add TerminalTransitionCoordinator.apply_audit_result that CAS-checks audit_id/target/fingerprint and requires In Validation before applying; (3) on PASS record safe evidence, post a result comment, and apply only the audited target while advancing the next chain item; (4) map FAIL classifications centrally to Open, Needs CI Fix, Needs Rebase, In Review, Needs Human, or the recorded pre-audit state per the spec; (5) NEEDS_HUMAN comments run through validate_needs_human_comment so they end with instructions/questions; (6) never map error/timeout/unparseable/malformed/retry-ceiling to PASS. Note: the dispatcher labelled this run 'CI Failure Fixer' but there is no failing PR/CI on this branch — the actual work is the feature. I will implement it directly rather than hand off again since the prior agent also did not close and CI has no failures to fix.
---
<!-- COMMENTS:END -->
