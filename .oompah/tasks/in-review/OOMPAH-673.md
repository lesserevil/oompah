---
id: OOMPAH-673
type: bug
status: In Review
priority: 2
title: Make canonical CLI mismatch recovery unambiguous across upgrades
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-01T02:34:24.348580Z'
updated_at: '2026-08-01T02:49:21.474852Z'
work_branch: null
target_branch: null
review_url: https://github.com/lesserevil/oompah/pull/636
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
oompah.agent_run_id: 88a64ded-7a4c-4184-8e43-59b838628a0c
oompah.task_costs:
  total_input_tokens: 760356
  total_output_tokens: 23866
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 760356
      output_tokens: 23866
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 760034
    output_tokens: 3487
    cost_usd: 0.0
    recorded_at: '2026-08-01T02:36:05.989406+00:00'
  - profile: default
    model: haiku
    input_tokens: 322
    output_tokens: 20379
    cost_usd: 0.0
    recorded_at: '2026-08-01T02:42:27.974665+00:00'
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
  - run_id: OOMPAH-673__20260801T023626Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: event_api
    source_branch: OOMPAH-673
    source_sha: b792568ef85d4b46a2e5607305a3dc3549a95860
    completed_at: '2026-08-01T02:42:27.978985+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-673
  base_branch: main
  base_sha: aceb82319369f1082307d6fc0a2931da03fab608
  head_sha: b792568ef85d4b46a2e5607305a3dc3549a95860
  submitted_at: '2026-08-01T02:42:07.028732+00:00'
  updated_at: '2026-08-01T02:42:33.407583+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/636
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
author: oompah
created: 2026-08-01 02:36
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-01 02:36
---
Focus: Event Api Redaction Specialist
---
author: oompah
created: 2026-08-01 02:37
---
**Understanding**: This issue describes a recovery trap when: service is at revision A, canonical CLI launcher does not match A, and checkout is advanced to B. Current problem: make install-cli from B creates launcher B while service A remains, preventing graceful cutover. Current recovery requires temporary remote branches and manual workarounds. Need to implement one of two solutions: (1) Recovery operation that pairs launcher with running revision without temp refs, or (2) Normal cutover safely accepts and repairs this pre-cutover state. Must add tests for A/mismatched-launcher/B scenario, documented operator sequence, failure rollbacks, concurrent locking, and proof of no final mismatch.

**Initial Approach**: Investigating the lifecycle management code (canonical_cli_cutover.py, sync_canonical_cli.py), API endpoints used (/api/v1/state, /healthz), and existing validation logic to determine best solution. Will then implement with full test coverage per requirements.
---
author: oompah
created: 2026-08-01 02:38
---
**Discovery**: The problem occurs in canonical_cli_cutover.py::graceful_cutover() which validates CLI matches running service. When launcher is advanced to B but service remains at A, the validation rejects with message 'repair it with make install-cli', but running make install-cli from B checkout reinstalls launcher B, not A. The fix: add recovery mode to sync_canonical_cli.py that accepts --running-revision parameter to install a specific revision without requiring git checkout to be at that revision. Then modify canonical_cli_cutover.py to detect this mismatch, extract running service revision from API (/healthz, /api/v1/state), and automatically repair the launcher before proceeding with normal cutover. This avoids temp remote refs and keeps recovery bounded.
---
author: oompah
created: 2026-08-01 02:42
---
**Implementation Complete**: Built automatic CLI/server mismatch recovery for the common operational trap where launcher has been advanced to revision B but service remains at A.

**Changes:**
1. Modified sync_canonical_cli.py: Added --running-revision parameter allowing CLI installation from specific revision without git checkout requirement. Enables recovery mode that pairs launcher with verified running service revision.

2. Modified canonical_cli_cutover.py: Added pre-cutover detection of launcher/service mismatch. When detected, automatically calls sync_canonical_cli with running service revision extracted from /healthz and /api/v1/state APIs. Recovery is bounded and transparent to normal cutover flow.

3. Updated docs/cli-install.md: Added 'CLI/server mismatch recovery' section documenting automatic repair behavior and operator guidance.

4. Added comprehensive tests (test_cli_mismatch_recovery.py): 7 new tests covering A service + mismatched launcher + B checkout scenario, automatic detection and repair, failure cases, lifecycle locking preserved, and proof of no final mismatch.

**Test Results:** 50/50 tests pass
- 18 canonical CLI sync tests: PASS
- 25 lifecycle integration tests: PASS  
- 7 new recovery tests: PASS

**Verification:** All requirements met:
✓ Bounded recovery (uses verified running service revision)
✓ No temporary remote branches required
✓ No manual tool-root surgery required
✓ Atomic launcher activation preserved
✓ Lifecycle locking preserved
✓ Fail-closed for unknown/unparseable revisions
✓ Comprehensive deterministic test coverage
✓ Documentation updated with recovery behavior

Branch pushed to OOMPAH-673. Ready for integration tests and review.
---
author: oompah
created: 2026-08-01 02:42
---
Implemented automatic CLI/server mismatch recovery during graceful cutover. Added --running-revision parameter to sync_canonical_cli.py for recovery mode installation. Modified canonical_cli_cutover.py to detect mismatch and auto-repair from running service revision via API. Bounded recovery with no temporary branches required. 50 tests pass including 7 new recovery scenario tests. Documentation updated.
---
author: oompah
created: 2026-08-01 02:42
---
Agent completed successfully in 368s (20701 tokens)
---
author: oompah
created: 2026-08-01 02:42
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 89, Tool calls: 41
- Tokens: 322 in / 20.4K out [20.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 6m 8s
- Log: OOMPAH-673__20260801T023626Z.jsonl
---
author: oompah
created: 2026-08-01 02:49
---
Branch quality gate passed for `b792568ef85d4b46a2e5607305a3dc3549a95860` using `make test` in 386.0s. Review creation may proceed.
---
<!-- COMMENTS:END -->
