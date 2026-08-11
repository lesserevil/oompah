---
id: OOMPAH-615
type: bug
status: Archived
priority: 1
title: Fence implementation retries when terminal audits take ownership
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T20:22:18.934506Z'
updated_at: '2026-08-11T07:36:52.308698Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 1ffadb7c497f76972b5542efce9941a262600258b9584273d2e08e0924a8c309
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-30T20:24:55.062508+00:00'
  matched_identifiers: []
  evidence: "Based on my investigation of the `.oompah/tasks` directory structure\
    \ and the detailed description provided in the issue header, I need to clarify\
    \ what I've discovered:\n\n**Investigation Results:**\n\n1. **Task Existence**:\
    \ OOMPAH-615 and OOMPAH-591 do not exist as files in `.oompah/tasks/` (open, backlog,\
    \ merged, or archived directories). This suggests they are newly created external\
    \ tasks, likely from GitHub issue intake.\n\n2. **Technical Context Search**:\
    \ I searched for related concepts mentioned in OOMPAH-615's description:\n   -\
    \ \"ownership races\", \"implementation retries\", \"terminal audit dispatch\"\
    , \"auditor dispatch\"\n   - Found extensive auditor-related code in `oompah/auditor_dispatch.py`,\
    \ `oompah/terminal_audit.py`, `oompah/terminal_transition_coordinator.py`, `oompah/orchestrator.py`,\
    \ and `oompah/server.py`\n   - However, found NO existing oompah tasks covering\
    \ retry-auditor ownership race conditions\n\n3. **Relevant Files Confirmed**:\n\
    \   - `oompah/server.py` (8928+ lines with terminal transition handling)\n   -\
    \ `oompah/orchestrator.py` (4400+ lines with auditor dispatch and retry scheduling)\n\
    \   - `oompah/terminal_transition_coordinator.py` (1800+ lines handling terminal\
    \ audits)\n   - `oompah/auditor_dispatch.py` (auditor retry backoff and scheduling)\n\
    \n4. **Duplicate Check Results**:\n   - Searched `.oompah/tasks/` across all states:\
    \ only OOMPAH-281 and OOMPAH-282 exist in open/backlog\n   - 200+ archived tasks\
    \ reviewed - none address ownership races between worker retries and terminal\
    \ audits\n   - No existing active oompah task covers the specific race condition\
    \ described in OOMPAH-615\n\n**Conclusion:**\n\nOOMPAH-615 addresses a novel bug\
    \ (reproduced in OOMPAH-591) involving concurrency races between ordinary worker\
    \ retries and terminal audit dispatch. No existing active oompah task covers the\
    \ same implementation scope. This is a unique, first-of-its-kind bug-fix task.\n\
    \nFocus handoff: duplicate_detector\n\nDuplicate preflight verdict: no_duplicate\n\
    \nMatches: none\n\nEvidence: C"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 6d5fe0c9-a096-4b3c-a8bf-96198cf2d3ca
oompah.task_costs:
  total_input_tokens: 143
  total_output_tokens: 4084
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 122
      output_tokens: 3612
      cost_usd: 0.0
    unknown:
      input_tokens: 21
      output_tokens: 472
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 122
    output_tokens: 3612
    cost_usd: 0.0
    recorded_at: '2026-07-30T20:24:55.061382+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 21
    output_tokens: 472
    cost_usd: 0.0
    recorded_at: '2026-07-31T06:07:29.489078+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-615__20260730T202336Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-615
    source_sha: c048ba706cbe9b1342b80a67576a49b82887e84a
    completed_at: '2026-07-30T20:24:55.071313+00:00'
oompah.integration:
  version: 1
  state: ready
  attempts: 0
  task_branch: OOMPAH-615
  head_sha: ce8a124fc76e1c97e666714503cdb599deb5e6b7
  submitted_at: '2026-07-30T20:45:26.045620+00:00'
  updated_at: '2026-07-30T20:45:26.045620+00:00'
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_override_records:
  - version: 1
    override_id: override-53ce2264ffc6
    project_id: proj-14849f1b
    task_id: OOMPAH-615
    target_state: Archived
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b7e6173482539d849db77203ce8877caf5081f827ed98979628e401dd671dfb2
    authorized_by:
      version: 1
      identity: lesserevil
      source: api
    reason: Archive parentless provenance record superseded by canonical merged child
      OOMPAH-616; prevents duplicate delivery of the same work.
    created_at: '2026-07-31T06:07:18.225250+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-93adc6105c0b
    project_id: proj-14849f1b
    task_id: OOMPAH-615
    target_state: Archived
    request_state: cancelled
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b7e6173482539d849db77203ce8877caf5081f827ed98979628e401dd671dfb2
    attempts:
    - version: 1
      attempt_id: attempt-3e11c1a1d215
      target_state: Archived
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: b7e6173482539d849db77203ce8877caf5081f827ed98979628e401dd671dfb2
      created_at: '2026-07-31T06:06:36.642106+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-07-31T06:06:36.642106+00:00'
      branch_key: OOMPAH-615
    requested_by:
      version: 1
      identity: api-client
      source: api
    previous_state: Ready to Integrate
    created_at: '2026-07-31T06:06:16.514388+00:00'
    updated_at: '2026-08-11T07:36:50.743434+00:00'
    source_generation: 1
  attempt_history:
  - version: 1
    attempt_id: attempt-3e11c1a1d215
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b7e6173482539d849db77203ce8877caf5081f827ed98979628e401dd671dfb2
    created_at: '2026-07-31T06:06:36.642106+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-07-31T06:06:36.642106+00:00'
    branch_key: OOMPAH-615
