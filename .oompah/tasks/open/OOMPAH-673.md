---
id: OOMPAH-673
type: bug
status: Open
priority: 2
title: Make canonical CLI mismatch recovery unambiguous across upgrades
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-01T02:34:24.348580Z'
updated_at: '2026-08-01T02:36:10.722674Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 6c063c0ee4af6e852f42b593bd42f90fa12c1aac379cb9da31e2685cd7dca129
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-01T02:36:05.990407+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\n\nDuplicate preflight verdict: no_duplicate\n\
    \nMatches: none\n\nEvidence: Searched `.oompah/tasks`, `docs/`, and `plans/` for\
    \ canonical CLI, launcher, revision mismatch, install, restart, and cutover terms.\
    \ Active tasks OOMPAH-281 and OOMPAH-282 are unrelated. Closest reviewed terminal\
    \ tasks\u2014OOMPAH-26 (CLI compatibility documentation) and OOMPAH-52 (stale\
    \ CLI reinstall guidance)\u2014do not address live service/launcher pairing recovery."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: c07d8fba-3989-414e-8dc4-8c25fd3deb7a
oompah.task_costs:
  total_input_tokens: 760034
  total_output_tokens: 3487
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 760034
      output_tokens: 3487
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 760034
    output_tokens: 3487
    cost_usd: 0.0
    recorded_at: '2026-08-01T02:36:05.989406+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-673__20260801T023441Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-673
    source_sha: aceb82319369f1082307d6fc0a2931da03fab608
    completed_at: '2026-08-01T02:36:05.994734+00:00'
---
## Summary

Triggered by: OOMPAH-672

Reproduce the safe-restart recovery trap when the running service is revision A, the canonical CLI does not match A, and the clean pushed checkout is advanced to candidate revision B. scripts/canonical_cli_cutover.py tells the operator to run make install-cli, but installing from B makes the launcher B while service A remains live, so make graceful rejects the same mismatch and cannot stage the normal A-to-B cutover. Today recovery required temporarily publishing a tracked A checkout, installing its CLI, restoring the operator venv to B, deleting the temporary branch/worktree, then running make graceful. Implement a supported, bounded recovery that can pair the canonical launcher with the verified running revision without temporary remote refs, or make the normal cutover safely accept and repair this exact pre-cutover state. Update Makefile targets and docs/cli-install.md recovery instructions. Preserve exact build/instance checks, lifecycle ownership, atomic launcher activation, drain semantics, and fail-closed behavior for unknown revisions. Add deterministic tests covering A service + mismatched launcher + B checkout, the documented operator sequence, install/stage failure rollback, concurrent cutover locking, and proof that no live CLI/server mismatch is left. Acceptance: the documented Makefile-backed recovery reaches a healthy B/B pair from this state without force-restart, temporary remote branches, or manual tool-root surgery; focused tests and the complete Makefile gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-01 02:34
---
Accepted follow-up from the OOMPAH-672 production cutover; ready for normal bug dispatch.
---
author: oompah
created: 2026-08-01 02:34
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-01 02:34
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-01 02:36
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 13
- Tokens: 760.0K in / 3.5K out [763.5K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 28s
- Log: OOMPAH-673__20260801T023441Z.jsonl
---
<!-- COMMENTS:END -->
