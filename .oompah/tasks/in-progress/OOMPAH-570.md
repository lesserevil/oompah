---
id: OOMPAH-570
type: bug
status: In Progress
priority: 1
title: Recover interrupted integration leases and explicit blocked-head retries
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-29T23:53:31.874608Z'
updated_at: '2026-07-30T00:01:17.856591Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 70211f087949bc92d36b39a24ee18fe20444239fd436a12269a096e08f38a265
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-29T23:58:31.979277+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\n\nDuplicate preflight verdict: no_duplicate\n\
    \nMatches: none\n\nEvidence: Closest reviewed tasks\u2014OOMPAH-177 (release-addendum\
    \ lease recovery), OOMPAH-165 (epic landing detection), and OOMPAH-214/OOMPAH-216\
    \ (release-delivery conflicts and retries)\u2014are all Archived and cover different\
    \ subsystems. Active tasks OOMPAH-281 and OOMPAH-282 are unrelated."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 1
  retry_after: null
oompah.agent_run_id: 2b30c2f1-f99c-49a8-9c98-96e3b2ec536d
oompah.task_costs:
  total_input_tokens: 618966
  total_output_tokens: 10122
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 618966
      output_tokens: 10122
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 162
    output_tokens: 6639
    cost_usd: 0.0
    recorded_at: '2026-07-29T23:55:49.586880+00:00'
  - profile: default
    model: haiku
    input_tokens: 618804
    output_tokens: 3483
    cost_usd: 0.0
    recorded_at: '2026-07-29T23:58:31.978665+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-570__20260729T235353Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-570
    source_sha: 8483db2e3e718c1f5f6476018d954574ce5d42f9
    completed_at: '2026-07-29T23:55:49.595678+00:00'
  - run_id: OOMPAH-570__20260729T235713Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-570
    source_sha: 8483db2e3e718c1f5f6476018d954574ce5d42f9
    completed_at: '2026-07-29T23:58:31.982681+00:00'
---
## Summary

Triggered by: OOMPAH-562

Implementation scope: make durable epic-child integration recover promptly after a service exec/restart interrupts an in-flight quality gate, and make an explicit task submission able to retry a blocked queue row even when task_branch and head_sha are unchanged. Preserve idempotency for periodic Ready-to-Integrate synchronization and for ready/integrating/integrated rows so no automatic retry loop or duplicate integration is introduced. Add an explicit retry flag or equivalent boundary between the submit API path and background queue synchronization. On orchestrator startup, safely identify/requeue abandoned integrating leases; ensure any active branch-quality-gate process group is terminated during shutdown before leases become reclaimable. Relevant files: oompah/integration_queue.py, oompah/orchestrator.py, oompah/quality_gate.py, server submission wiring, and their tests. Tests: reproduce (1) blocked identical explicit resubmit versus background sync, (2) restart with a durable integrating row and rebased private head, (3) shutdown process-tree cleanup, and (4) no duplicate claims/integration. Acceptance criteria: an operator never waits for the hour-long lease after a normal restart, a same-head explicit resubmit clears a blocked row without branch-name workarounds, background sync remains idempotent, and focused plus full Makefile gates pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 23:53
---
Accepted for implementation after live queue recovery exposed the restart-lease and same-head retry gaps.
---
author: oompah
created: 2026-07-29 23:53
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-29 23:53
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-29 23:55
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 67, Tool calls: 40
- Tokens: 162 in / 6.6K out [6.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 58s
- Log: OOMPAH-570__20260729T235353Z.jsonl
---
author: oompah
created: 2026-07-29 23:57
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-29 23:57
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-29 23:58
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 21
- Tokens: 618.8K in / 3.5K out [622.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 21s
- Log: OOMPAH-570__20260729T235713Z.jsonl
---
author: oompah
created: 2026-07-29 23:58
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-29 23:58
---
Focus: Refactoring Specialist
---
author: oompah
created: 2026-07-29 23:59
---
**Understanding:** This is a bug fix for restart-safety and explicit retries in durable integration. Key issues:

1. **Restart lease recovery:** On orchestrator restart, integrating leases remain stuck for ~1 hour (current lease expiration). Need to recover abandoned leases at startup.

2. **Explicit retry vs background sync:** Currently, enqueue() is idempotent for same head+branch. This blocks explicit user resubmits from clearing blocked rows. Need to distinguish explicit retries from background sync.

3. **Process cleanup on shutdown:** quality_gate.py creates subprocesses with start_new_session=True (process groups), but there's no guaranteed cleanup on orchestrator shutdown. Active process groups can prevent leases from becoming reclaimable.

**Planned approach:**
1. Add explicit_retry flag to IntegrationQueueStore.enqueue() to distinguish explicit submissions
2. Implement abandoned integrating lease recovery at orchestrator startup
3. Add graceful shutdown hook in orchestrator to terminate active quality gate process groups
4. Add tests for: blocked explicit resubmit, restart with durable integrating row, shutdown cleanup, no duplicate claims

Will proceed with discovery of server submission wiring next.
---
author: oompah
created: 2026-07-30 00:01
---
**Discovery:** Found the key code patterns:

1. **Two sync paths:** 
   - Background sync at line 4627: Periodically enqueues Ready submissions
   - Retryable recovery at line 4871: Re-enqueues with rebased head_sha on transient failure

2. **Idempotency issue:** Both paths call enqueue() which returns early if (project_id, task_id, head_sha, task_branch) are identical. This blocks explicit retries of blocked rows.

3. **Lease recovery:** orchestrator.py line 5192 calls recover_expired() during processing loop, but only recovers leases with expired timestamps. No startup-time recovery for abandoned integrating rows.

4. **Process cleanup:** quality_gate.py creates subprocesses with start_new_session=True (line 207), but no mechanism to terminate active process groups on orchestrator shutdown. TimeoutExpired handler catches them (line 234) but graceful shutdown has no equivalent.

5. **Server submission wiring:** server.py line 2886 (_enqueue_worker_submission) is the entry point for explicit API submissions.

All existing tests pass (4 integration_queue + 9 quality_gate tests).

Next: Implement explicit_retry flag, startup lease recovery, and shutdown process cleanup.
---
<!-- COMMENTS:END -->
