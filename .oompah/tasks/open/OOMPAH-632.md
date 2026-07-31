---
id: OOMPAH-632
type: bug
status: Open
priority: 1
title: Refresh candidate refs before child landing reconciliation
parent: OOMPAH-584
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T00:46:34.785511Z'
updated_at: '2026-07-31T00:48:59.904176Z'
work_branch: epic-OOMPAH-584--task-OOMPAH-632
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 086c243d77d576cb1f23c0dac01f07be249264f5de6a58316a69d9e72e7ce663
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-31T00:48:54.105090+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\n\nDuplicate preflight verdict: no_duplicate\n\
    \nMatches: none\n\nEvidence: Active tasks OOMPAH-281 and OOMPAH-282 are unrelated.\
    \ Closest reviewed historical tasks\u2014OOMPAH-162, OOMPAH-168, OOMPAH-216, and\
    \ OOMPAH-219\u2014are terminal and cover different reconciliation problems. No\
    \ files or tracker state were modified."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 8c95c3d6-1f5f-4d13-860c-7355e3432abf
oompah.work_branch: epic-OOMPAH-584--task-OOMPAH-632
oompah.integration:
  version: 1
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-584--task-OOMPAH-632
  base_branch: epic-OOMPAH-584
  base_sha: d62dd4cff702ae2b818418407d7d15b7a643213e
  updated_at: '2026-07-31T00:47:31.212817+00:00'
oompah.task_costs:
  total_input_tokens: 595655
  total_output_tokens: 3140
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 595655
      output_tokens: 3140
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 595655
    output_tokens: 3140
    cost_usd: 0.0
    recorded_at: '2026-07-31T00:48:54.103873+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-632__20260731T004738Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: epic-OOMPAH-584--task-OOMPAH-632
    source_sha: d62dd4cff702ae2b818418407d7d15b7a643213e
    completed_at: '2026-07-31T00:48:54.116448+00:00'
---
## Summary

Implementation scope: make Done-child landing reconciliation fetch authoritative remote refs for both the rollup container branch and every recorded/canonical candidate task branch before comparing patches. A force-pushed rebase must not be judged from a stale refs/heads task branch when refs/remotes/origin contains the rewritten commit. Preserve fail-closed behavior when either required fetch cannot be proven and do not mutate genuine unlanded children. Relevant code: oompah/orchestrator.py landing-evidence refresh and merged-epic child reconciliation. Tests: reproduce a local task branch at the pre-rebase SHA with origin/task at a rewritten SHA already contained in the landed target; prove reconciliation accepts it, while fetch failures defer mutation and genuinely unlanded rewritten heads still escalate. Acceptance criteria: an auditor PASS cannot be overwritten by stale local source evidence; focused epic-strategy tests and the complete Makefile gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-31 00:46
---
Claimed directly by the operator Codex session because stale candidate-ref reconciliation is currently re-escalating OOMPAH-595 after a valid auditor PASS and blocks the green recovery epic. Implementing the regression fix against the latest OOMPAH-584 head now.
---
author: oompah
created: 2026-07-31 00:47
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-31 00:47
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-31 00:48
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 10
- Tokens: 595.7K in / 3.1K out [598.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 27s
- Log: OOMPAH-632__20260731T004738Z.jsonl
---
<!-- COMMENTS:END -->
