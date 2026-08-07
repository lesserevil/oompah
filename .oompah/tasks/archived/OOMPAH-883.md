---
id: OOMPAH-883
type: task
status: Archived
priority: null
title: Break epic-rebase and child-integration ordering deadlocks
parent: null
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-879
labels: []
assignee: null
created_at: '2026-08-07T12:02:23.163009Z'
updated_at: '2026-08-07T21:10:57.499124Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 77f7d0fc4a05d3d41f7a69977b130dcb86eb08bfd126752c7c94d246a02e53ac
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-07T12:09:26.215260+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: OOMPAH-879 is the closest active task, but it addresses\
    \ duplicate rebase authority and concurrent generation fencing. OOMPAH-883 addresses\
    \ ordering deadlocks where child integration waits for an epic rebase that would\
    \ unlock it; these are distinct problems.\nFocus handoff: duplicate_detector \
    \ \nDuplicate preflight verdict: no_duplicate  \nMatches: none  \n\nEvidence:\
    \ OOMPAH-879 is the closest active task, but it addresses duplicate rebase authority\
    \ and concurrent generation fencing. OOMPAH-883 addresses ordering deadlocks where\
    \ child integration waits for an epic rebase that would unlock it; these are distinct\
    \ problems."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: a0c4c3ad-582e-4f8d-a564-dd1b535b6e8c
oompah.task_costs:
  total_input_tokens: 46848
  total_output_tokens: 237
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 46848
      output_tokens: 237
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 46848
    output_tokens: 237
    cost_usd: 0.0
    recorded_at: '2026-08-07T12:09:26.214465+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-883__20260807T120809Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-883
    source_sha: a57b76354493a38e9147c255d9cbd4215e7bbec6
    completed_at: '2026-08-07T12:09:26.224228+00:00'
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-0b568a54c40c
    project_id: proj-14849f1b
    task_id: OOMPAH-883
    target_state: Archived
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: ac451a10c798da9973a01f052752d86e63c4f5ffa0dc9cc69338c9ecb2b85100
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: Duplicate of completed OOMPAH-879; no distinct implementation or revision
      exists.
    created_at: '2026-08-07T21:10:43.258102+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-883
    target_state: Archived
    evidence_fingerprint: ac451a10c798da9973a01f052752d86e63c4f5ffa0dc9cc69338c9ecb2b85100
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-07T21:10:52.246558+00:00'
  oompah.terminal_audit_result_intents: []
  oompah.terminal_provenance_suppression:
    version: 1
    suppressed: true
    authority_generation: 0
    reason: Retain metadata-only Archived duplicate provenance pointing to completed
      OOMPAH-879.
    marked_at: '2026-08-07T21:10:55.927072+00:00'
    updated_at: '2026-08-07T21:10:55.927072+00:00'
    history:
    - kind: mark
      actor:
        version: 1
        identity: oompah-cli
        source: api
      reason: Retain metadata-only Archived duplicate provenance pointing to completed
        OOMPAH-879.
      recorded_at: '2026-08-07T21:10:55.927072+00:00'
      authority_generation: 0
    actor:
      version: 1
      identity: oompah-cli
      source: api
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

Live regression on epic OOMPAH-763 at 2026-08-07: Ready children OOMPAH-863 and OOMPAH-866 had accepted remote heads but eligible_ready_count remained zero because their merged cross-epic prerequisite OOMPAH-845 was not reachable from the stale epic branch. OOMPAH-877, the task that would rebase that epic onto current main and make the prerequisite reachable, was conservatively fenced until those Ready children integrated. This creates a cycle: child integration waits for the rebase, while the rebase waits for child integration. The operator had to revise sequencing manually.

Implementation scope: teach the integration/rebase planner to identify tasks blocked solely because a stale epic has not yet absorbed current main; allow the one exact-generation epic rebase helper to run once other shared-branch mutation is fenced, without waiting for Ready children whose eligibility that rebase unlocks; after the rebase, re-evaluate and integrate those children normally. Preserve accepted child heads, dynamic dependency checks, exact-generation authority, and per-epic serialization. Surface a durable diagnostic when a genuine independent blocker remains rather than silently reporting eligible_ready_count=0.

Relevant code: orchestrator epic staleness/rebase scheduling, _integration_satisfied_dependencies, integration eligibility/maintenance state, and exact-generation rebase authority from OOMPAH-879.

Required tests: reproduce an epic behind main with two Ready children depending on a standalone task merged only on main; prove the rebase helper is eligible and no child is discarded; advance the epic to main and prove both children become normally integrable; cover a genuine unresolved dependency that must still block, concurrent helper fencing, restart recovery, and dynamic arrival of another accepted child.

Acceptance criteria: the scheduler cannot form a wait cycle between an epic rebase and child integrations that the rebase itself unlocks; the system chooses and records a safe ordering automatically; no accepted head or dependency invariant is bypassed; focused integration/rebase tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-07 12:07
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-07 12:08
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-07 12:09
---
Deeper live-code analysis shows this is not an independent planner deadlock. _detect_and_repair_integration_queue_staleness_block already recognizes a Ready child blocked by terminal work reachable from the target, schedules the epic rebase first, and re-evaluates child integration afterward. It fired in this incident by creating OOMPAH-882. The actual defect was that it failed to reuse/fence the already-authorized OOMPAH-877 helper; that exact-generation duplicate filing/admission/push race is OOMPAH-879, now including the O882 recurrence. The operator workaround revised sequencing and safely retained the single rebase. Archive this duplicate rather than implement a second overlapping fix.
---
author: oompah
created: 2026-08-07 12:09
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 46.8K in / 237 out [47.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 32s
- Log: OOMPAH-883__20260807T120809Z.jsonl
---
author: oompah
created: 2026-08-07 21:10
---
Read-only evidence audit confirms this task is a duplicate of completed OOMPAH-879. It has no implementation branch, ref, worktree, submitted head, or PR and requires no distinct code. Closing as Archived duplicate rather than carrying a false non-terminal owner.
---
author: oompah
created: 2026-08-07 21:10
---
Override by oompah-cli: terminal transition to Archived applied by project owner.

Reason: Duplicate of completed OOMPAH-879; no distinct implementation or revision exists.
---
<!-- COMMENTS:END -->
