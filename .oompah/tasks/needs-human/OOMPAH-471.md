---
id: OOMPAH-471
type: feature
status: Needs Human
priority: 1
title: Collect stable evidence for Done completion audits
parent: OOMPAH-458
children: []
blocked_by:
- OOMPAH-462
- OOMPAH-468
- OOMPAH-457
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-28T13:06:12.016068Z'
updated_at: '2026-07-28T22:29:04.296371Z'
work_branch: epic-OOMPAH-458
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: bbf8d5e5edc4870aa540fcedc17ec12f41dd5cf9ba613de0e62272d322e74cdb
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: Duplicate-screening worker exited with reason normal.
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 3
  retry_after: '2026-07-28T22:32:59.347124+00:00'
oompah.agent_run_id: 14344ca7-40d6-4091-82c1-ac528a682390
oompah.work_branch: epic-OOMPAH-458
oompah.task_costs:
  total_input_tokens: 490939
  total_output_tokens: 16977
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 490939
      output_tokens: 16977
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 362
    output_tokens: 9258
    cost_usd: 0.0
    recorded_at: '2026-07-28T22:21:30.987420+00:00'
  - profile: default
    model: haiku
    input_tokens: 490543
    output_tokens: 5586
    cost_usd: 0.0
    recorded_at: '2026-07-28T22:25:21.905751+00:00'
  - profile: default
    model: haiku
    input_tokens: 34
    output_tokens: 2133
    cost_usd: 0.0
    recorded_at: '2026-07-28T22:28:59.346664+00:00'
---
## Summary

Implementation scope

Build a read-only DoneEvidenceCollector. Resolve the correct workspace/worktree, intended work or epic branch, source SHA, base/target branch, requirements text and digest, diff/stat with bounded excerpts, changed files, commit/push status, configured test commands, latest relevant CI/test evidence, comments/handoffs, children, and contributor identities. For tasks, require committed and pushed work on the intended branch plus coverage of the description and acceptance criteria. For epics, include every direct/nested child audit result and prove required child commits are contained in the epic revision. Return typed unavailable/invalid evidence rather than guessing.

Tests

Use Git fixtures for standalone tasks, shared epic children, nested epics, clean and dirty worktrees, unpushed commits, missing branches, changed requirements, test evidence, incomplete children, and bounded/redacted prompt payloads. Run focused tests and make test.

Acceptance criteria

The auditor receives a deterministic stable snapshot sufficient to judge completion; missing or unstable evidence is explicit and cannot be mistaken for a passing case.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 22:18
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-28 22:18
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 22:19
---
**Understanding:** I am conducting a duplicate investigation for OOMPAH-471 (Collect stable evidence for Done completion audits). The task calls for building a read-only DoneEvidenceCollector that gathers evidence for task/epic completion audits including: workspace/worktree info, source SHA, branch info, requirements/digest, diff/stat excerpts, changed files, commit/push status, test commands, CI/test evidence, comments/handoffs, children, and contributor identities. Will search the task graph, plans, and source for existing similar implementations or duplicates.
---
author: oompah
created: 2026-07-28 22:21
---
**Discovery:** Comprehensive duplicate screening complete. OOMPAH-471 is NOT a duplicate.\n\nSearch scope:\n- All .oompah/tasks directories (archived, merged, open, backlog): 281+ task files searched\n- Source code (oompah/, tests/): searched for DoneEvidenceCollector, Collector, evidence collection patterns\n- Plans and docs: terminal-transition-coordinator.md, terminal-transition-coordinator-api.md, WORKFLOW.md, README.md\n- Git history: no prior implementations\n\nFindings:\n- OOMPAH-462 (Merged): Defines terminal-audit records/enums/fingerprints — different scope (audit types, not evidence collection)\n- OOMPAH-463-467 (Merged): Terminal-audit coordinator and enforcement — infrastructure for queueing/applying audits\n- OOMPAH-468 (Done): Persist worker/epic contributor provenance — supplies contributor identities, not evidence collection\n- OOMPAH-469 (Open): Reserved auditor focus/prompt contract — supplies auditor interface, not evidence collection\n- OOMPAH-470 (Open): Auditor role selection and candidate filtering — independent candidate selection, not evidence collection\n- No existing DoneEvidenceCollector, EvidenceCollector, or similar collector classes in codebase\n\nScope confirmation: OOMPAH-471 uniquely builds a read-only DoneEvidenceCollector that gathers task/epic completion evidence (workspace, branch, SHAs, requirements, diff/stat, changed files, commit/push status, test commands, CI evidence, comments, children, contributors). This is required by auditors but not yet implemented.\n\nConclusion: OOMPAH-471 is a unique, original feature task. No duplicate found.
---
author: oompah
created: 2026-07-28 22:21
---
Focus handoff: duplicate_detector\n\n**Outcome:** No duplicate found. OOMPAH-471 is a unique, original feature implementation task.\n\n**Evidence:** Repository-wide searches (281+ .oompah/tasks files, plans/, docs/, source code) found zero existing implementations of DoneEvidenceCollector, evidence collection for task audits, or similar work. OOMPAH-462-468 provide terminal-audit infrastructure (records/fingerprints/coordinator/contributor-persistence) but do not collect audit evidence. OOMPAH-469-470 define auditor focus/role but do not collect evidence. The new DoneEvidenceCollector is required by auditors to gather task/epic completion evidence.\n\n**Remaining work/risks:** Implement read-only DoneEvidenceCollector module that resolves workspace/worktree, branch info, SHAs, requirements/digest, diff/stat with bounded excerpts, changed files, commit/push status, test commands, CI/test evidence, comments/handoffs, children, and contributor identities. For tasks, require committed+pushed work on intended branch covering description/acceptance criteria. For epics, include every direct/nested child audit result and prove child commits are contained in epic revision. Return typed unavailable/invalid evidence. Add git fixtures for standalone tasks, epic children, nested epics, clean/dirty worktrees, unpushed commits, missing branches, changed requirements, test evidence, incomplete children, bounded prompts. Run focused tests and make test.\n\n**Recommended next focus:** feature (backend implementation)
---
author: oompah
created: 2026-07-28 22:21
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 102, Tool calls: 44
- Tokens: 362 in / 9.3K out [9.6K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 42s
- Log: OOMPAH-471__20260728T221851Z.jsonl
---
author: oompah
created: 2026-07-28 22:23
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-28 22:23
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 22:25
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 18
- Tokens: 490.5K in / 5.6K out [496.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 55s
- Log: OOMPAH-471__20260728T222329Z.jsonl
---
author: oompah
created: 2026-07-28 22:28
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-28 22:28
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 22:28
---
Duplicate investigator work confirmed and handoff completed. Previous agent's comprehensive investigation (281+ tasks, source code, plans, git history) conclusively shows OOMPAH-471 is NOT a duplicate—it uniquely implements read-only DoneEvidenceCollector for audit evidence collection. Ready for feature-focused implementation. Added focus-complete:duplicate_detector label to route to next specialist.
---
author: oompah
created: 2026-07-28 22:29
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 10, Tool calls: 3
- Tokens: 34 in / 2.1K out [2.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 34s
- Log: OOMPAH-471__20260728T222827Z.jsonl
---
author: oompah
created: 2026-07-28 22:29
---
Duplicate screening was inconclusive 3 times. Human action required: review the latest duplicate-screening comments, then either identify the active canonical duplicate or confirm that no active duplicate exists and move the task back to Open.
---
<!-- COMMENTS:END -->
