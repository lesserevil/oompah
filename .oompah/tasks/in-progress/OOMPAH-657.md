---
id: OOMPAH-657
type: task
status: In Progress
priority: null
title: Run branch quality gates from immutable exact-head snapshots
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T11:06:15.542774Z'
updated_at: '2026-07-31T11:32:15.093412Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 156eeba91c00cafe17da43dbf88f58a7e3e04e766e328754b828313bb3033357
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-31T11:08:39.612047+00:00'
  matched_identifiers: []
  evidence: "Based on my comprehensive search of the oompah task tracker, I can now\
    \ provide my duplicate investigation verdict.\n\n## Investigation Summary\n\n\
    I searched for existing tasks that might duplicate OOMPAH-657 (\"Run branch quality\
    \ gates from immutable exact-head snapshots\") using multiple approaches:\n\n\
    1. **Keyword searches** across `.oompah/tasks/`:\n   - Quality gate terms: `quality_gate`,\
    \ `gate`, `exact-head`, `immutable`, `snapshot`\n   - Race condition terms: `race`,\
    \ `mutation`, `moving`, `worktree.reassign`, `reopen`\n   - Related domains: `integration`,\
    \ `review`, `orchestration`\n\n2. **Task state search**:\n   - Examined all `open/`\
    \ tasks (1 task - OOMPAH-281, unrelated)\n   - Examined all `backlog/` tasks (1\
    \ task - OOMPAH-282, unrelated)\n   - Noted all `merged/` and `archived/` tasks\
    \ are terminal states and excluded from consideration\n\n3. **Direct dependency\
    \ check**:\n   - OOMPAH-655 referenced in coordination note as dependency \u2014\
    \ **does not exist** in `.oompah/tasks`\n   - OOMPAH-655 is mentioned as the incident\
    \ where the race was reproduced (\"Live race reproduced on OOMPAH-655 at 2026-07-31\
    \ 11:03-11:06 UTC\")\n\n4. **Code validation**:\n   - Confirmed `oompah/quality_gate.py`\
    \ exists (current implementation)\n   - No other quality-gate-related tasks found\
    \ in tracker\n\n## Findings\n\n**No active duplicate task exists.** The only referenced\
    \ related task (OOMPAH-655) is not present in the native oompah task tracker.\
    \ It either:\n- Has not yet been filed as a native task (may be tracked externally)\n\
    - Is the incident report from which OOMPAH-657 is derived\n- Will be filed as\
    \ a separate dependency task\n\n---\n\n**Focus handoff: duplicate_detector**\n\
    \n**Duplicate preflight verdict: no_duplicate**\n\n**Matches: none**\n\n**Evidence:**\
    \ Comprehensive search of `.oompah/tasks` across all non-terminal states (open,\
    \ backlog) found no existing tasks addressing quality gates, immutable snapshots,\
    \ exact-head verification, worktree mutation race conditions, or integration launch\
    \ paths. The sole mentioned d"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: f75cece9-82da-4c80-842b-614d77367f5b
oompah.task_costs:
  total_input_tokens: 186
  total_output_tokens: 5176
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 186
      output_tokens: 5176
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 186
    output_tokens: 5176
    cost_usd: 0.0
    recorded_at: '2026-07-31T11:08:39.611070+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-657__20260731T110710Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-657
    source_sha: 54dd2509c6cbc73aaadbda2a3fdc7cfbb14530eb
    completed_at: '2026-07-31T11:08:39.620340+00:00'
---
## Summary

