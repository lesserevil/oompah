---
id: OOMPAH-675
type: bug
status: In Progress
priority: 1
title: Keep the parallel pytest gate stable when workers terminate
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-01T04:59:55.163807Z'
updated_at: '2026-08-01T05:12:08.847374Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 5ab5cde2ab072b5c4f07af63d1f20e0931acb6036cfa517d764ef6c88708cd73
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-01T05:11:47.902873+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector  \nDuplicate preflight verdict: no_duplicate\
    \  \nMatches: none  \nEvidence: Searched active and terminal task records for\
    \ xdist, pytest worker termination, node-down, replacement-worker, process-group,\
    \ and parallel-gate terms. Closest matches were archived OOMPAH-219 and unrelated\
    \ active OOMPAH-281; neither covers this issue. No files or tracker state were\
    \ modified."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: a491585b-73cd-4e7b-8a5a-16f264ae4cad
oompah.task_costs:
  total_input_tokens: 348763
  total_output_tokens: 2085
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 348763
      output_tokens: 2085
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 348763
    output_tokens: 2085
    cost_usd: 0.0
    recorded_at: '2026-08-01T05:11:47.900532+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-675__20260801T051057Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-675
    source_sha: cde6401136d6561b694b05f81f4337cd26d7a3fe
    completed_at: '2026-08-01T05:11:47.923643+00:00'
---
## Summary

Discovered while validating OOMPAH-674 on 2026-08-01. Two consecutive make test runs with the configured four xdist workers aborted after workers reported node down: Not properly terminated; xdist created replacement workers and LoadGroupScheduling then crashed with KeyError for WorkerController gw6. Runs stopped near 47 percent with roughly 6,956 tests passed, so the controller did not preserve actionable identities for the original failures. Focused one-worker selections pass. Implementation scope: reproduce and identify why bounded tests terminate xdist workers, ensure lifecycle or process-group tests cannot kill their pytest worker, and make the gate surface original test failures without scheduler-internal replacement crashes. Relevant areas: Makefile test target, scripts/run-tests.sh, pytest timeout and xdist configuration, process lifecycle tests. Acceptance criteria: repeated configured four-worker gates complete without lost workers or xdist internal errors; intentional timeouts report the responsible test; isolation guarantees remain intact; regression coverage exercises worker failure and replacement behavior where practical.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-01 05:10
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-01 05:10
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-01 05:11
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 7
- Tokens: 348.8K in / 2.1K out [350.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 54s
- Log: OOMPAH-675__20260801T051057Z.jsonl
---
author: oompah
created: 2026-08-01 05:12
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-01 05:12
---
Focus: Software Engineer
---
<!-- COMMENTS:END -->
