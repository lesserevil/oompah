---
id: OOMPAH-706
type: bug
status: Open
priority: 1
title: Make duplicate-preflight verdict delivery truncation-proof
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-02T21:55:47.761417Z'
updated_at: '2026-08-02T22:06:54.746954Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 82145263e666d6ef638c055ad7010f38bff980cdc24ed61b65e79d6555a76293
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 3c882ade-6955-4154-9ca1-0a7df367fb9a
  claim_owner: 0b22eab2-a2d1-4082-a6c8-404ec37650a4
  claimed_at: '2026-08-02T22:06:48.339113+00:00'
  claim_expires_at: '2026-08-02T22:36:48.339113+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 09332cfd-89eb-40a1-8bdc-5852580d439d
---
## Summary

Triggered by: OOMPAH-701

Production regression observed while dispatching OOMPAH-701 on 2026-08-02 after OOMPAH-682 was merged. Two independent Duplicate Investigator runs both concluded no_duplicate in prose, but each placed the machine-readable verdict after a long narrative and exhausted its response before completing a parseable verdict block. Oompah classified both normal successful exits as inconclusive and scheduled retry delays (60s, then 120s), leaving an otherwise actionable task Open.

Implementation scope:
- Make the duplicate-investigator prompt and transport reserve a small leading structured result envelope before any optional reasoning, and validate that the selected provider/model can comply within its output budget.
- Prefer a typed/tool result or constrained machine-readable channel that cannot be displaced by narrative. If text remains supported, parse a complete leading verdict before optional trailing prose and bound the narrative budget.
- Detect normal provider completion containing an unambiguous no_duplicate conclusion but a missing/truncated contract as a contract/output failure with actionable observability, not an opaque retry.
- Preserve fail-closed behavior against task-comment injection, stale claims, ambiguous prose, and forged verdicts.
- Prevent repeated identical malformed completions from silently consuming the full retry budget; vary/fallback the provider or surface the contract failure explicitly.

Relevant code: oompah/duplicate_screening.py; duplicate-preflight prompt/rendering and finish paths in oompah/orchestrator.py and oompah/focus.py; ACP provider output limits/structured result handling; duplicate-screening metrics and comments.

Required tests:
- A provider that attempts long narrative cannot displace the leading structured no_duplicate verdict.
- A response truncated after a complete leading verdict is accepted, while narrative-only or partial verdict content remains inconclusive.
- Two identical contract failures do not produce an unbounded same-provider retry loop.
- Late/stale output and user-authored comments cannot satisfy the verdict.
- The exact OOMPAH-701 response shape reaches implementation dispatch without owner intervention.

Acceptance criteria:
- Duplicate screening reaches a conclusive result within one normal successful agent completion when the investigator determines no duplicate.
- Output truncation cannot remove the authoritative verdict.
- Contract failures are visible and bounded, with deterministic focused tests and make test/check-secrets passing.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-02 22:06
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-02 22:06
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
