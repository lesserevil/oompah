---
id: OOMPAH-1229
type: task
status: Open
priority: null
title: Stabilize WebSocket completion fault-injection synchronization
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T09:37:50.327401Z'
updated_at: '2026-08-21T01:52:56.665604Z'
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
oompah.lifecycle_revision: 1
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
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 79bae9518fcb588f68d79d577713d9cde9e3d28e8a026095692d8e1295c1cc5e:142859
  claim_owner: 884c7b0a-4fe0-4acd-9fe6-041416485094
  claimed_at: '2026-08-21T01:52:42.913087+00:00'
  claim_expires_at: '2026-08-21T02:22:42.913087+00:00'
  retry_count: 2
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: db85869b-0d2b-4efa-9826-02e5ccf08f4e
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
<!-- COMMENTS:END -->
