---
id: OOMPAH-876
type: task
status: Open
priority: null
title: Retry auditor transport failures without consuming substantive candidate capacity
parent: OOMPAH-768
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-07T08:51:10.232904Z'
updated_at: '2026-08-07T09:34:02.198332Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Live regression on OOMPAH-870 on 2026-08-07. Its only eligible Completion Auditor (Claude/haiku) suffered a bounded run_command result-delivery timeout and forced ACP shutdown before submitting a verdict. The scheduler consumed that candidate permanently and moved the task to Needs Human/no_auditor, even though the failure was transport/finalization infrastructure and a healthy independent verdict-capable model can retry the same immutable audit. A configured Codex/luna candidate was correctly excluded because its ACP backend cannot submit audit verdicts.

Implementation scope:
- Classify forced tool-result delivery timeout and provider shutdown before verdict as retryable transport/finalization failure, not a substantive auditor-candidate rejection.
- Preserve independent-candidate accounting: policy rejection or completed substantive audit may consume a candidate, while transient infrastructure failure may retry it or another eligible model under bounded backoff.
- Do not count verdict-incapable configured candidates as usable capacity, and report that misconfiguration separately.
- Keep exact audit id, fingerprint, revision binding, attempt history, authority fencing, and maximum retry bounds.
- Make Needs Human/no_auditor occur only after all genuinely eligible candidates or infrastructure retry budgets are exhausted.

Relevant code: auditor dispatch candidate ledger, ACP tool-result delivery timeout/forced shutdown handling, orchestrator auditor exit classification, terminal-audit retry/exhaustion metadata, and health alerts.

Required tests:
- Tool-result delivery timeout before verdict retries without consuming the sole eligible candidate as substantive exhaustion.
- Policy/substantive rejection still rotates and consumes as designed.
- Verdict-incapable ACP candidates do not mask zero eligible capacity.
- Restart preserves retry classification and bounded backoff without duplicate auditors.
- OOMPAH-870 sequence reaches a verdict after transport recovery without reopening implementation.

Acceptance criteria: a transient auditor transport/finalization failure cannot strand a valid merged task in Needs Human/no_auditor while a bounded retry remains; operator health distinguishes transport recovery from candidate exhaustion; focused auditor lifecycle/dispatch/coordinator/health tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-07 09:33
---
Additional live reproduction: OOMPAH-845's Merged audit consumed haiku, sonnet, and opus; each transport terminated before producing a structured verdict (17m, 12m, 14m), then the audit exhausted max_attempts=3 and entered Needs Human despite merged exact-head gate evidence. Owner override restored Merged. Regression coverage should include repeated pre-verdict transport termination across the whole configured pool and prove candidate capacity is not substantively consumed.
---
author: oompah
created: 2026-08-07 09:34
---
Second same-cycle reproduction: OOMPAH-867 exhausted haiku, sonnet, and opus at 16m/12m/13m with zero-turn pre-verdict transport terminations, then entered Needs Human at max_attempts=3 despite exact full-gate and independent-review evidence. Owner override restored Done. This confirms the failure family is systematic rather than task-specific.
---
<!-- COMMENTS:END -->
