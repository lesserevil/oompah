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
updated_at: '2026-08-02T22:11:37.674410Z'
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
  claim_id: 8d15a3de-134a-492e-81b3-8c0db8903a48
  claim_owner: 0b22eab2-a2d1-4082-a6c8-404ec37650a4
  claimed_at: '2026-08-02T22:11:31.635025+00:00'
  claim_expires_at: '2026-08-02T22:41:31.635025+00:00'
  retry_count: 2
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: aec8c7ea-8cf1-4b45-8e2c-1713e97345f6
oompah.task_costs:
  total_input_tokens: 110748
  total_output_tokens: 3384
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 110748
      output_tokens: 3384
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1372
    cost_usd: 0.0
    recorded_at: '2026-08-02T22:07:19.608253+00:00'
  - profile: default
    model: haiku
    input_tokens: 110738
    output_tokens: 2012
    cost_usd: 0.0
    recorded_at: '2026-08-02T22:09:19.796427+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-706__20260802T220658Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-706
    source_sha: 366129d0a5046c5ed7caed4acf26cd8cd2a3fbdd
    completed_at: '2026-08-02T22:07:19.647136+00:00'
  - run_id: OOMPAH-706__20260802T220834Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-706
    source_sha: 366129d0a5046c5ed7caed4acf26cd8cd2a3fbdd
    completed_at: '2026-08-02T22:09:19.824930+00:00'
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
author: oompah
created: 2026-08-02 22:07
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 4, Tool calls: 0
- Tokens: 10 in / 1.4K out [1.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 28s
- Log: OOMPAH-706__20260802T220658Z.jsonl
---
author: oompah
created: 2026-08-02 22:08
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-02 22:08
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-02 22:09
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 3
- Tokens: 110.7K in / 2.0K out [112.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 49s
- Log: OOMPAH-706__20260802T220834Z.jsonl
---
author: oompah
created: 2026-08-02 22:11
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-02 22:11
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
