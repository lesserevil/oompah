---
id: OOMPAH-1229
type: task
status: In Progress
priority: null
title: Stabilize WebSocket completion fault-injection synchronization
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T09:37:50.327401Z'
updated_at: '2026-08-24T08:01:56.022883Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: oompah
  operation_kind: api_task_create
  creation_marker: 1392a045-7295-4cfd-8a46-295cbe950be9
  request_fingerprint: cc9c91296985b97656c171e2976056fe6d8bbd5cabb832cae4e84348f15dddcc
oompah.lifecycle_revision: 2
oompah.last_batch:
  batch_id: batch-41327bd44d2248989351b0a98c84746f
  actor: shedwards
  committed_at: '2026-08-18T16:18:18.970327Z'
  operation:
    kind: whole_column_move
    source_status: Backlog
    scope: flat_board
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: fd6a6bc927ee173374556df071e911a6dacc4d5de0740f7b52a5fe1dee158923
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-21T14:38:19.048840+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: ** OOMPAH-1229 is a test-level synchronization fix for\
    \ WebSocket broadcast observation in the fault-injection test suite, addressing\
    \ Python 3.13 flakiness. The corpus contains only systemic orchestrator/workflow\
    \ repair tasks (OOMPAH-1000/1001\u20131014, 1073\u20131084) all concerned with\
    \ terminal audit dispatch, epic validation, workflow admission, and quality gates\u2014\
    no overlap with test synchronization or WebSocket/broadcast behavior. All similar-scoring\
    \ tasks (0.5 similarity) are keyword-matched on generic terms like \"test\" or\
    \ \"synchronization\" but address unrelated domains. OOMPAH-1229 is genuinely\
    \ novel and should proceed to implementation.\nLooking at OOMPAH-1229 and comparing\
    \ it with the supplied project task corpus, I need to determine if this is a duplicate.\n\
    \n**OOMPAH-1229 Analysis:**\n- **Issue**: WebSocket completion fault-injection\
    \ test `test_four_completion_snapshots_converge_to_zero_running_chips` is flaky\
    \ in Python 3.13, intermittently observing only 3 of 4 broadcast completion envelopes\n\
    - **Root cause**: Race condition where the final zero-running broadcast arrives\
    \ after the assertion\n- **Solution scope**: Replace timing-dependent observation\
    \ with explicit bounded synchronization, preserve real WebSocket/broadcast/full-sync\
    \ paths, avoid sleeps as correctness mechanism\n\n**Corpus Review:**\n\nThe provided\
    \ corpus contains 25 candidate tasks plus the current task. I've reviewed all\
    \ of them:\n\n1. **OOMPAH-1 to OOMPAH-17** (Archived/Archived): Historical CI/release\
    \ tasks, unrelated\n2. **OOMPAH-1000 to OOMPAH-1014** (Merged/Done): Systemic\
    \ workflow orchestrator bugs (terminal audit dispatch, epic validation, workflow\
    \ admission fencing, quality-gate lifecycle, health scanning)\u2014all complete\
    \ and focused on server/workflow coordination\n3. **OOMPAH-1073 to OOMPAH-1084**\
    \ (Merged/Done): Follow-up fixes from the OOMPAH-940 live incident (owner claims,\
    \ epic auto-close retirement, branch gate blocking, workflow reconciliation bounds,\
    \ PRqueue head propagation)\u2014all complete\n\n**Key Distinctions:**\n\n- OOMPAH-1229\
    \ addresses **test synchronization flakiness** in the WebSocket fault-injection\
    \ test suite\n- All other active/completed tasks address **systemic orchestrator/workflow\
    \ issues** (coordination, authority validation, health scanning, terminal audit\
    \ lifecycle)\n- No other task mentions WebSocket, broadcast completion envelopes,\
    \ fault injection, or the specific test `test_four_completion_snapshots_converge_to_zero_running_chips`\n\
    - OOMPAH-1229 is the only Open task; all others are terminal states\n\n---\n\n\
    **Focus handoff: duplicate_detector**\n\n**Duplicate preflight verdict: no_duplicate**\n\
    \n**Matches: none**\n\n**Evidence:*"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 2
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: b91589af-4061-4d17-bf05-3d3e831de2a6
oompah.work_contributors:
  runs:
  - run_id: 190a7293314449c2ada31002bbbaa419--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1229
    source_sha: null
    completed_at: ''
  - run_id: 190a7293314449c2ada31002bbbaa419--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1229
    source_sha: null
    completed_at: ''
  - run_id: 71d95951ec3d4994b2e05c931ec66ae6--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1229
    source_sha: null
    completed_at: ''
  - run_id: 71d95951ec3d4994b2e05c931ec66ae6--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1229
    source_sha: null
    completed_at: ''
  - run_id: cf84a141fe194b2498337571cc7d87bf--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1229
    source_sha: null
    completed_at: ''
  - run_id: bee9d072ab1c41f3b2da24772941150f--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1229
    source_sha: null
    completed_at: ''
  - run_id: 998b00c29f6e4c09811cecd9ee4b899e--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1229
    source_sha: null
    completed_at: ''
  - run_id: f3c18749e2d24c619e527e12fba78f01--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1229
    source_sha: c7b3911883a90c1b5805204a430926eb1c6f53b8
    completed_at: '2026-08-21T14:38:19.063310+00:00'
  - run_id: 2ac180f85bcd4d03841653ef8b1311fa--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: security
    source_branch: OOMPAH-1229
    source_sha: null
    completed_at: ''
  - run_id: 2cfee11c2e434b2288c4b2c0c52841e3--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: security
    source_branch: OOMPAH-1229
    source_sha: null
    completed_at: ''
  - run_id: 3ebd1d75b6f8466db50d6734808818e2--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: security
    source_branch: OOMPAH-1229
    source_sha: null
    completed_at: ''
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 1596
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 1596
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1596
    cost_usd: 0.0
    recorded_at: '2026-08-21T14:38:19.045611+00:00'
