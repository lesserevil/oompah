---
id: OOMPAH-721
type: task
status: In Progress
priority: null
title: Do not escalate completed duplicate preflights as implementation work
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-03T14:39:16.938367Z'
updated_at: '2026-08-03T15:01:38.545554Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 2d9cf1ef6da5b257011f4cfaf6c43cfb8cdd40a0b1fe94a02ee38a3d5a089a4b
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-03T14:43:11.552891+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: No active task in the authoritative corpus covers this\
    \ duplicate-preflight exit/escalation bug. Closest reviewed tasks\u2014OOMPAH-156,\
    \ OOMPAH-168, and OOMPAH-170\u2014are archived and address different behavior.\n\
    Focus handoff: duplicate_detector  \nDuplicate preflight verdict: no_duplicate\
    \  \nMatches: none\n\nEvidence: No active task in the authoritative corpus covers\
    \ this duplicate-preflight exit/escalation bug. Closest reviewed tasks\u2014OOMPAH-156,\
    \ OOMPAH-168, and OOMPAH-170\u2014are archived and address different behavior."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 80074d89-1af4-4932-9513-1c5fc1039e55
oompah.task_costs:
  total_input_tokens: 51836
  total_output_tokens: 1202
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 51836
      output_tokens: 1202
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 50598
    output_tokens: 879
    cost_usd: 0.0
    recorded_at: '2026-08-03T14:43:11.552089+00:00'
  - profile: default
    model: haiku
    input_tokens: 1238
    output_tokens: 323
    cost_usd: 0.0
    recorded_at: '2026-08-03T15:01:34.681167+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-721__20260803T144231Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-721
    source_sha: 99d33e120ffafe28b5790438072bfa9e74f88974
    completed_at: '2026-08-03T14:43:11.558589+00:00'
---
## Summary

Live reproduction (2026-08-03): automatically filed epic-staleness tasks EXOCOMP-240 and EXOCOMP-241 entered In Progress under Focus: Duplicate Investigator. EXOCOMP-241's screening run exited normally without closing the task, but the generic worker-exit path escalated it from standard to deep and relaunched the same Duplicate Investigator instead of recording the screening result and handing the still-active task to the rebase/merge-conflict focus. This regresses the two-stage behavior previously specified by OOMPAH-217 and wastes increasingly expensive agents on implementation work outside the duplicate-screening role.

Implementation scope:
- Route every model-backed duplicate-preflight exit through the dedicated screening completion path before generic retry/escalation logic, including auto-filed maintenance/rebase tasks and providers that return no structured duplicate verdict.
- A non-duplicate/indeterminate normal exit must atomically clear the preflight claim, persist a revision-aware screened result (or bounded retry only within the screening subsystem), return the task to Open, and dispatch a fresh implementation session with the appropriate rebase focus.
- A Duplicate Investigator must never execute the rebase or other implementation, and generic standard-to-deep escalation must never retain duplicate_preflight=true.
- Preserve confirmed-duplicate archival, changed-task fingerprint invalidation, crash retry limits, authority revocation, and concurrency accounting.

Required tests:
- Reproduce EXOCOMP-241: normal preflight exit without closing an auto-filed rebase task, then prove no generic escalation occurs and the next worker is a rebase specialist with duplicate_preflight=false.
- Cover missing/malformed structured verdicts, confirmed duplicates, changed fingerprints, provider failure, restart recovery, and exact running/preflight counters.
- Assert the duplicate prompt cannot perform implementation and task comments clearly distinguish screening from implementation handoff.
- Run focused duplicate-screening/orchestrator/maintenance suites and make test.

Acceptance criteria:
- EXOCOMP-240/241-style tasks cannot loop or escalate under Duplicate Investigator.
- Screening either archives a confirmed duplicate or hands an active task to a new correctly focused implementation agent exactly once.
- No stale preflight claim or duplicate running entry remains after handoff.
## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-03 14:42
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-03 14:42
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-03 14:43
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 50.6K in / 879 out [51.5K total]
- Cost: $0.0000
- Exit: normal, Duration: 46s
- Log: OOMPAH-721__20260803T144231Z.jsonl
---
author: oompah
created: 2026-08-03 14:43
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-03 14:43
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-03 14:44
---
**Understanding & Plan:**

OOMPAH-721 requires fixing duplicate-preflight screening handoff to prevent infinite loops. Currently, when a Duplicate Investigator agent exits normally from screening, the generic escalation logic relaunches the same agent instead of handing off to a rebase specialist.

**Key changes needed:**
1. Route all model-backed duplicate-preflight exits through a dedicated screening completion path
2. On non-duplicate/indeterminate normal exit: atomically clear preflight claim, persist result, return task to Open, dispatch correct focus
3. Ensure Duplicate Investigator never executes implementation work
4. Prevent generic standard-to-deep escalation from retaining duplicate_preflight=true

**Approach:**
- Find worker exit/escalation handling logic
- Identify duplicate screening completion paths
- Implement dedicated preflight completion path
- Add tests for EXOCOMP-241-style scenarios
- Verify no stale preflight claims or duplicate running entries remain

Starting discovery now.
---
author: oompah
created: 2026-08-03 14:51
---
**Discovery: Root Cause Identified**

Found the regression in orchestrator.py:

Current behavior (_finish_duplicate_preflight_sync):
- When screening finishes with NO_DUPLICATE verdict, it:
  1. Completes the screening record ✓
  2. Saves the record ✓
  3. Returns outcome='checked' ✗ (but doesn't hand off)

The problem:
- No handoff comment is posted (focus handoff: duplicate_detector)
- No focus-complete:duplicate_detector label is added
- Task stays in Open but without proper handoff markers
- Next scheduler tick doesn't know to dispatch implementation with correct focus
- Generic escalation logic then takes over instead of dispatching implementation

The fix requires:
1. After NO_DUPLICATE verdict, post handoff comment with verdict block
2. Add focus-complete:duplicate_detector label
3. Immediately dispatch fresh implementation agent with appropriate focus (rebase/general)
4. Ensure duplicate_preflight claim is cleared before implementation dispatch
5. Add tests for EXOCOMP-241-style scenarios (no-dup screen → rebase dispatch, no escalation)

Key files:
- oompah/orchestrator.py: _finish_duplicate_preflight_sync, _handle_duplicate_preflight_exit
- oompah/focus.py: duplicate_detector focus definition
- oompah/duplicate_screening.py: result parsing and record management

Starting implementation now.
---
author: oompah
created: 2026-08-03 15:01
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 0, Tool calls: 70
- Tokens: 1.2K in / 323 out [1.6K total]
- Cost: $0.0000
- Exit: terminated, Duration: 17m 48s
- Log: OOMPAH-721__20260803T144352Z.jsonl
---
<!-- COMMENTS:END -->
