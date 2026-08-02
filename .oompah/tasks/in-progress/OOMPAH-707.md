---
id: OOMPAH-707
type: task
status: In Progress
priority: null
title: Preserve explicit owner work from orphaned-In-Progress reset
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- focus-complete:frontend
assignee: null
created_at: '2026-08-02T22:19:11.796639Z'
updated_at: '2026-08-02T22:43:06.711102Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 7d4d9cd88ad1c84fe1c9d9dcb34803d9be4586a3b35ef419bd3cfa27efa0e822
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-02T22:39:06.357208+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector  \nDuplicate preflight verdict: no_duplicate\
    \  \nMatches: none  \n\nEvidence: No active peer task covers direct-owner claims\
    \ or orphan watchdog resets. Closest reviewed tasks OOMPAH-160, OOMPAH-163, and\
    \ OOMPAH-165 are archived and address different mechanisms."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: b3cd976a-a926-41aa-a7bf-287c22a70670
oompah.task_costs:
  total_input_tokens: 50670
  total_output_tokens: 9264
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 50670
      output_tokens: 9264
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 50340
    output_tokens: 904
    cost_usd: 0.0
    recorded_at: '2026-08-02T22:39:06.355945+00:00'
  - profile: default
    model: haiku
    input_tokens: 330
    output_tokens: 8360
    cost_usd: 0.0
    recorded_at: '2026-08-02T22:42:43.146917+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-707__20260802T223833Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-707
    source_sha: 53b14479d528381299b101f602dae6fae1161df9
    completed_at: '2026-08-02T22:39:06.408255+00:00'
  - run_id: OOMPAH-707__20260802T223942Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: frontend
    source_branch: OOMPAH-707
    source_sha: 53b14479d528381299b101f602dae6fae1161df9
    completed_at: '2026-08-02T22:42:43.151656+00:00'
---
## Summary

