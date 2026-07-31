---
id: OOMPAH-663
type: task
status: Open
priority: null
title: Canonicalize integrated-task fingerprints for owner overrides
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T13:52:05.961085Z'
updated_at: '2026-07-31T14:04:04.513891Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 9c360850b6c5b27e660228b90dfb195a9e618c097840d9bc4e5d7613b84d84cf
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-31T14:04:00.236167+00:00'
  matched_identifiers: []
  evidence: "No repository or tracker mutations were made.\n\nFocus handoff: duplicate_detector\
    \  \nDuplicate preflight verdict: no_duplicate  \nMatches: none  \nEvidence: Active\
    \ OOMPAH-645, OOMPAH-658, and OOMPAH-661 cover transport-health, duplicate-preflight,\
    \ and retry-authority issues respectively. Closest terminal records OOMPAH-604,\
    \ OOMPAH-577, OOMPAH-626, OOMPAH-627, and OOMPAH-653 are Done/Merged and therefore\
    \ excluded; their scopes differ from this canonical integrated-evidence fingerprint\
    \ bug."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: cd436e5a-c0f6-4cc3-8afc-7b0258555ee2
oompah.task_costs:
  total_input_tokens: 3662929
  total_output_tokens: 8902
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 3662929
      output_tokens: 8902
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 3662929
    output_tokens: 8902
    cost_usd: 0.0
    recorded_at: '2026-07-31T14:04:00.235023+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-663__20260731T140033Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-663
    source_sha: ef2938146bf828ddc8d8d677501f4fad61d65a73
    completed_at: '2026-07-31T14:04:00.251325+00:00'
---
## Summary

Bug reproduction: OOMPAH-660 was integrated at 793bcc7969d39634dab560ed0a10b9dcad7a9716, but its integration-staged Done audit fingerprinted the epic branch and a git-branch contributor while the API owner-override path recomputed evidence from the normalized task issue. The legitimate project-owner override therefore failed with HTTP 409 until a duplicate Done request was restaged with the API fingerprint. Implementation scope: define one canonical evidence snapshot/fingerprint path for integrated-task terminal audit creation, API and ACP owner overrides, and restart recovery. Preserve auditor-independence provenance separately if it must not be part of the canonical task evidence. Relevant files include oompah/orchestrator.py, oompah/server.py, oompah/acp_tools.py, oompah/terminal_audit.py, and terminal-transition tests. Add regression coverage that stages an integrated task audit, routes it to Needs Human for no independent candidate, and applies an authorized owner override without restaging; also verify a genuinely changed integration SHA still fails closed. Acceptance criteria: the first valid override succeeds and retires the audit alert, no duplicate terminal request is needed, stale evidence remains rejected, and focused plus full Makefile gates pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-31 14:00
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-31 14:00
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-31 14:04
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 36
- Tokens: 3.7M in / 8.9K out [3.7M total]
- Cost: $0.0000
- Exit: normal, Duration: 3m 30s
- Log: OOMPAH-663__20260731T140033Z.jsonl
---
<!-- COMMENTS:END -->
