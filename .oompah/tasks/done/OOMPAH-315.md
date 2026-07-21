---
id: OOMPAH-315
type: bug
status: Done
priority: 2
title: '[backend:orchestrator] Fetch failed for project exocomp: State branch ''oompah/state/proj-c260b117''
  does not exist locally or at origin/''oompah/state/proj-c260b117''. Run the bootstrap
  or migration f...'
parent: null
children: []
blocked_by: []
labels:
- external:github
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-21T18:20:09.334393Z'
updated_at: '2026-07-21T19:01:09.227008Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.external.github:
  id: lesserevil/oompah#470
  owner: lesserevil
  repo: oompah
  number: '470'
  url: https://github.com/lesserevil/oompah/issues/470
  requestor_login: lesserevil
  imported_comment_ids: []
  last_synced_status: In Progress
  last_synced_at: '2026-07-21T18:55:46.791053+00:00'
oompah.intake:
  missing_fields: []
  scope: small
  requestor_approved: false
  requestor_approved_at: null
  requestor_actor: null
  owner_override: false
  owner_override_at: null
  owner_actor: null
  decomposition_status: not_needed
  proposal_fingerprint: null
  last_validator_result: pass
  last_validated_at: '2026-07-21T18:20:20.176791+00:00'
oompah.agent_run_id: ed592296-d191-440b-92c2-c9ace493d0af
oompah.task_costs:
  total_input_tokens: 40
  total_output_tokens: 11789
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 40
      output_tokens: 11789
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 40
    output_tokens: 11789
    cost_usd: 0.0
    recorded_at: '2026-07-21T18:49:58.872531+00:00'
---
## Summary

### Problem

Oompah detected a backend error (error class: `tracker_failed`) from `backend:orchestrator`:

> Fetch failed for project exocomp: State branch 'oompah/state/proj-c260b117' does not exist locally or at origin/'oompah/state/proj-c260b117'. Run the bootstrap or migration flow to create it before enabling state_branch_enabled=True for this project. Normal tracker reads must not create remote branches.

### Desired Behavior

The operation in `backend:orchestrator` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Steps to Reproduce