Live race reproduced on OOMPAH-655 at 2026-07-31 11:03-11:06 UTC: a full gate launched for submitted head 2713e14ea continued in the task's reusable worktree after operator rejection/reopen, while the replacement implementation agent modified oompah/quality_gate.py and tests in that same worktree. Pytest therefore read a moving mixture that did not correspond to the recorded head, yet the result could still be consumed as exact-head evidence. Implementation scope: change the server-owned quality-gate/integration launch path and worktree lifecycle so every gate executes from an immutable snapshot of the recorded commit (dedicated detached worktree, archive, or equivalent), with the checked-out SHA verified before spawn; prevent task worktree reassignment/mutation from affecting an active gate; tie cancellation and process-group cleanup to the exact gate generation; and discard results when task/head/generation is no longer current. Relevant code includes oompah/quality_gate.py, integration/review orchestration, worktree allocation/cleanup, and their tests. Add deterministic barrier tests that start a gate, reopen and edit/reassign the normal task worktree, then prove the gate sees only its recorded head; cover old/new head gates overlapping, cancellation/rejection before completion, stale success never creating a review/integration, exact owned-descendant cleanup, and snapshot cleanup without pruning active evidence. Acceptance: a gate result is cryptographically/topologically attributable to one immutable commit, mutable task worktrees can never change its inputs, stale generations have no state effect, and focused tests plus make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-31 11:07
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-31 11:07
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-31 11:08
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 51, Tool calls: 22
- Tokens: 186 in / 5.2K out [5.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 33s
- Log: OOMPAH-657__20260731T110710Z.jsonl
---
author: oompah
created: 2026-07-31 11:09
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-31 11:09
---
Focus: Refactoring Specialist
---
author: oompah
created: 2026-07-31 11:11
---
Second live OOMPAH-657 reproduction: after OOMPAH-655 was moved from Ready to Integrate back to Open for rejected head b519be788, the stale integration generation launched a new server-owned make test PGID 1239518 in the reusable OOMPAH-655 worktree. Operator verified task status/head/cwd/PGID and terminated only that gate group to prevent rejected work from advancing. Fix must cancel queued/running gate generations on Ready to Integrate to Open/rejection and re-check current tracker status plus exact generation before spawn and before consuming success.
---
author: oompah
created: 2026-07-31 11:11
---
Follow-up: the first guard intentionally sent no signal because the expected full SHA was mistyped; a second guard revalidated the actual full head b519be788276e349d4b39978660d6a9ee92b5cfa, cwd, and PGID, then terminated only PGID 1239518. No provider process or other task was signaled.
---
author: oompah
created: 2026-07-31 11:12
---
Third live reproduction: moving rejected OOMPAH-653 head 59436e50aa0122224ad01746c6b7b8380a52241b from Ready to Integrate back to Open did not cancel its just-launched make test. Operator revalidated cwd/head/PGID and terminated only stale gate PGID 1303079. The tracker transition and gate launch are racing repeatedly across tasks.
---
author: oompah
created: 2026-07-31 11:16
---
Root-cause pointer from the live reproductions: _retire_inactive_integration_rows only treats terminal/In Validation/Needs Human as inactive, so Ready to Integrate to Open leaves ready/integrating rows alive. Cancel whenever the current task no longer exactly matches Ready to Integrate plus the queued IntegrationRecord branch/head/generation, and cancel the matching gate generation. In execute_integration, commit_allowed is checked before preparation and after the gate, so authority withdrawal during snapshot creation/Popen cannot stop the expensive gate; add a cancellation token/tombstone checked before and immediately after spawn and driven by the tracker transition. There is currently a Popen-before-_active_generations registration window where cancel_generation can miss the process, and cancellation during git worktree creation can still launch afterward. Standalone _review_quality_gate_passes likewise runs from a stale Issue object; bind expected head/state to StandaloneDeliveryAuthority and recheck before spawn and before consuming pass. Add barriers for cancellation during snapshot creation and between Popen and registration, not only after the process is in the map.
---
author: oompah
created: 2026-07-31 11:20
---
Current OOMPAH-657 tests cover snapshot input isolation and cancellation only after the process is already registered, but they do not cover the three live failure windows. Add deterministic barriers for (1) task authority revoked during git worktree creation before Popen, (2) revocation after Popen but before _active_generations registration, and (3) Ready to Integrate to Open cancelling/retiring the exact integration row and preventing any stale pass from changing status or creating review/integration. _retire_inactive_integration_rows still excludes Open, so the reproduced root cause is currently unchanged. cancel_generation also needs a durable/tombstoned cancellation state checked before and immediately after spawn; a map lookup cannot close those windows. Verify detached worktree registration/path cleanup, prune _key_locks or bound it with evidence retention, and use the current tracker IntegrationRecord branch/head/generation—not only a stale Issue/ref—to authorize both launch and pass consumption.
---
author: oompah
created: 2026-07-31 11:25
---
Operator stopped only the exact direct python -m pytest process group 1597527. Project instructions require Makefile targets, and the branch still lacks the Ready-to-Open retirement plus pre-registration cancellation barriers, so a repository-wide run is premature. This was not a test failure. Finish the blocking production paths and deterministic focused regressions using an available Make target; run one immutable exact-head full make test only when the branch is clean/frozen and ready.
---
author: oompah
created: 2026-07-31 11:31
---
Fourth live stale-generation reproduction: after clean OOMPAH-653 head 44742bb1f exited and the task was explicitly returned to Open for blocking review defects, the old integration row launched server-owned make test PGID 1747920 in the OOMPAH-653 worktree. Operator verified exact Open status/cwd/head/PGID and terminated only that gate group. The current OOMPAH-657 head still leaves _retire_inactive_integration_rows excluding Open and only polls is_current after Popen registration, so the reproduced root cause remains.
---
author: oompah
created: 2026-07-31 11:32
---
Fifth live reproduction against the current candidate head: exact-head review moved rejected OOMPAH-658 head 7e4375e6f from Ready to Integrate to Open, and the stale row immediately launched server-owned make test PGID 1882247 in that worktree. Operator revalidated Open status/cwd/head/PGID and terminated only that gate group. This is the exact deterministic Ready-to-Open case still absent from 08bc7ebfe; polling is_current after process registration does not retire the row or close pre-spawn races.
---
<!-- COMMENTS:END -->
