---
id: OOMPAH-738
type: task
status: In Progress
priority: null
title: Fence terminal override cleanup from concurrent worker-map mutation
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-03T20:08:56.082557Z'
updated_at: '2026-08-03T21:22:10.720614Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 70243d630f540010251b43840969051a50b72a2fd2361e3c2c8cdde27635bcfe
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-03T21:07:13.102332+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: No active duplicate appears in the supplied corpus. Closest\
    \ tasks OOMPAH-156 and OOMPAH-161 are terminal and address unrelated error-task\
    \ deduplication and project lookup failures.\nFocus handoff: duplicate_detector\
    \  \nDuplicate preflight verdict: no_duplicate  \nMatches: none  \n\nEvidence:\
    \ No active duplicate appears in the supplied corpus. Closest tasks OOMPAH-156\
    \ and OOMPAH-161 are terminal and address unrelated error-task deduplication and\
    \ project lookup failures."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: bd106330-9432-4f7c-9cca-f997772cf4dd
oompah.task_costs:
  total_input_tokens: 46940
  total_output_tokens: 298
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 46940
      output_tokens: 298
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 46940
    output_tokens: 298
    cost_usd: 0.0
    recorded_at: '2026-08-03T21:07:13.095059+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-738__20260803T210359Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-738
    source_sha: 576a85bfccedf903b9be03adb1088f1c69227c68
    completed_at: '2026-08-03T21:07:13.120323+00:00'
---
## Summary

Live race reproduced on 2026-08-03 while overriding EXOCOMP-159 after deploying OOMPAH-729. The PATCH/terminal override correctly committed EXOCOMP-159 from In Validation to Done and revoked its newly dispatching auditor authority, but concurrent provider exit removed an entry from a shared dictionary while the update path iterated it. The server logged, in order: Running implementation authority generation revoked ... reason=task status changed; Skipping revoked implementation worker before provider setup; Quarantined revoked implementation worker after provider exit; then Update issue API error: RuntimeError('dictionary changed size during iteration'). The CLI received HTTP 500 even though a fresh task view proved the terminal mutation had committed. A caller can therefore retry a successful non-idempotent owner action because the response falsely reports failure.\n\nImplementation scope:\n- Identify every update/terminal-override cleanup loop that traverses running workers, auditors, managed processes, authority maps, or audit chains while provider-exit callbacks can mutate them.\n- Snapshot or lock the iteration under the existing authority boundary; never await or call provider cleanup while holding a mutable-dictionary iterator.\n- Make post-commit cleanup idempotent and ordered so a concurrent worker exit cannot change the authoritative terminal outcome.\n- If cleanup fails after the tracker/audit commit, return the committed result with explicit cleanup diagnostics rather than an ambiguous 500; preserve fail-closed behavior before commit.\n- Ensure retries observe and return the same terminal decision without creating duplicate override records, comments, audit retirement, or worker termination.\n\nRelevant code: PATCH /api/v1/issues/{identifier} update path in oompah/server.py, owner terminal override/coordinator finalization, orchestrator authority revocation and running-worker quarantine/provider-exit callbacks, and audit scheduler retirement.\n\nRequired tests:\n- Deterministically pause an auditor between dispatch registration and provider setup, commit an owner override, and concurrently remove/quarantine that run; no dictionary-size exception and one successful response.\n- Cover provider exit during iteration, already-retired auditor, multiple sibling audits, implementation worker versus audit worker, and task status change callbacks.\n- Inject a post-commit cleanup exception and prove the API reports the committed terminal state with actionable diagnostics; inject a pre-commit exception and prove no state change.\n- Retry the exact request and prove idempotent override metadata/comments and no duplicate termination.\n- Run focused terminal override, audit scheduler, agent lifecycle, server update API, and concurrency suites plus make test.\n\nAcceptance criteria:\n- Concurrent authority revocation/provider exit cannot produce 'dictionary changed size during iteration'.\n- A client never receives an ambiguous failure after the requested terminal state has committed.\n- Terminal authority, fingerprint fencing, worker retirement, and audit history remain exact and race-safe.\n\nTriggered by: EXOCOMP-159; related to OOMPAH-729 and OOMPAH-734.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-03 21:02
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-03 21:02
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-03 21:07
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 46.9K in / 298 out [47.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 4m 28s
- Log: OOMPAH-738__20260803T210359Z.jsonl
---
author: oompah
created: 2026-08-03 21:20
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-03 21:20
---
Focus: Maintenance Engineer
---
author: oompah
created: 2026-08-03 21:22
---
Understanding: I will trace the PATCH terminal-override commit and all worker/auditor/provider-exit cleanup loops, identify the shared-map mutation boundary, then add a minimal snapshot/locking fix with regression tests for post-commit diagnostics and retry idempotency.
---
<!-- COMMENTS:END -->