---
## Summary

Bug observed in hosted Python 3.13 gate for OOMPAH-1227 PR #856: tests/test_ws_fault_injection.py::TestLiveDashboardConvergence::test_four_completion_snapshots_converge_to_zero_running_chips intermittently records only 3 of 4 broadcast completion envelopes because the final zero-running broadcast races the assertion, while Python 3.11/3.12 pass. This is unrelated to the GitLab provider patch but makes branch gates nondeterministic. Scope: replace timing-dependent portal/broadcast observation with an explicit bounded synchronization point that proves all four broadcasts were processed before asserting; preserve the real WebSocket/broadcast/full-sync path and avoid sleeps as correctness. Add/adjust regression coverage across supported Python versions. Acceptance: the test reliably observes all four deliberately dropped completion states, then proves a full sync converges to zero chips; repeated focused runs and the hosted Makefile matrix pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-13 09:38
---
Filed from PR #856's hosted Python 3.13 gate. Exact failure: the test asserted immediately after four portal.call(_broadcast, ...) invocations but the final zero-running envelope had not yet reached the patched send seam (3 observed). Python 3.11/3.12 passed. Rerunning the failed gate to confirm nondeterminism; scheduling fix separately so the live GitLab deadlock patch remains narrowly scoped.
---
author: oompah
created: 2026-08-20 23:02
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-20 23:02
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-20 23:04
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 55s
- Log: OOMPAH-1229__20260820T230342Z.jsonl
---
author: oompah
created: 2026-08-21 00:16
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 00:17
---
Run #1 [attempt=1, profile=default, role=— -> Claude/haiku]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 57s
---
author: oompah
created: 2026-08-21 01:53
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 01:54
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 01:54
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: interrupted, Duration: 1m 14s
- Log: OOMPAH-1229__20260821T015414Z.jsonl
---
author: oompah
created: 2026-08-21 01:54
---
Duplicate screening was inconclusive 3 times. Human action required: a project owner must review the authoritative task corpus and use the authenticated duplicate-screening owner-resolution action (POST /api/v1/issues/OOMPAH-1229/duplicate-screening/owner-resolution) with a conclusive verdict and reason. This records the owner decision, resets the retry budget, and returns no_duplicate tasks to Open (or routes a verified duplicate to Duplicate Candidate). A plain verdict comment is not authoritative.
---
author: oompah
created: 2026-08-21 05:29
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 05:30
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 05:30
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 22s
- Log: OOMPAH-1229__20260821T053028Z.jsonl
---
author: oompah
created: 2026-08-21 10:29
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 10:30
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 10:31
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 48s
- Log: OOMPAH-1229__20260821T103047Z.jsonl
---
author: oompah
created: 2026-08-21 14:36
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 14:37
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 14:38
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.6K out [1.6K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 40s
- Log: OOMPAH-1229__20260821T143725Z.jsonl
---
author: oompah
created: 2026-08-23 23:13
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-23 23:13
---
Focus: Security Auditor
---
author: oompah
created: 2026-08-24 06:24
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-24 06:24
---
Focus: Security Auditor
---
author: oompah
created: 2026-08-24 06:25
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 55s
- Log: OOMPAH-1229__20260824T062434Z.jsonl
---
author: oompah
created: 2026-08-24 07:02
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-24 07:04
---
Focus: Security Auditor
---
author: oompah
created: 2026-08-24 07:05
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 2m 30s
- Log: OOMPAH-1229__20260824T070431Z.jsonl
---
author: oompah
created: 2026-08-24 08:01
---
Agent dispatched (profile: default)
---
<!-- COMMENTS:END -->
