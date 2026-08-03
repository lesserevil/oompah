---
id: OOMPAH-711
type: bug
status: Open
priority: null
title: Fence owner duplicate resolution from superseded preflight exit
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-02T23:59:03.600915Z'
updated_at: '2026-08-03T00:07:09.559718Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 202c56bf80474585cba587c717a0651c36dc9fd09908afc88a9cb21caf68b2d2
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 1cd5d6a2-1c59-4ce8-a539-9adfa878b46c
  claim_owner: 282fbdbd-517c-4b57-a6ee-f47cdefb1b24
  claimed_at: '2026-08-03T00:07:03.014324+00:00'
  claim_expires_at: '2026-08-03T00:37:03.014324+00:00'
  retry_count: 1
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 961341b2-26f7-459e-9496-63f74f9de936
oompah.task_costs:
  total_input_tokens: 224241
  total_output_tokens: 1710
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 224241
      output_tokens: 1710
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 224241
    output_tokens: 1710
    cost_usd: 0.0
    recorded_at: '2026-08-03T00:05:55.473586+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-711__20260803T000511Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-711
    source_sha: 93513d742b8abd45b6df2abf3683666787e24a42
    completed_at: '2026-08-03T00:05:55.493145+00:00'
---
## Summary

Triggered by: OOMPAH-710; regression of OOMPAH-682 and OOMPAH-535.

Live reproduction on 2026-08-02: OOMPAH-710 had a third duplicate-preflight worker active after two inconclusive contract failures. The authenticated project-owner resolution endpoint successfully recorded no_duplicate, reset retry_count to 0, and returned the task to Open. The owner then added human-only and moved the task to In Progress for direct implementation. After the superseded duplicate worker exited and the service later auto-updated, OOMPAH-710 surfaced as Done despite an uncommitted dirty implementation worktree and no task submit. The task had to be reopened manually. This violates OOMPAH-682 acceptance that late claim completion cannot overwrite a newer owner resolution or task revision.

Implementation scope:
- Make owner-resolution acquire/revoke the exact duplicate claim generation atomically and cancel/await any active matching preflight before returning success, or persist a generation tombstone that the exit path must honor.
- Make duplicate-preflight normal/cancelled/forced exit compare the current task fingerprint, owner-resolution generation, claim identity, and status before any tracker transition or completion bookkeeping.
- Never infer implementation completion/Done from a duplicate-investigator exit.
- Preserve the newer owner-selected Open/In Progress state and human-only ownership across graceful restart and auto-update.
- Keep visible agent/process lifecycle truthful while the superseded preflight is terminating.

Relevant code: duplicate owner-resolution route in oompah/server.py; duplicate claim/finish and worker-exit paths in oompah/orchestrator.py; oompah/duplicate_screening.py metadata generations; restart recovery covered by OOMPAH-701/704/707.

Required tests:
- Barrier-race a live duplicate worker exit against owner no_duplicate resolution, then move the task to In Progress and prove late output/exit cannot change status or retry metadata.
- Repeat with cancellation-resistant provider termination and prove the endpoint does not retire visibility before the process exits.
- Restart between owner resolution and old worker exit and prove the owner-selected state survives exactly once.
- Assert a duplicate-preflight exit can never set Done or submit implementation work.
- Focused duplicate owner/claim tests and make test/check-secrets pass.

Acceptance criteria:
- Owner-resolution success is a generation fence: every older preflight result and exit becomes a no-op except bounded cleanup.
- Direct owner work cannot be marked Done, reopened, or redispatched by the superseded investigator.
- The OOMPAH-710 sequence is deterministic and leaves no hidden provider, phantom claim, or tracker-state regression.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-03 00:05
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-03 00:05
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-03 00:05
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 4
- Tokens: 224.2K in / 1.7K out [226.0K total]
- Cost: $0.0000
- Exit: normal, Duration: 48s
- Log: OOMPAH-711__20260803T000511Z.jsonl
---
author: oompah
created: 2026-08-03 00:07
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-03 00:07
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
