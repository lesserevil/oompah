---
id: OOMPAH-710
type: bug
status: Open
priority: null
title: Keep oversized auditor tool results inside the read-only authority boundary
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-02T23:45:39.918535Z'
updated_at: '2026-08-02T23:51:13.871916Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: f64744d5cece2f0044fdcdb2efdf7ceb2d7c11e4cc2e54b922d072574a454bd6
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 65bfa554-8c1f-424e-86f8-931c0afef4f1
  claim_owner: e66a0cec-af3d-4845-bbdc-4b14727350de
  claimed_at: '2026-08-02T23:51:07.847725+00:00'
  claim_expires_at: '2026-08-03T00:21:07.847725+00:00'
  retry_count: 2
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 590ba94c-4338-4d32-aa04-424cc8bacc37
oompah.task_costs:
  total_input_tokens: 51458
  total_output_tokens: 3004
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 51458
      output_tokens: 3004
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1342
    cost_usd: 0.0
    recorded_at: '2026-08-02T23:46:36.307344+00:00'
  - profile: default
    model: haiku
    input_tokens: 51448
    output_tokens: 1662
    cost_usd: 0.0
    recorded_at: '2026-08-02T23:48:58.135833+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-710__20260802T234610Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-710
    source_sha: 3a231ee97337db95bb131abc0dd27ca12133c257
    completed_at: '2026-08-02T23:46:36.314348+00:00'
  - run_id: OOMPAH-710__20260802T234817Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-710
    source_sha: 3a231ee97337db95bb131abc0dd27ca12133c257
    completed_at: '2026-08-02T23:48:58.152118+00:00'
---
## Summary

Triggered by: OOMPAH-701 terminal audit audit-c521d3856622 on 2026-08-02.

Production evidence: two independent Claude completion auditors (opus and sonnet) were terminated by the bounded repeated-policy-denial guard after using the approved read_file tool on a large source file. The ACP backend persisted the oversized 1,452,395-character result under ~/.claude/projects/.../tool-results outside the read-only terminal-audit worktree and instructed the model that it MUST read that path. The strict auditor authority boundary then denied the required follow-up access. Both transports failed, OOMPAH-701 remained In Validation, terminal_audit_health:launch_failures alerted with two transport failures, and the public running-agent list was empty while terminal-audit running remained 1.

Implementation scope:
- Keep oversized read/search output needed by an auditor inside an explicitly approved read-only result channel or audit-scoped temp root; do not direct a strict auditor to provider-private paths outside its authority.
- Prefer bounded/chunked tool responses that the model can continue reading through the approved MCP surface.
- Classify repeated policy denial caused by provider output persistence precisely and continue through eligible independent transports without stranding the audit.
- Make queued/running/in-progress audit counters describe the same durable/provider lifecycle while between candidates or exhausted.
- Clear launch/transport health once the affected audit is resolved so later audits are not contaminated.

Relevant code: oompah/acp_backends/claude.py and ACP tool-result bridging/truncation; oompah/api_agent.py approved file tools; oompah/authority_boundary.py auditor policy; oompah/orchestrator.py terminal-audit retry bookkeeping; terminal-audit health snapshot code.

Required tests:
- Reproduce an auditor reading a >1 MB file and prove every continuation path remains within its approved read-only worktree/tool channel.
- Run two candidate failures followed by a healthy independent candidate and prove the audit retries and completes exactly once.
- Assert public running agents, audit queued/running counters, health in_progress_count, and process liveness agree between attempts and after exhaustion.
- Assert the transport-failure alert clears after successful recovery and does not leak into a later audit.
- Focused ACP/auditor tests and make test/check-secrets pass.

Acceptance criteria:
- A compliant read-only auditor cannot be forced into an authority denial by Oompah/provider oversized-output handling.
- OOMPAH-701-style audits either launch a visible candidate or expose a truthful queued/exhausted state, never running=1 with no provider and in_progress=0.
- Recovery completes the terminal transition and clears the alert without an owner override.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-02 23:46
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-02 23:46
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-02 23:46
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.3K out [1.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 29s
- Log: OOMPAH-710__20260802T234610Z.jsonl
---
author: oompah
created: 2026-08-02 23:48
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-02 23:48
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-02 23:49
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 51.4K in / 1.7K out [53.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 44s
- Log: OOMPAH-710__20260802T234817Z.jsonl
---
author: oompah
created: 2026-08-02 23:51
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-02 23:51
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