1. Run oompah with `backend:orchestrator` active.
2. Let oompah execute the operation that involves `backend:orchestrator` (tracker: `github_issues:lesserevil/oompah`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior

An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Fetch failed for project exocomp: State branch 'oompah/state/proj-c260b117' does not exist locally or at origin/'oompah/state/proj-c260b117'. Run the bootstrap or migration flow to create it before enabling state_branch_enabled=True for this project. Normal tracker reads must not create remote branches.

### Acceptance Criteria

- The error from `backend:orchestrator` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: global
- tracker: github_issues:lesserevil/oompah
- tracker_kind: github_issues
- fingerprint: 4dba66ecb4abddff
- dedup_fingerprint: 4dba66ecb4abddff
- tracker_owner: lesserevil
- tracker_repo: oompah
- error_class: tracker_failed

## External GitHub Issue

- URL: https://github.com/lesserevil/oompah/issues/470
- Requestor: @lesserevil
- Reference: lesserevil/oompah#470

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-21 18:44
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-21 18:44
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-21 18:45
---
Understanding: Investigating OOMPAH-315 as Duplicate Investigator. The error is about project 'exocomp' (proj-c260b117) having state_branch_enabled=True but the state branch 'oompah/state/proj-c260b117' doesn't exist locally or at origin. This triggers a tracker_failed error caught by error_watcher. My plan: search for similar existing tasks about state branch missing errors, state_branch_enabled misconfiguration, or the same proj-c260b117 project to determine if this is a duplicate.
---
author: oompah
created: 2026-07-21 18:49
---
Discovery: Duplicate screening complete. OOMPAH-315 is NOT a duplicate.

Key findings:
1. **Same fingerprint as OOMPAH-6 (archived)** — both have dedup_fingerprint 4dba66ecb4abddff, but this is because ALL tracker_failed errors share one fingerprint (computed as sha256('class=tracker_failed')[:16] in error_watcher.py). OOMPAH-6 was about a GitHub API auth failure for the OVA project; that's a completely different root cause. Not a duplicate.
2. **OOMPAH-282 (backlog)** — closest in topic (state branch migration failure), but covers proj-edbc8b4c with a UnicodeEncodeError during Stage A migration. Different project, different error. Not a duplicate.
3. **OOMPAH-253 epic + children (OOMPAH-254 through OOMPAH-260, all merged)** — implemented the state branch feature. OOMPAH-256 specifically added the intentional TrackerError when the state branch doesn't exist ('Normal reads must not auto-create the state branch'). But none of these tasks addressed what should happen when error_watcher picks up this expected configuration error and auto-files it.

Root cause identified: Project exocomp (proj-c260b117) is in the system with state_branch_enabled=True, but its state branch 'oompah/state/proj-c260b117' does not exist locally or at origin. The TrackerError raised in oompah_md_tracker.py:1312 propagates through the orchestrator as tracker_failed, triggering error_watcher to auto-file this task repeatedly.

Relevant files:
- oompah/oompah_md_tracker.py:1280-1315 (where the TrackerError is raised)
- oompah/orchestrator.py:151-173 (_error_class_for_tracker_exc — classifies as tracker_failed)
- oompah/error_watcher.py:508-540 (fingerprinting — all tracker_failed share same hash)
- oompah/server.py:10662 (state_branch_enabled=True set during migration Stage A)

The fix options are: (a) run the bootstrap/migration for exocomp to create its state branch, OR (b) add a distinct error class for 'missing state branch' to prevent error_watcher from auto-filing it, OR (c) suppress the error in the orchestrator when it's a known configuration state. A devops or backend agent should assess which is appropriate.
---
author: oompah
created: 2026-07-21 18:49
---
Focus handoff: duplicate_detector

1. **Outcome**: No duplicate confirmed. OOMPAH-315 is a unique issue distinct from OOMPAH-6 (auth failure, archived), OOMPAH-282 (UnicodeEncodeError in migration, different project), and the OOMPAH-253 state-branch epic (which implemented the feature but didn't handle the error_watcher auto-filing scenario).

2. **Relevant files and evidence**:
   - oompah/oompah_md_tracker.py:1280-1315 — TrackerError raised when state branch is missing (intentional by design from OOMPAH-256)
   - oompah/orchestrator.py:151-173 — _error_class_for_tracker_exc classifies all TrackerError as 'tracker_failed'
   - oompah/error_watcher.py:508-540 — all tracker_failed errors share fingerprint 4dba66ecb4abddff (sha256 of 'class=tracker_failed')
   - Project exocomp (proj-c260b117) is live in the server but its state branch oompah/state/proj-c260b117 does not exist
   - oompah/server.py:10662 — state_branch_enabled=True is set atomically during successful Stage A migration

3. **Remaining work**: Determine the correct fix: (a) run bootstrap/migration for exocomp to create its state branch, (b) add a distinct error subclass (e.g., TrackerStateBranchMissingError) so error_watcher can deduplicate or suppress it separately, or (c) detect and handle the missing-state-branch condition in the orchestrator before it triggers error_watcher. Note: OOMPAH-282 has a related migration failure (UnicodeEncodeError on Stage A for proj-edbc8b4c) which may need to be resolved before exocomp's migration can proceed if exocomp uses the same migration path.

4. **Recommended next focus**: backend (to evaluate which fix option applies and implement the code change needed)
---
author: oompah
created: 2026-07-21 18:49
---
Agent completed successfully in 301s (11829 tokens)
---
author: oompah
created: 2026-07-21 18:50
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 82, Tool calls: 57
- Tokens: 40 in / 11.8K out [11.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 5m 1s
- Log: OOMPAH-315__20260721T184459Z.jsonl
---
author: oompah
created: 2026-07-21 18:50
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-21 18:51
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-21 18:51
---
Focus: Software Engineer
---
author: oompah
created: 2026-07-21 18:53
---
Understanding: Working as Software Engineer on OOMPAH-315.

Root cause (confirmed from duplicate investigator): project exocomp (proj-c260b117) has state_branch_enabled=True but its state branch 'oompah/state/proj-c260b117' does not exist. Every fetch attempt raises a generic TrackerError in oompah_md_tracker.py:1312, which is classified as 'tracker_failed' in orchestrator.py, triggering error_watcher to auto-file this task.

Fix plan (option b from prior investigation):
1. Add TrackerStateBranchMissingError(TrackerError) subclass to tracker.py
2. Raise TrackerStateBranchMissingError instead of TrackerError when state branch is missing in oompah_md_tracker.py
3. In orchestrator.py, catch TrackerStateBranchMissingError BEFORE the generic TrackerError catch — log a warning (not an error with error_class), so error_watcher is not triggered
4. Add tests in test_oompah_md_tracker_state_branch.py and test_error_watcher_orchestrator.py

Rationale: treating the missing-state-branch condition like TrackerNotConfiguredError (configuration issue requiring operator action, not a transient error) keeps the diagnostic message visible in logs while preventing repetitive auto-filing of tasks.
---
author: oompah
created: 2026-07-21 18:55
---
Discovery: Code changes complete.

Changes made:
1. oompah/tracker.py: Added TrackerStateBranchMissingError(TrackerError) subclass with docstring explaining it's a config/setup issue that doesn't trigger error_watcher
2. oompah/oompah_md_tracker.py: Imported TrackerStateBranchMissingError and raised it (instead of generic TrackerError) when the state branch is missing in _get_state_root()
3. oompah/orchestrator.py: (a) Imported TrackerStateBranchMissingError, (b) Added it to _error_class_for_tracker_exc returning 'tracker_state_branch_missing', (c) Added explicit catch for TrackerStateBranchMissingError in all 4 fetch sites — logs WARNING (no error_class), so error_watcher is NOT triggered

Key insight: The existing test test_missing_state_branch_raises_actionable_error checks for TrackerError which TrackerStateBranchMissingError still is (subclass), so it passes unchanged. The orchestrator now treats missing-state-branch like a configuration issue (warning) rather than a transient error (error + error_class), preventing auto-filing.
---
author: oompah
created: 2026-07-21 19:00
---
Implementation: 5 files changed.

**oompah/tracker.py** — added TrackerStateBranchMissingError(TrackerError) subclass. Docstring explains it is a configuration/setup problem, not a transient failure, and that the orchestrator catches it separately to avoid error_watcher auto-filing.

**oompah/oompah_md_tracker.py** — imported TrackerStateBranchMissingError; changed _get_state_root() to raise TrackerStateBranchMissingError instead of generic TrackerError when the state branch is missing locally and at origin.

**oompah/orchestrator.py** — three changes:
1. Imported TrackerStateBranchMissingError
2. _error_class_for_tracker_exc: added case returning 'tracker_state_branch_missing' (must be tested before generic TrackerError case, after all other specific subtypes)
3. All 4 fetch sites (_fetch_candidates_from_all_projects coro, _fetch_legacy_candidates, _fetch_in_progress_issues coro, _fetch_legacy_in_progress): added explicit catch for TrackerStateBranchMissingError BEFORE the generic (TrackerError, ProjectError) catch. Logs WARNING (no error_class in extra= dict) so error_watcher is NOT triggered.

**tests/test_oompah_md_tracker_state_branch.py** — 2 new tests in TestStateBranchTrackerFailures:
- test_missing_state_branch_raises_tracker_state_branch_missing_error: verifies the specific subclass is raised
- test_tracker_state_branch_missing_error_is_tracker_error_subclass: verifies backward compat

**tests/test_error_watcher_orchestrator.py** — 3 new tests in TestErrorClassForTrackerExc:
- test_tracker_state_branch_missing_error_returns_distinct_class: class = 'tracker_state_branch_missing'
- test_tracker_state_branch_missing_error_not_classified_as_tracker_failed
- test_tracker_state_branch_missing_error_is_tracker_error_subclass

**tests/test_error_watcher.py** — 1 new test in TestErrorClassForTrackerExc verifying the new classification.
---
author: oompah
created: 2026-07-21 19:00
---
Verification: All tests pass.

Full test suite: 9957 passed, 36 skipped, 13 warnings (196.80s)
Targeted test run (new tests + modified test classes): 20/20 passed (1.54s)

No regressions. The 5 new tests all pass:
- TrackerStateBranchMissingError is raised (not generic TrackerError) when state branch missing
- TrackerStateBranchMissingError is a subclass of TrackerError (backward compat)
- _error_class_for_tracker_exc returns 'tracker_state_branch_missing' for the new subclass
- The new class is distinct from 'tracker_failed'
- Generic TrackerError still returns 'tracker_failed' (no regression)
---
author: oompah
created: 2026-07-21 19:01
---
Completion: OOMPAH-315 resolved.

Root cause: project exocomp (proj-c260b117) has state_branch_enabled=True but its state branch oompah/state/proj-c260b117 does not exist. Every fetch raised a generic TrackerError, classified as 'tracker_failed', triggering error_watcher to auto-file tasks.

Fix delivered:
- New TrackerStateBranchMissingError subclass of TrackerError in tracker.py
- oompah_md_tracker.py raises this specific exception (not generic TrackerError) for missing state branch
- orchestrator.py catches it as a WARNING (no error_class) in all 4 fetch sites, so error_watcher is NOT triggered
- Distinct error class 'tracker_state_branch_missing' in _error_class_for_tracker_exc for proper dedup if needed
- 6 new tests (all passing): TrackerStateBranchMissingError class hierarchy + orchestrator classification

Note: the underlying configuration issue (project exocomp needs bootstrap/migration to create its state branch) is separate. This fix prevents repeated noise; the operator warning log message tells them what action to take.
---
<!-- COMMENTS:END -->
