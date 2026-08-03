---
id: OOMPAH-711
type: bug
status: In Progress
priority: null
title: Fence owner duplicate resolution from superseded preflight exit
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-02T23:59:03.600915Z'
updated_at: '2026-08-03T00:08:06.415548Z'
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
  verdict: no_duplicate
  checked_at: '2026-08-03T00:07:31.533727+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\n\nDuplicate preflight verdict: no_duplicate\n\
    \nMatches: none\n\nEvidence: OOMPAH-711 describes a specific race condition involving\
    \ fence generation for owner duplicate resolution and superseded preflight worker\
    \ exit. The issue is triggered by OOMPAH-710 and regresses OOMPAH-682 and OOMPAH-535\
    \ (not in the current corpus).\n\nThe key unique elements are:\n1. Generation-based\
    \ fencing for duplicate claims to make owner resolution atomic\n2. Cancellation/awaiting\
    \ of active matching preflight workers before resolution succeeds\n3. State validation\
    \ (fingerprint, generation, claim identity, status) before any duplicate-preflight\
    \ exit transitions\n4. Prevention of Done inference from duplicate-investigator\
    \ exit\n5. Persistence of owner-selected state across restart/auto-update\n6.\
    \ Specific race condition between owner resolution endpoint and superseded preflight\
    \ worker exit\n\nReviewed the task corpus (OOMPAH-1 through OOMPAH-175) with focus\
    \ on:\n- Duplicate screening/investigation (OOMPAH-156: deduplicating auto-filed\
    \ error tasks \u2014 different scope, covers fingerprint dedup, not claim generation)\n\
    - Orchestrator/worker lifecycle (OOMPAH-158-175: various workflow and release-addendum\
    \ work \u2014 no owner-resolution fencing)\n- Dashboard/UI/intake (OOMPAH-10-15:\
    \ integration and validation \u2014 not related to preflight worker exit handling)\n\
    \nNo active task in the corpus addresses owner-resolution claim generation, preflight\
    \ worker fence validation, or the specific OOMPAH-710 sequence described. This\
    \ is a new bug fix for a latent race condition in the duplicate-screening subsystem."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 1
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: fda8afd8-3c4f-4aa5-9649-7dd729875339
oompah.task_costs:
  total_input_tokens: 224251
  total_output_tokens: 2986
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 224251
      output_tokens: 2986
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 224241
    output_tokens: 1710
    cost_usd: 0.0
    recorded_at: '2026-08-03T00:05:55.473586+00:00'
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1276
    cost_usd: 0.0
    recorded_at: '2026-08-03T00:07:31.532815+00:00'
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
  - run_id: OOMPAH-711__20260803T000710Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-711
    source_sha: 93513d742b8abd45b6df2abf3683666787e24a42
    completed_at: '2026-08-03T00:07:31.538915+00:00'
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
author: oompah
created: 2026-08-03 00:07
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.3K out [1.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 25s
- Log: OOMPAH-711__20260803T000710Z.jsonl
---
author: oompah
created: 2026-08-03 00:07
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-03 00:07
---
Focus: Maintenance Engineer
---
author: oompah
created: 2026-08-03 00:08
---
Understanding: owner resolution must fence the exact duplicate-preflight generation; matching workers must be cancelled/awaited or tombstoned before success, and late results/exits may only do bounded cleanup after validating generation, claim, fingerprint, and status. I will trace owner resolution, claim/exit, and restart paths, add race-focused regressions, then verify and submit.
---
<!-- COMMENTS:END -->
