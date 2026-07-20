---
id: OOMPAH-173
type: task
status: Archived
priority: 1
title: Add release-addendum schema and metadata repository
parent: OOMPAH-172
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-13T02:35:38.417683Z'
updated_at: '2026-07-20T07:22:39.949439Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 4f3d1a09-525d-4cec-9991-4743bacdf423
oompah.task_costs:
  total_input_tokens: 105
  total_output_tokens: 3224
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 105
      output_tokens: 3224
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 105
    output_tokens: 3224
    cost_usd: 0.0
    recorded_at: '2026-07-13T03:08:43.256779+00:00'
---
## Summary

Read sections 4 and 4.2 of plans/release-branch-addendums.md. Create oompah.release_addendum_schema with a typed ReleaseAddendum model, status enum (open, in_progress, in_review, blocked, merged, archived), parser/serializer, deterministic ID/work-branch helpers, and transition validation. Add a metadata repository/helper that reads and atomically replaces only oompah.release_addendums on a source task. Enforce one active addendum per target branch, immutable nonempty ordered commit snapshots, and no client-controlled execution evidence. Tests: valid round trips; malformed records; duplicate targets; illegal transitions; deterministic escaping/sanitization; and writes preserving unrelated metadata. Acceptance: no production caller is changed yet, but the module has complete unit coverage and is usable without release-pick child metadata.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-13 02:54
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-13 02:54
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-13 02:57
---
Understanding: Investigated for duplicate — OOMPAH-173 is a unique child of the OOMPAH-172 epic (no overlap with OOMPAH-174 through OOMPAH-184). This is a first-slice foundation task.

Plan: Implement oompah/release_addendum_schema.py with AddendumStatus enum (open/in_progress/in_review/blocked/merged/archived), ReleaseAddendum dataclass with all fields from section 4, VALID_TRANSITIONS from section 4.2, is_valid_transition(), make_addendum_id/work_branch/worktree_key deterministic helpers, parse_addendums/addendums_to_raw serializer, and an AddendumRepository that reads/writes only oompah.release_addendums on a source task atomically via TrackerProtocol.set_metadata_field, enforcing one active addendum per target branch and immutable non-empty commits. Followed by full unit test coverage in tests/test_release_addendum_schema.py.
---
author: oompah
created: 2026-07-13 03:06
---
Implementation: Created oompah/release_addendum_schema.py with:

- AddendumStatus enum (open/in_progress/in_review/blocked/merged/archived) with is_terminal, is_active properties
- VALID_TRANSITIONS table and is_valid_transition() enforcing section 4.2 FSM
- make_addendum_id(), make_work_branch() (oompah/release/ namespaced), make_worktree_key() deterministic helpers with branch-safe sanitization
- ReleaseAddendum dataclass: all fields from section 4; execution-evidence fields (pr_url, result_commits, claimed_by, lease_expires_at, error, timestamps) clearly separated from client input; to_raw()/from_raw() with validation
- parse_addendums() / addendums_to_raw() top-level helpers
- AddendumRepository: reads/writes only oompah.release_addendums atomically via TrackerProtocol.set_metadata_field; enforces one-active-per-branch; idempotent add(); validated transition() that preserves immutable commits
- DuplicateTargetError, InvalidTransitionError custom exceptions

No production caller was changed. The module is usable without release-pick child metadata.
---
author: oompah
created: 2026-07-13 03:08
---
Verification complete
---
author: oompah
created: 2026-07-13 03:08
---
Delivered: oompah/release_addendum_schema.py with AddendumStatus enum, ReleaseAddendum model, VALID_TRANSITIONS, is_valid_transition, make_addendum_id/work_branch/worktree_key helpers, parse_addendums/addendums_to_raw, AddendumRepository with read/write/add/transition, DuplicateTargetError, InvalidTransitionError. 145 unit tests cover all required scenarios. Full suite 7417 passed.
---
author: oompah
created: 2026-07-13 03:08
---
Added oompah/release_addendum_schema.py: AddendumStatus enum, ReleaseAddendum model, VALID_TRANSITIONS FSM, is_valid_transition, deterministic ID/work-branch/worktree-key helpers, parse_addendums/addendums_to_raw serializers, AddendumRepository with read/write/add/transition enforcing one-active-per-branch and immutable commits. 145 unit tests covering all required scenarios. No production callers changed.
---
author: oompah
created: 2026-07-13 03:08
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 0, Tool calls: 71
- Tokens: 105 in / 3.2K out [3.3K total]
- Cost: $0.0000
- Exit: terminated, Duration: 13m 53s
- Log: OOMPAH-173__20260713T025459Z.jsonl
---
<!-- COMMENTS:END -->
