---
id: OOMPAH-795
type: feature
status: In Progress
priority: 1
title: Expose one why-not-progressing projection and make alerts truthful
parent: OOMPAH-770
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-796
- OOMPAH-779
labels: []
assignee: null
created_at: '2026-08-04T13:59:25.042939Z'
updated_at: '2026-08-06T07:31:11.823566Z'
work_branch: epic-OOMPAH-770--task-OOMPAH-795
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: cca5bb79b5ef913d067319f95efd895068f95d98a3219c342eac066a5b54df29
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-06T03:52:37.482346+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: OOMPAH-770 is the parent epic, while OOMPAH-784 covers\
    \ SLO metrics and OOMPAH-821 covers terminal-audit recovery alerts. None is an\
    \ active duplicate of this projection/parity task.\nFocus handoff: duplicate_detector\
    \  \nDuplicate preflight verdict: no_duplicate  \nMatches: none  \n\nEvidence:\
    \ OOMPAH-770 is the parent epic, while OOMPAH-784 covers SLO metrics and OOMPAH-821\
    \ covers terminal-audit recovery alerts. None is an active duplicate of this projection/parity\
    \ task."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 7b681f73-6bbc-4059-a848-183ddd630e65
oompah.work_branch: epic-OOMPAH-770--task-OOMPAH-795
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-770--task-OOMPAH-795
  base_branch: epic-OOMPAH-770
  base_sha: 2bc189d706a6afcf7ecc8b2f5ac8a572a93d522b
  updated_at: '2026-08-06T03:56:31.779212+00:00'
oompah.task_costs:
  total_input_tokens: 47754
  total_output_tokens: 416
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 47754
      output_tokens: 416
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 47754
    output_tokens: 416
    cost_usd: 0.0
    recorded_at: '2026-08-06T03:52:34.515888+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-795__20260806T034836Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: epic-OOMPAH-770--task-OOMPAH-795
    source_sha: 2bc189d706a6afcf7ecc8b2f5ac8a572a93d522b
    completed_at: '2026-08-06T03:52:34.531472+00:00'
---
## Summary

Make API, dashboard board/detail, queue rows, agent panels, and alerts consume WorkDecision rather than local heuristics. Expose owner, disposition, reason code/text, prerequisites, evidence revision, next reassessment, recovery action, and action_required. Global warnings must contain only operator-actionable conditions; queued work, active repair, retry backoff, audit rotation, CI pending, and capacity waits remain task-local/informational. Preserve WebSocket sequence/full-sync behavior and secret redaction. Required tests: executor/UI parity, alert severity transitions and clearing, stale snapshot resync, compact dashboard rendering, accessibility, auth/redaction, and no warning for normal recovery. Acceptance: operator can answer why any task is idle from one projection and every global warning requires an actual operator action.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-06 03:19
---
Promoted from Backlog to Open after hard-start prerequisite OOMPAH-796 reached Done. Project is temporarily paused for the graceful cutover; dispatch normally on resume.
---
author: oompah
created: 2026-08-06 03:47
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-06 03:47
---
Fresh live acceptance evidence after fe6257b restart: the global alert list warns 'Terminal-audit backlog is stale' with oldest age 4186s while explicitly reporting 0 pending audits, plus an operator-auth warning for one recent failed probe that will age out without operator action. Both exemplify normal/stale conditions that must be task-local/informational rather than global warning banners unless an action_required recovery exists.
---
author: oompah
created: 2026-08-06 03:47
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-06 03:52
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 47.8K in / 416 out [48.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 5m 11s
- Log: OOMPAH-795__20260806T034836Z.jsonl
---
author: oompah
created: 2026-08-06 03:56
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-06 03:56
---
Focus: Oompah Tests Auth Specialist
---
author: oompah
created: 2026-08-06 03:56
---
Understanding: unify API/dashboard/queue/agent/alert consumers around one WorkDecision projection, with truthful operator-only global warnings and preserved websocket sync/redaction. I will inspect the existing projection, alert, auth, and UI contracts, implement focused compatibility-safe changes, add regression tests for parity/severity/resync/rendering/redaction, and verify the affected suites.
---
author: oompah
created: 2026-08-06 03:57
---
Discovery: the branch already has pure WorkDecision evaluation and an enforce-mode controller, but consumers still read legacy rows/alerts; the public snapshot exposes no canonical task decision collection. I am tracing retained controller state and snapshot assembly to add a shared projection at the state boundary while preserving websocket sequencing and auth redaction.
---
author: oompah
created: 2026-08-06 04:14
---
Implementation: added the shared redacted WorkDecision projection boundary and cache, attached it to state/running/retry/queue, board/detail responses, and a protected single-task endpoint. Global alerts now require explicit action_required plus warning severity; the dashboard renders the same reason/owner/prerequisite/action fields with escaped accessible markup. Added projection documentation and parity/redaction/alert/UI tests.
---
author: oompah
created: 2026-08-06 04:21
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 211
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 25m 30s
- Log: OOMPAH-795__20260806T035642Z.jsonl
---
author: oompah
created: 2026-08-06 07:31
---
Independent static review REJECTED the current uncommitted repair. Blockers: queued audit age still becomes a false actionable error; failed-project truth is lost after cold restart; several alert and agent-panel identities remain identifier-only across projects; full-sync can publish old decisions with newer issues and discard the intervening update; reload epoch/tracker cutover is non-atomic and does not immediately notify/refresh; Done parity tests do not prove cache/API/UI behavior. Accepted epoch fencing, redaction, and card/detail identity work will be preserved while repair continues. No tests were run.
---
<!-- COMMENTS:END -->
