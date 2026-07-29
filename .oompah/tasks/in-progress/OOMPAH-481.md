---
id: OOMPAH-481
type: feature
status: In Progress
priority: 1
title: Route automatic archive and intake retirement through Archived audits
parent: OOMPAH-459
children: []
blocked_by:
- OOMPAH-464
- OOMPAH-475
- OOMPAH-458
labels: []
assignee: null
created_at: '2026-07-28T13:07:29.211296Z'
updated_at: '2026-07-29T18:30:03.005037Z'
work_branch: epic-OOMPAH-459--task-OOMPAH-481
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 37e03dedf4b09d9f40dde2f20036507fba50ed3ba0fb78907074894f9e017853
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-29T01:59:19.449025+00:00'
  matched_identifiers: []
  evidence: "Based on my comprehensive investigation, I need to provide my duplicate\
    \ screening verdict.\n\n## Investigation Summary\n\nI searched the codebase for\
    \ tasks that might be duplicates of OOMPAH-481:\n\n**Search Scope:**\n- All `.oompah/tasks/`\
    \ states (open, backlog, merged, archived)\n- `plans/` directory (37 plan files\
    \ reviewed)\n- Source code for references to: auto-archive, terminal audit, disposition,\
    \ retention, safe retirement, intake retirement, error-task cleanup, external\
    \ issue close\n- Git references for OOMPAH-464, OOMPAH-475, OOMPAH-458 (blockers)\n\
    \n**Key Findings:**\n\n1. **Terminal Audit System**: Already implemented in the\
    \ codebase\n   - `oompah/terminal_audit.py` \u2014 audit record structures\n \
    \  - `oompah/terminal_transition_coordinator.py` \u2014 coordinator\n   - `oompah/terminal_audit_enforcement.py`\
    \ \u2014 auditor\n   - `oompah/terminal_audit_metadata.py` \u2014 metadata storage\n\
    \   - Comprehensive design in `plans/terminal-transition-coordinator.md`\n\n2.\
    \ **Current Auto-Archive**: Exists but bypasses terminal audit system\n   - `oompah/orchestrator.py:21480`\
    \ \u2014 `_auto_archive()` method\n   - Directly archives without audit coordination\n\
    \   - Used for aged Done/Merged items\n\n3. **No Existing Task**: No open, in-progress,\
    \ or recently-merged task covers:\n   - Routing auto-archive maintenance through\
    \ Archived audits\n   - Routing external issue close/archive reconciliation through\
    \ audits\n   - Routing duplicate retirement through audits\n   - Routing error-task\
    \ cleanup through audits\n   - Supply of disposition reason and pre-archive state\n\
    \   - Prevention of repeated requests while audit pending\n   - Unsafe retirement\
    \ with state restoration\n\n4. **Blocker Tasks**: OOMPAH-464, OOMPAH-475, OOMPAH-458\
    \ do not appear in the tracker yet (likely future prerequisites)\n\n---\n\n**Focus\
    \ handoff: duplicate_detector**\n\n**Duplicate preflight verdict: no_duplicate**\n\
    \n**Matches: none**\n\n**Evidence:** OOMPAH-481 is NOT a duplicate. The terminal-transition-coordinator\
    \ system is already implemented (OOMPAH-465, OOMPAH-4"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 66f1310f-3902-4a4f-b83c-0de81a16a8cc
oompah.work_branch: epic-OOMPAH-459--task-OOMPAH-481
oompah.task_costs:
  total_input_tokens: 218
  total_output_tokens: 5606
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 218
      output_tokens: 5606
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 218
    output_tokens: 5606
    cost_usd: 0.0
    recorded_at: '2026-07-29T01:59:19.448217+00:00'
oompah.integration:
  version: 1
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-459--task-OOMPAH-481
  base_branch: epic-OOMPAH-459
  base_sha: 65c8e4725fe931bf0fa9c3357d153ba003ad03c4
  updated_at: '2026-07-29T18:29:58.173928+00:00'
---
## Summary

Implementation scope

Update auto-archive maintenance, external issue close/archive reconciliation, duplicate retirement, error-task cleanup, and other automatic archive_issue/status=Archived calls to request an Archived audit. Supply retention or structured disposition reason and pre-archive state. Do not repeatedly request archive while an audit is pending. On unsafe retirement, restore the recorded prior state or use the coordinator failure classification. Existing archived upgrade records stay grandfathered.

Tests

Cover aged Done/Merged auto-archive, recent item, active review/agent/retry, external issue close, duplicate with source reference, missing disposition evidence, repeated maintenance ticks, failed tracker writes, unsafe restoration, and grandfathered Archived records. Run archive/intake/error-watcher tests and make test.

Acceptance criteria

No automatic path hides unresolved work in Archived; valid retirement remains bounded/idempotent and produces a concise durable audit comment.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 01:57
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-29 01:57
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-29 01:59
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 56, Tool calls: 26
- Tokens: 218 in / 5.6K out [5.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 34s
- Log: OOMPAH-481__20260729T015749Z.jsonl
---
author: oompah
created: 2026-07-29 18:29
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-29 18:30
---
Focus: Maintenance Engineer
---
<!-- COMMENTS:END -->
