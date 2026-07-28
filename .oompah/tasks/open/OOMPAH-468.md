---
id: OOMPAH-468
type: feature
status: Open
priority: 1
title: Persist worker and epic contributor provider-model provenance
parent: OOMPAH-458
children: []
blocked_by:
- OOMPAH-462
- OOMPAH-463
- OOMPAH-457
labels: []
assignee: null
created_at: '2026-07-28T13:06:08.315289Z'
updated_at: '2026-07-28T21:12:08.463819Z'
work_branch: epic-OOMPAH-458
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: d67d60ba-3924-4ac8-80a7-939687ba33b6
oompah.work_branch: epic-OOMPAH-458
oompah.task_costs:
  total_input_tokens: 226
  total_output_tokens: 8041
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 226
      output_tokens: 8041
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 226
    output_tokens: 8041
    cost_usd: 0.0
    recorded_at: '2026-07-28T21:12:04.091442+00:00'
---
## Summary

Implementation scope

At successful worker startup/exit, persist a compact oompah.work_contributors record containing run ID, provider ID, safe provider name, resolved model ID when known, focus, source branch, source SHA, and completion time. Do not store credentials, prompts, logs, or costs. For an epic evidence revision, derive the union of contributors from its own branch work plus all child and nested-child audit/work records whose commits are contained in that revision. Preserve prior contributors when later workers add commits; discard contributors whose commits are not in the audited revision.

Tests

Cover API, ACP SDK-managed unknown model, CLI worker, retries, multiple workers on one task, shared epic children, nested epics, commits excluded from the current SHA, restart rereads, and redaction. Run focused tests and make test.

Acceptance criteria

The audit evidence collector can identify every provider/model that contributed to a task or epic revision, including unknown-model ACP contributors, without relying on transient RunningEntry state.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 21:10
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 21:10
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 21:11
---
**Understanding:** Duplicate investigation starting. OOMPAH-468 is about persisting work_contributors records (run ID, provider ID, safe provider name, resolved model ID, focus, source branch/SHA, completion time) at worker startup/exit, deriving union of contributors from child/nested-child audit records for epic revisions, without storing credentials/prompts/logs/costs. This is distinct from OOMPAH-462/463 which handle terminal-audit records and state transitions. Searching for any prior implementation or duplicate tasks.
---
author: oompah
created: 2026-07-28 21:11
---
**Discovery:** Comprehensive duplicate screening complete. OOMPAH-468 is NOT a duplicate.\n\nSearched scope:\n- All .oompah/tasks directories (open, backlog, merged, archived): 281 task files total\n- Source code (oompah/, src/, tests/): zero matches for work_contributors, WorkContributor, RunningEntry, audit.*work patterns\n- Git history: no prior implementations of provider-model provenance tracking\n- OOMPAH-458 (parent epic) and its 8 children: distinct scopes confirmed\n  - OOMPAH-469 (auditor focus contract) — defines auditor role, not contributor tracking\n  - OOMPAH-470 (auditor candidate selection) — DEPENDS on OOMPAH-468 to exclude contributors\n  - OOMPAH-471 (Done evidence collector) — includes contributor identities as part of evidence\n- Related prior work: OOMPAH-287 (external content provenance) — different domain (trust boundaries, not worker provenance)\n\nScope confirmation: OOMPAH-468 is uniquely focused on persisting work_contributors records at worker startup/exit containing run ID, provider ID, safe provider name, resolved model ID, focus, source branch/SHA, and completion time. This infrastructure is required by OOMPAH-470 and later auditor tasks but does not duplicate any existing implementation.\n\nNo duplicate found. Ready for implementation focus.
---
author: oompah
created: 2026-07-28 21:12
---
Agent completed successfully in 124s (8267 tokens)
---
author: oompah
created: 2026-07-28 21:12
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 103, Tool calls: 47
- Tokens: 226 in / 8.0K out [8.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 4s
- Log: OOMPAH-468__20260728T211004Z.jsonl
---
author: oompah
created: 2026-07-28 21:12
---
Focus handoff required before leaving `duplicate_detector`. Add a comment headed `Focus handoff: duplicate_detector` with outcome, evidence, remaining work, and next focus.
---
<!-- COMMENTS:END -->
