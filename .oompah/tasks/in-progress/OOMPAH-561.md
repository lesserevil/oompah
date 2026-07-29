---
id: OOMPAH-561
type: chore
status: In Progress
priority: 1
title: Prune terminal branches and worktrees aggressively
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-29T21:03:33.910422Z'
updated_at: '2026-07-29T21:06:13.745445Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 5564fb01f918b647d6568a7856225eb465888ace4cce6e15dfcfc4de0aba2a7a
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-29T21:05:46.512742+00:00'
  matched_identifiers: []
  evidence: 'Focus handoff: duplicate_detector


    Duplicate preflight verdict: no_duplicate


    Matches: none


    Evidence: Active tasks OOMPAH-281 and OOMPAH-282 are unrelated. Historical OOMPAH-168,
    OOMPAH-195, OOMPAH-219, OOMPAH-248, and OOMPAH-256 are terminal and cover distinct
    branch/worktree concerns. No repository changes or tracker mutations were made.'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 77ee1743-ccca-4780-beaf-3a43dfd2a300
oompah.task_costs:
  total_input_tokens: 435371
  total_output_tokens: 2824
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 435371
      output_tokens: 2824
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 435371
    output_tokens: 2824
    cost_usd: 0.0
    recorded_at: '2026-07-29T21:05:46.477859+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-561__20260729T210432Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-561
    source_sha: 31f8938b8f669a316a830690aaedcc1e0d3834bf
    completed_at: '2026-07-29T21:05:46.587322+00:00'
---
## Summary

Increase cleanup throughput for the parallel agent scheduler. Scope: make managed repository fetches prune deleted remote-tracking refs; give worktree cleanup its own short configurable interval and a higher bounded default batch; make terminal Merged/Archived cleanup remove the task or epic worktree plus its Oompah-owned local and remote work branch; do not count already-absent resources against the mutation budget; and sweep fully merged local branches whose upstream is gone. Preserve active/shared epic branches and protect default, configured target/release, and Git state branches. Relevant files: oompah/config.py, oompah/orchestrator.py, oompah/projects.py, oompah/repo_health.py, .env.example, docs/tick-latency-diagnostics.md, and focused tests under tests/. Tests must cover branch ownership/protection, shared-child safety, remote/local deletion, gone-upstream pruning, no-op budget behavior, interval/default configuration, and fetch --prune. Acceptance criteria: terminal Oompah-owned worktrees and branches are removed within the cleanup cadence; branch/worktree volume cannot grow merely because completed entries are revisited; protected or active refs are never deleted; focused tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 21:03
---
Implementation started from the primary checkout. Confirmed current gaps: five-minute inherited cleanup cadence, default batch 25, no-op entries consume the budget, terminal task/epic cleanup leaves local and remote branches, and managed fetch does not prune remote-tracking refs. Adding guarded terminal branch cleanup, safe gone-upstream pruning, independent interval/batch defaults, and regression coverage.
---
author: oompah
created: 2026-07-29 21:04
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-29 21:04
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-29 21:05
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 9
- Tokens: 435.4K in / 2.8K out [438.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 22s
- Log: OOMPAH-561__20260729T210432Z.jsonl
---
author: oompah
created: 2026-07-29 21:06
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-29 21:06
---
Focus: Maintenance Engineer
---
<!-- COMMENTS:END -->
