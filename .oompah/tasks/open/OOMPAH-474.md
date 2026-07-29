---
id: OOMPAH-474
type: feature
status: Open
priority: 1
title: Add the auditor-only structured result submission API and tool
parent: OOMPAH-458
children: []
blocked_by:
- OOMPAH-466
- OOMPAH-469
- OOMPAH-457
labels: []
assignee: null
created_at: '2026-07-28T13:06:14.992374Z'
updated_at: '2026-07-29T01:24:52.513450Z'
work_branch: epic-OOMPAH-458
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 4cddd67c9f2bb5ce97c8ca4fd0e6672095b56fbaa867049566aadf017869676e
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-29T01:24:50.432229+00:00'
  matched_identifiers: []
  evidence: "Based on my comprehensive duplicate investigation of OOMPAH-474 (\"Add\
    \ the auditor-only structured result submission API and tool\"), I have completed\
    \ my search across all task states and documentation.\n\n## Investigation Summary\n\
    \nI searched:\n- **All task states**: .oompah/tasks/open/, backlog/, merged/,\
    \ and archived/ directories\n- **Documentation**: plans/, docs/, README.md, WORKFLOW.md\n\
    - **Source code**: Root and oompah/ directory\n- **Keywords searched**: \n  -\
    \ auditor, audit, auditor-only\n  - result submission, structured result, verdict\n\
    \  - submission-related terms\n  - coordinator/coordinate\n  - Evidence, session\
    \ audit, AuditSession\n\n## Findings\n\n**No existing tasks contain references\
    \ to:**\n- Auditor functionality\n- Result submissions\n- Structured verdicts\n\
    - Result APIs or tools\n- Audit sessions or related concepts\n\n**Blocking tasks\
    \ do not exist:**\n- OOMPAH-466, OOMPAH-469, OOMPAH-457 are not present in the\
    \ tracker\n\n**Epic context:**\n- OOMPAH-458 (the parent epic) is not documented\
    \ in the task tracker\n- This indicates OOMPAH-474 is part of a new feature development\
    \ cycle\n\n## Conclusion\n\nThis is a genuinely new feature with no active duplicates\
    \ in the oompah task system.\n\n---\n\n**Focus handoff: duplicate_detector**\n\
    \n**Duplicate preflight verdict: no_duplicate**\n\n**Matches: none**\n\n**Evidence:**\
    \ Comprehensive search across all task states (open, backlog, merged, archived)\
    \ found zero existing tasks related to auditor functionality, result submissions,\
    \ structured verdicts, audit sessions, or coordinator services. The three blocking\
    \ tasks (OOMPAH-466, OOMPAH-469, OOMPAH-457) do not exist in the tracker, indicating\
    \ OOMPAH-474 is part of a new epic development cycle. No code references to auditor-related\
    \ modules exist in the codebase. This is original work, not a duplicate of any\
    \ prior issue."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 290691d7-1175-437f-9e95-ce12491f8102
oompah.work_branch: epic-OOMPAH-458
oompah.task_costs:
  total_input_tokens: 154
  total_output_tokens: 4468
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 154
      output_tokens: 4468
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 154
    output_tokens: 4468
    cost_usd: 0.0
    recorded_at: '2026-07-29T01:24:50.431578+00:00'
---
## Summary

Implementation scope

Add an internal result endpoint/tool keyed by audit ID and task/project identity. Accept only PASS, FAIL, or NEEDS_HUMAN plus the defined failure enum, concise summary, bounded structured evidence references, and optional questions/instructions. Authenticate the call as the running auditor session, verify that session owns the audit, validate payload size and enums, reject credentials/unsafe fields, and pass the typed result to the coordinator. The tool must not accept an arbitrary status. Make repeated identical submissions idempotent and conflicting submissions reject.

Tests

Cover owner session, wrong session/task/project, expired/stale audit, malformed enum, oversized output, attempted status injection, secret-like fields, duplicate/conflicting submissions, and coordinator failure. Run API/tool tests and make test.

Acceptance criteria

An auditor can submit exactly one safe structured verdict for its assigned audit; it cannot mutate state directly or affect another audit.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 01:23
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-29 01:23
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-29 01:24
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 48, Tool calls: 24
- Tokens: 154 in / 4.5K out [4.6K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 13s
- Log: OOMPAH-474__20260729T012340Z.jsonl
---
<!-- COMMENTS:END -->
