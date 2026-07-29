---
id: OOMPAH-540
type: task
status: In Review
priority: null
title: Let read-only duplicate preflight bypass dependency and epic serialization
  gates
parent: null
children: []
blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-07-29T00:46:32.053029Z'
updated_at: '2026-07-29T00:53:51.638567Z'
work_branch: OOMPAH-540
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/572
review_number: '572'
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: ab83d9f4e304a67a40246836c5e51e480ddc6fed67248267b351bb1d20b021f9
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-29T00:50:22.043099+00:00'
  matched_identifiers: []
  evidence: "I've completed a thorough search across all task states and documentation.\
    \ Here is my conclusion:\n\n---\n\nFocus handoff: duplicate_detector\n\nDuplicate\
    \ preflight verdict: no_duplicate\n\nMatches: none\n\nEvidence: I searched all\
    \ non-terminal task files (open: OOMPAH-281, backlog: OOMPAH-282), all archived\
    \ tasks, all merged tasks, and all documentation in `docs/` and `plans/` using\
    \ patterns covering: `duplicate preflight`, `preflight`, `screening`, `scheduler\
    \ eligibility`, `dependency gate`, `epic serialization`, `bypass`, `shared-epic`,\
    \ `one-agent-per-epic`, `unchecked queue`, and the specific task IDs OOMPAH-471\
    \ through OOMPAH-489 mentioned in the description. No matches appeared for any\
    \ of these patterns across the entire task corpus. The two active non-terminal\
    \ tasks (OOMPAH-281: containerized self-hosted GitHub Actions runner; OOMPAH-282:\
    \ `state_branch_migration` UnicodeEncodeError) cover entirely unrelated topics.\
    \ `docs/duplicate-screening.md` confirms the duplicate screening feature exists\
    \ and currently applies full implementation eligibility gates (including dependency/shared-epic\
    \ serialization) to screening agents \u2014 exactly the bug OOMPAH-540 describes\
    \ \u2014 but no prior task has addressed bypassing those gates for `duplicate_preflight=True`.\
    \ OOMPAH-540 is a novel, first-of-its-kind scheduler enhancement request with\
    \ no active counterpart in the task graph."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: ef3574fd-dfd0-43ee-b663-8287aef7f342
oompah.task_costs:
  total_input_tokens: 22
  total_output_tokens: 4352
  total_cost_usd: 0.0
  by_model:
    sonnet:
      input_tokens: 22
      output_tokens: 4352
      cost_usd: 0.0
  runs:
  - profile: standard
    model: sonnet
    input_tokens: 22
    output_tokens: 4352
    cost_usd: 0.0
    recorded_at: '2026-07-29T00:50:22.042786+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/572
oompah.review_number: '572'
oompah.work_branch: OOMPAH-540
oompah.target_branch: main
---
## Summary

The Open-task duplicate-preflight implementation incorrectly reuses normal implementation eligibility for dependency readiness and one-agent-per-epic/shared-branch serialization. This defeats the feature's purpose: duplicate checks are read-only qualification work intended to run early on any ordinary Open task while screening capacity is available, even when implementation must wait on dependencies or another child is actively changing the shared epic branch. Production evidence on 2026-07-29: 21 unchecked Open tasks remained unscreened with 8 spare hardware slots because OOMPAH-471 through OOMPAH-489 were rejected by dependency/shared-epic gates.\n\nImplementation scope:\n- For duplicate_preflight=True only, bypass unresolved dependency/blocker readiness and one-agent-per-epic/shared-branch busy gates.\n- Continue enforcing ordinary-task/Open-state eligibility, exact per-task claim/running exclusivity, global/project pause, budget/rate/provider availability and whitelist, screening cap, deterministic ordering, and implementation-first capacity reservation.\n- Keep preflight strictly read-only and keep the task Open. Do not weaken any implementation dispatch gate.\n- Update documentation that currently says dependency and shared-epic constraints apply.\n\nRequired tests:\n- A dependency-blocked Open child can enter duplicate screening but cannot enter implementation.\n- A second child of a shared epic can screen while a sibling implementation agent is active, without moving state or mutating the worktree.\n- The same task cannot screen and implement concurrently and two preflights cannot claim the same task.\n- Pause, provider, budget, terminal/non-task, capacity cap, and implementation-lane reservation remain enforced.\n- Deterministic ordering remains stable and implementation behavior is unchanged. Run focused scheduler tests and make test.\n\nAcceptance criteria:\nWith spare screening capacity, blocked ordinary Open tasks and siblings of an actively implemented shared epic are selected for read-only duplicate preflight; implementation remains blocked until normal dependency/epic gates pass; screening stays Open and claim-safe; and production begins draining the existing unchecked Open queue.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 00:46
---
Claimed by the current interactive Codex session for immediate implementation and production verification; do not dispatch another worker for this task.
---
author: oompah
created: 2026-07-29 00:48
---
Duplicate screening dispatched (profile: standard, task remains Open)
---
author: oompah
created: 2026-07-29 00:48
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-29 00:50
---
Run #1 [attempt=1, profile=standard, role=standard -> Claude/sonnet]
- Turns: 48, Tool calls: 36
- Tokens: 22 in / 4.4K out [4.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 30s
- Log: OOMPAH-540__20260729T004855Z.jsonl
---
author: oompah
created: 2026-07-29 00:50
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-29 00:50
---
Focus: Maintenance Engineer
---
author: oompah
created: 2026-07-29 00:52
---
Stop work immediately and make no further changes or commits. This task is already implemented and fully tested in the owner's interactive OOMPAH-540 branch; this duplicate server worker was dispatched after ownership was recorded. Exit cleanly so the completed branch can be merged and deployed.
---
author: oompah
created: 2026-07-29 00:53
---
Agent completed successfully in 151s
---
author: oompah
created: 2026-07-29 00:53
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 30
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 31s
- Log: OOMPAH-540__20260729T005032Z.jsonl
---
author: oompah
created: 2026-07-29 00:53
---
Agent completed without landing — no commits found on origin for branch `OOMPAH-540`. Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-29 00:53
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-29 00:53
---
Focus: Maintenance Engineer
---
author: oompah
created: 2026-07-29 00:53
---
Temporarily marked human-only to prevent redispatch while the already-tested interactive branch is committed, merged, deployed, and verified. The label will be removed when the task is completed.
---
<!-- COMMENTS:END -->
