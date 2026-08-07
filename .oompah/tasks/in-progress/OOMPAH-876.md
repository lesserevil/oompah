---
id: OOMPAH-876
type: task
status: In Progress
priority: null
title: Retry auditor transport failures without consuming substantive candidate capacity
parent: OOMPAH-768
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-07T08:51:10.232904Z'
updated_at: '2026-08-07T10:19:57.828017Z'
work_branch: epic-OOMPAH-768--task-OOMPAH-876
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: a65ea1cca8d20eed7b092bbd7d9508a9efb66b5de9a560e5789a353e11a480e7
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-07T09:46:45.616533+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: OOMPAH-781 is terminal and excluded; active OOMPAH-874\
    \ concerns exact-gate cancellation, while OOMPAH-875 concerns integration-lane\
    \ starvation. Neither addresses auditor transport failures or candidate-capacity\
    \ accounting.\nFocus handoff: duplicate_detector  \nDuplicate preflight verdict:\
    \ no_duplicate  \nMatches: none  \n\nEvidence: OOMPAH-781 is terminal and excluded;\
    \ active OOMPAH-874 concerns exact-gate cancellation, while OOMPAH-875 concerns\
    \ integration-lane starvation. Neither addresses auditor transport failures or\
    \ candidate-capacity accounting."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 1d23cb04-ac65-49b3-8bf1-c91c752826aa
oompah.work_branch: epic-OOMPAH-768--task-OOMPAH-876
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-768--task-OOMPAH-876
  base_branch: epic-OOMPAH-768
  base_sha: 6a84d9bcc2ca1e3e825883d298793e04bd9c43a8
  updated_at: '2026-08-07T09:53:42.693673+00:00'
oompah.task_costs:
  total_input_tokens: 47741
  total_output_tokens: 1317
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 47741
      output_tokens: 1317
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 47731
    output_tokens: 303
    cost_usd: 0.0
    recorded_at: '2026-08-07T09:46:45.605951+00:00'
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1014
    cost_usd: 0.0
    recorded_at: '2026-08-07T10:19:20.766113+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-876__20260807T094554Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: epic-OOMPAH-768--task-OOMPAH-876
    source_sha: 6a84d9bcc2ca1e3e825883d298793e04bd9c43a8
    completed_at: '2026-08-07T09:46:45.640121+00:00'
  - run_id: OOMPAH-876__20260807T095353Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: oompah_tests
    source_branch: epic-OOMPAH-768--task-OOMPAH-876
    source_sha: 6a84d9bcc2ca1e3e825883d298793e04bd9c43a8
    completed_at: '2026-08-07T10:19:20.770428+00:00'
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
author: oompah
created: 2026-08-07 09:43
---
Live reproductions on 2026-08-07: OOMPAH-581 exhausted sonnet and opus after both transports terminated before a verdict, reaching Needs Human on its Done audit; OOMPAH-870 exhausted all eligible auditor candidates after pre-verdict transport terminations, reaching Needs Human on its Merged audit. Both had authoritative merged exact-head evidence and required owner overrides. Acceptance must ensure pre-verdict transport failure does not consume substantive candidate capacity or force Needs Human.
---
author: oompah
created: 2026-08-07 09:45
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-07 09:45
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-07 09:46
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 47.7K in / 303 out [48.0K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 32s
- Log: OOMPAH-876__20260807T094554Z.jsonl
---
author: oompah
created: 2026-08-07 09:52
---
Additional live reproduction: OOMPAH-426 exhausted its rearmed Archived audit after a prior PASS/finalization failure. Attempt 3 again ended without a usable transport verdict and forced Needs Human despite unchanged merged provenance; owner override restored Archived. Transport retries must preserve substantive candidate capacity and durable PASS finalization must not relaunch unnecessary auditors.
---
author: oompah
created: 2026-08-07 09:53
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-07 09:53
---
Focus: Oompah Tests Auth Specialist
---
author: oompah
created: 2026-08-07 09:54
---
Additional live reproduction: OOMPAH-414 reached Needs Human on Archived after the YOLO-reopen Claude/opus transport terminated (0 turns, 6 tool calls) and max attempts exhausted. No code verdict rejected the work; owner override restored terminal provenance.
---
author: oompah
created: 2026-08-07 10:02
---
Additional stale Needs Human reproduction: OOMPAH-575 had an independent Done PASS covering 14,163 tests and an existing owner-verified Merged state, but remained Needs Human from a historical Merged audit infrastructure exhaustion while Archived was queued. Owner recovery retained the merged/archived provenance; implementation was not reopened.
---
author: oompah
created: 2026-08-07 10:16
---
Additional live reproduction: OOMPAH-865 exact integrated head 04fa6781091e reached Needs Human after haiku/sonnet/opus all terminated before a verdict (0 turns; attempts lasted 14m05s, 17m00s, 16m40s). The code had independent acceptance plus 211 serial + 211 xdist4 focused validation and prior gate repairs; owner override restored Done. Pre-verdict transport termination must not consume the substantive candidate budget.
---
author: oompah
created: 2026-08-07 10:19
---
Agent completed successfully in 1549s (1024 tokens)
---
author: oompah
created: 2026-08-07 10:19
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 52, Tool calls: 16
- Tokens: 10 in / 1.0K out [1.0K total]
- Cost: $0.0000
- Exit: normal, Duration: 25m 49s
- Log: OOMPAH-876__20260807T095353Z.jsonl
---
author: oompah
created: 2026-08-07 10:19
---
Agent completed without closing this issue (1549s (1024 tokens)). Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---
<!-- COMMENTS:END -->