Triggered by: OOMPAH-701\n\nProduction evidence on 2026-08-02: the authenticated project owner placed human-only OOMPAH-701 In Progress for direct implementation with an explicit handoff comment and active task worktree, but _reset_orphaned_in_progress changed it back to Open twice because no scheduler RunningEntry was attached. This makes direct owner work look idle and can expose it to conflicting lifecycle automation.\n\nImplementation scope:\n- Represent a durable direct-owner claim/lease, or another explicit ownership fence, that distinguishes intentional owner work from a genuinely orphaned scheduler assignment.\n- Make _reset_orphaned_in_progress preserve a live owner claim while retaining recovery of truly abandoned tasks.\n- Expose the ownership source and staleness/expiry evidence in API/UI state.\n- Define bounded expiry/release behavior so an abandoned owner claim cannot strand work indefinitely.\n\nRelevant code: oompah/orchestrator.py _reset_orphaned_in_progress and watchdog maintenance; task status/assignment APIs; native Markdown tracker metadata; dashboard task/agent ownership state.\n\nRequired tests:\n- Direct owner claim plus human-only and In Progress survives repeated orphan watchdog scans.\n- Expired/explicitly released owner claim is safely reset through the existing recovery path.\n- Scheduler-owned orphan behavior remains unchanged.\n- Owner claim versus watchdog scan is serialized so neither transition can overwrite a newer decision.\n\nAcceptance criteria:\n- Intentional direct owner work remains visibly In Progress without a scheduler agent.\n- Genuine orphan recovery stays bounded and automatic.\n- Focused race tests and make test/check-secrets pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-02 22:37
---
Promoted to Open after confirming the live watchdog reset direct project-owner work twice. The description contains the production evidence, implementation scope, required race tests, and bounded owner-claim acceptance criteria; Oompah may dispatch it normally while the directly owned OOMPAH-701 repair proceeds.
---
author: oompah
created: 2026-08-02 22:38
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-02 22:38
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-02 22:39
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 50.3K in / 904 out [51.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 37s
- Log: OOMPAH-707__20260802T223833Z.jsonl
---
author: oompah
created: 2026-08-02 22:39
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-02 22:39
---
Focus: Frontend Developer
---
author: oompah
created: 2026-08-02 22:40
---
**Understanding**: This task requires implementing an owner-claim mechanism to prevent the orphan watchdog from resetting intentional direct-owner work back to Open. The issue was triggered by OOMPAH-701 where a project owner placed a task In Progress but the watchdog reset it because there was no scheduler agent attached.

The implementation needs:
1. A durable owner-claim/lease representation (probably in OrchestratorState)
2. Logic to preserve In Progress status when a direct owner claim exists
3. Bounded expiry/release so claims don't strand work indefinitely
4. API/UI exposure of the ownership source and staleness evidence
5. Race condition tests to ensure watchdog and owner claims don't conflict

Key code locations identified:
- oompah/orchestrator.py::_reset_orphaned_in_progress (line 15228): main reset logic
- oompah/models.py::OrchestratorState (line 1460): state tracking
- Current check is: if no running_ids, no retry_ids, and no claimed_ids → reset

**Role note**: As Frontend Developer, I'll focus on UI/API exposure and then likely hand off to backend agent for core implementation. First, let me explore the full scope and what needs to surface in the UI.
---
author: oompah
created: 2026-08-02 22:41
---
**Discovery**: Examined codebase structure:

**Current state tracking:**
- OrchestratorState (oompah/models.py:1460) tracks: running (agents), claimed (issued claimed by dispatch), retry_attempts
- _reset_orphaned_in_progress (oompah/orchestrator.py:15228) resets In Progress issues without running/retry/claimed entries
- get_snapshot() (oompah/orchestrator.py:31936) builds API payload with running/retrying lists for dashboard
- Frontend: single component (Dashboard.tsx is empty), dashboard.html is server-rendered HTML template

**What needs to happen:**
1. **Backend (core)**: Add OwnerClaim data structure, persist claims, modify watchdog to preserve them
2. **Frontend (exposure)**: Add owner claim fields to API snapshot, display in dashboard

This is primarily a backend task with frontend UI exposure. As Frontend Developer, I should hand off the core implementation to backend and then handle UI exposure, OR hand off entirely if you need the core done first.
---
author: oompah
created: 2026-08-02 22:42
---
HANDOFF: Frontend Developer assessment complete.

**Analysis Summary:**
This issue requires implementing a durable owner-claim/lease system to prevent the orphan watchdog from resetting intentional direct-owner work. The implementation is primarily backend infrastructure:

**Backend work (blocking UI work):**
1. Add OwnerClaim data structure to OrchestratorState (oompah/models.py:1460)
   - Track: owner name, claim timestamp, expiry time, claim_id
   - Implement bounded expiry (e.g., 24-48 hours default, renewable)
   - Serialize state for persistence
   
2. Modify orchestrator.py _reset_orphaned_in_progress (line 15228)
   - Check if issue has live owner claim before resetting
   - Preserve In Progress status if owner claim exists
   - Handle claim expiry gracefully
   
3. Create API endpoints for owner claims
   - Set claim (when owner marks task In Progress)
   - Get/validate claim (check staleness)
   - Release claim (manual or expiry-based)
   
4. Race condition safety
   - Add mutex/lock serialization between watchdog scan and claim operations
   - Ensure neither can overwrite newer decision
   
5. Tests (as specified in acceptance criteria)
   - Owner claim + In Progress survives repeated scans
   - Expired claim is reset through recovery path
   - Scheduler orphan behavior unchanged
   - Race conditions handled correctly

**Frontend work (depends on backend):**
Once backend is ready, UI needs to:
1. Add owner_claim fields to API snapshot (get_snapshot returning owner name, staleness, expiry)
2. Display in dashboard: show owner name + last-claimed timestamp on In Progress tasks with owner claims
3. Optional: UI controls to set/release claims manually

**Recommended next focus:** Backend specialist to implement the core OwnerClaim infrastructure and orchestrator changes.
---
author: oompah
created: 2026-08-02 22:42
---
Operator direction: proceed autonomously. This is primarily a backend/state-machine change; use the supported peer coordination or handoff path to get backend implementation ownership, then retain or resume frontend/API exposure work as appropriate. Do not wait for a human choice, and do not implement unrelated backend scope merely because the initial focus was Frontend Developer.
---
author: oompah
created: 2026-08-02 22:42
---
**Focus handoff: frontend - COMPLETE**

**Outcome:**
After investigating the codebase, determined that OOMPAH-707 is primarily a backend infrastructure task that requires changes to the orchestrator's state management, watchdog logic, and API before UI work can begin.

**Key findings:**
- No existing owner claim system in OrchestratorState
- Watchdog (_reset_orphaned_in_progress) has no knowledge of direct owner intent
- API snapshot (get_snapshot) doesn't track owner claims yet
- Dashboard is server-rendered HTML with no owner claim display

**Remaining work:**
- Backend agent needs to implement: OwnerClaim data structure, persistence, orchestrator logic, API endpoints, race-safe serialization, and comprehensive tests
- Frontend agent can then pick up: adding owner claim fields to API snapshot display in dashboard UI

**Recommended next focus:** Backend specialist (needs:backend)
---
author: oompah
created: 2026-08-02 22:42
---
Agent completed successfully in 194s (8690 tokens)
---
author: oompah
created: 2026-08-02 22:42
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 87, Tool calls: 40
- Tokens: 330 in / 8.4K out [8.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 3m 14s
- Log: OOMPAH-707__20260802T223942Z.jsonl
---
author: oompah
created: 2026-08-02 22:42
---
Focus handoff from `frontend` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-08-02 22:43
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-08-02 22:43
---
Focus: Technical Writer
---
<!-- COMMENTS:END -->