---
## Summary

Triggered by: OOMPAH-591

Implementation scope: Fix the reproduced ownership races between ordinary worker retries and terminal-audit dispatch. A supported Done request that stages a task in In Validation must request an immediate scheduler refresh. The same transition must atomically invalidate every pending, delayed, or callback-owned implementation retry before auditor ownership becomes visible, and a retry callback must re-read canonical task state immediately before dispatch so it cannot reopen or reclaim In Validation, Done, Merged, Archived, or Needs Human work. Preserve ordinary retry behavior for genuinely In Progress/Open work and keep auditor retry rotation independent. Relevant files include oompah/server.py terminal transition handling, oompah/orchestrator.py retry scheduling/callback and dispatch events, and related state snapshots. Tests: deterministically reproduce (1) terminal audit staged between worker exit and delayed retry callback, (2) callback already awakened while the terminal transition cancels ownership, (3) In Validation staging wakes the audit lane without waiting for the safety-net poll, and (4) normal retries still dispatch. Assert there is never simultaneous implementation/auditor ownership and task state cannot regress from In Validation to In Progress/Open. Run focused server/orchestrator/auditor tests and make test. Acceptance criteria: staged audits wake immediately; terminal transition wins every implementation-retry race; no stale implementation agent can launch after audit staging; live OOMPAH-591 can be requeued and receive exactly one auditor; all tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 20:22
---
Claimed directly by the operator Codex session after live reproduction on OOMPAH-591. I will implement and verify this task locally; do not dispatch a separate implementation agent.
---
author: oompah
created: 2026-07-30 20:23
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-30 20:23
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-30 20:24
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 40, Tool calls: 16
- Tokens: 122 in / 3.6K out [3.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 23s
- Log: OOMPAH-615__20260730T202336Z.jsonl
---
author: oompah
created: 2026-07-30 20:25
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-30 20:25
---
Focus: Software Engineer
---
author: oompah
created: 2026-07-30 20:40
---
Implemented terminal-audit ownership fencing across API staging, retry dispatch, and worker exit. Added per-task serialization so In Progress writes cannot cross audit staging, immediate audit-lane wakeups after ownership cleanup, and fence release after failed/incomplete audits. Focused regression suite: 408 passed.
---
author: oompah
created: 2026-07-30 20:45
---
Fenced terminal-audit ownership against stale implementation retries, serialized audit staging with In Progress tracker writes, suppressed retries after In Validation handoff, woke the audit lane after cleanup, and added deterministic race regressions. Full gate: terminal mutation scan passed; 13,736 passed, 7 skipped.
---
author: oompah
created: 2026-07-30 20:45
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 62
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 20m 35s
- Log: OOMPAH-615__20260730T202515Z.jsonl
---
author: oompah
created: 2026-07-30 20:47
---
This parentless Ready-to-Integrate record cannot enter the project's require-epic-parent delivery path. OOMPAH-616 is the canonical OOMPAH-585 child carrying commit ce8a124fc through integration; keep this record as provenance and do not redispatch it.
---
author: oompah
created: 2026-07-31 06:06
---
Post-restart reconciliation: this parentless record is provenance superseded by canonical shared-epic child OOMPAH-616, which carried the terminal-audit fencing work through the merged recovery epic to main. Archiving the duplicate Ready row as previously instructed; do not redispatch it.
---
author: oompah
created: 2026-07-31 06:06
---
Queued for terminal transition to Archived. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-07-31 06:06
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-07-31 06:06
---
Focus: Completion Auditor
---
author: oompah
created: 2026-07-31 06:07
---
Override by lesserevil: terminal transition to Archived applied by project owner.

Reason: Archive parentless provenance record superseded by canonical merged child OOMPAH-616; prevents duplicate delivery of the same work.
---
author: oompah
created: 2026-07-31 06:07
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 0, Tool calls: 9
- Tokens: 21 in / 472 out [493 total]
- Cost: $0.0000
- Exit: terminated, Duration: 51s
- Log: OOMPAH-615__20260731T060650Z.jsonl
---
<!-- COMMENTS:END -->
