---
id: OOMPAH-592
type: feature
status: Done
priority: 1
title: Alert on terminal-audit launch failures and backlog age
parent: OOMPAH-585
children: []
blocked_by:
- OOMPAH-589
- OOMPAH-590
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T14:14:28.755226Z'
updated_at: '2026-08-03T20:03:13.911865Z'
work_branch: epic-OOMPAH-585--task-OOMPAH-592
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: e63ac8087f03fa3d8e428789060b5e66d27092edde9c2b197433ace96b4cd4ac
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-30T14:47:44.845272+00:00'
  matched_identifiers: []
  evidence: 'Focus handoff: duplicate_detector


    Duplicate preflight verdict: no_duplicate


    Matches: none


    Evidence: Reviewed active OOMPAH-590 (retry mechanics), OOMPAH-591 (backlog reconciliation),
    OOMPAH-460 (broader UI/observability epic), and OOMPAH-599 (final invariant verification).
    None owns the specific durable alerting and recovery-clear behavior described
    by OOMPAH-592.'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 05fdcabe-8554-4489-b773-2a19f3e1c2c3
oompah.work_branch: epic-OOMPAH-585--task-OOMPAH-592
oompah.integration:
  version: 1
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-585--task-OOMPAH-592
  base_branch: epic-OOMPAH-585
  base_sha: 64b9b00c55f34d164d4eca2dd6071887ea5b5bb3
  updated_at: '2026-07-30T18:57:45.619687+00:00'
oompah.task_costs:
  total_input_tokens: 3151215
  total_output_tokens: 33901
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 3151103
      output_tokens: 25005
      cost_usd: 0.0
    sonnet:
      input_tokens: 12
      output_tokens: 546
      cost_usd: 0.0
    unknown:
      input_tokens: 100
      output_tokens: 8350
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 3151103
    output_tokens: 25005
    cost_usd: 0.0
    recorded_at: '2026-07-30T14:47:44.844076+00:00'
  - profile: standard
    model: sonnet
    input_tokens: 12
    output_tokens: 546
    cost_usd: 0.0
    recorded_at: '2026-07-30T15:52:22.322471+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 77
    output_tokens: 3701
    cost_usd: 0.0
    recorded_at: '2026-07-30T19:06:21.163229+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 23
    output_tokens: 4649
    cost_usd: 0.0
    recorded_at: '2026-07-30T23:53:01.385122+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-592__20260730T143353Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: epic-OOMPAH-585--task-OOMPAH-592
    source_sha: 12f63352ba017c6ffe88b0ca730bf3f7f973304e
    completed_at: '2026-07-30T14:47:44.853900+00:00'
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-2b3803f5ac37: '2026-07-30T19:06:01.255993+00:00'
    attempt-04adcc5ea409: '2026-07-30T23:52:36.211664+00:00'
  oompah.terminal_override_records:
  - version: 1
    override_id: override-5b95b98161b0
    project_id: proj-14849f1b
    task_id: OOMPAH-592
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 61c2cbc2a3efc33f8ca52ebffdcfe569c9bac1815e4009c6b41047dedb4a051d
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Owner reconciliation: parent OOMPAH-585 is Merged and its accepted rollup
      contains this previously audited Done child; durable integration-queue/rollup
      evidence survives branch pruning. OOMPAH-699 tracks automatic convergence.'
    created_at: '2026-08-02T18:24:32.370125+00:00'
    applied: true
    lifecycle_reconciled: true
    reconciled_to: Done
    retired_reason: shared_epic_parent_not_landed
    reconciled_at: '2026-08-03T20:03:11.626769+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-592
    target_state: Merged
    evidence_fingerprint: 61c2cbc2a3efc33f8ca52ebffdcfe569c9bac1815e4009c6b41047dedb4a051d
    audit_ids:
    - audit-9506c6289586
    - audit-b1aef56b01c8
    kind: override
    applied: false
    retired_at: '2026-08-02T18:24:39.461380+00:00'
    lifecycle_reconciled: true
    reconciled_to: Done
    retired_reason: shared_epic_parent_not_landed
  oompah.terminal_audit_result_intents: []
  oompah.lifecycle_reconciliations:
  - project_id: proj-14849f1b
    task_id: OOMPAH-592
    from: Merged
    to: Done
    reason: shared_epic_parent_not_landed
    conflict: 'Cannot transition shared-epic child OOMPAH-592 to Merged: parent epic
      OOMPAH-585 could not be verified. The parent review must land on its configured
      target branch first.'
    done_audit_ids:
    - audit-b1aef56b01c8
    created_at: '2026-08-03T20:03:11.626769+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-9506c6289586
    project_id: proj-14849f1b
    task_id: OOMPAH-592
    target_state: Done
    request_state: superseded
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 1e272a702875fe9c92b2aace58f742ab97637388b06a06859bae94947230b85d
    attempts:
    - version: 1
      attempt_id: attempt-2b3803f5ac37
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 1e272a702875fe9c92b2aace58f742ab97637388b06a06859bae94947230b85d
      created_at: '2026-07-30T18:57:42.401889+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-07-30T18:57:42.401889+00:00'
      branch_key: epic-OOMPAH-585--task-OOMPAH-592
      verdict: pass
      completed_at: '2026-07-30T19:06:01.255747+00:00'
      ended_at: '2026-07-30T19:06:01.255747+00:00'
    requested_by:
      version: 1
      identity: oompah-integration
      source: service
    previous_state: Ready to Integrate
    created_at: '2026-07-30T18:56:57.602107+00:00'
    updated_at: '2026-07-30T19:06:01.255747+00:00'
  - version: 1
    audit_id: audit-b1aef56b01c8
    project_id: proj-14849f1b
    task_id: OOMPAH-592
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 7cd854b0950d689b3e9fee4500fcbb6ef4dc1f6779fb4cebe28f84bd495efae3
    attempts:
    - version: 1
      attempt_id: attempt-04adcc5ea409
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 7cd854b0950d689b3e9fee4500fcbb6ef4dc1f6779fb4cebe28f84bd495efae3
      created_at: '2026-07-30T23:51:02.406057+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-07-30T23:51:02.406057+00:00'
      branch_key: epic-OOMPAH-585--task-OOMPAH-592
      verdict: pass
      completed_at: '2026-07-30T23:52:36.211519+00:00'
      ended_at: '2026-07-30T23:52:36.211519+00:00'
    requested_by:
      version: 1
      identity: api-client
      source: api
    previous_state: Needs Human
    created_at: '2026-07-30T23:50:21.503390+00:00'
    updated_at: '2026-07-30T23:52:36.211519+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-2b3803f5ac37
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 1e272a702875fe9c92b2aace58f742ab97637388b06a06859bae94947230b85d
    created_at: '2026-07-30T18:57:42.401889+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-07-30T18:57:42.401889+00:00'
    branch_key: epic-OOMPAH-585--task-OOMPAH-592
  - version: 1
    attempt_id: attempt-04adcc5ea409
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 7cd854b0950d689b3e9fee4500fcbb6ef4dc1f6779fb4cebe28f84bd495efae3
    created_at: '2026-07-30T23:51:02.406057+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-07-30T23:51:02.406057+00:00'
    branch_key: epic-OOMPAH-585--task-OOMPAH-592
---
## Summary

Implementation scope

Extend terminal-audit health so the operator alert surface includes auditor launch/transport failure counts, oldest pending age, retry exhaustion, and stale In Validation records. Keep the existing enforcement/quarantine signal distinct but aggregate them into truthful project/service health. Alerts must clear only after underlying recovery and must not expose provider secrets or model output. Relevant files include terminal audit health/metrics, oompah/server.py state and alerts APIs, and dashboard rendering.

Tests

Cover empty backlog, fresh normal queue, aged backlog, repeated launch failures, exhausted candidates, successful recovery/clear, restart persistence, and redaction. Run focused API/dashboard tests and make test.

Acceptance criteria

A state with failed auditor launches or materially stale pending audits cannot show an empty healthy alert list; recovered normal operation clears the alert deterministically.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 14:18
---
Project-owner-approved green recovery work; dispatch under recorded dependencies and acceptance criteria.
---
author: oompah
created: 2026-07-30 14:33
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-30 14:33
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-30 14:47
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 2, Tool calls: 92
- Tokens: 3.2M in / 25.0K out [3.2M total]
- Cost: $0.0000
- Exit: normal, Duration: 14m 0s
- Log: OOMPAH-592__20260730T143353Z.jsonl
---
author: oompah
created: 2026-07-30 15:04
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-30 15:04
---
Focus: Frontend Developer
---
author: oompah
created: 2026-07-30 15:25
---
Agent failed: RuntimeError: Codex exec exited with code 1: 2026-07-30T15:14:54.440078Z ERROR codex_core::tools::router: error=apply_patch verification failed: Failed to find expected lines in /home/shedwards/.oompah/worktrees/oompah/OOMPAH-592/oompah/orchestrator.py:
        self._alerts: list[
            dict[str, str]
        ] = []  # {"level": "warning", "message": "..."}
. Retrying in 10s (attempt #1)
---
author: oompah
created: 2026-07-30 15:25
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 63
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 20m 15s
- Log: OOMPAH-592__20260730T150921Z.jsonl
---
author: oompah
created: 2026-07-30 15:25
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-30 15:25
---
Focus: Frontend Developer
---
author: oompah
created: 2026-07-30 15:34
---
Understanding: Previous agents implemented most of the structure in .pyc form but failed to commit. I found: (1) terminal_audit_health.py with AuditHealthObservation, TerminalAuditHealth, build_terminal_audit_health, terminal_audit_health_alerts; (2) orchestrator changes adding _refresh_terminal_audit_health(), _audit_health field, extending _audit_metrics; (3) dashboard UI changes adding terminal-audit-health banner; (4) tests in test_terminal_audit_health.py, test_terminal_audit_health_api.py, test_dashboard_terminal_audit_health.py. Plan: Reconstruct all these files from .pyc decompilation data, write clean implementations, run tests, commit and push.
---
author: oompah
created: 2026-07-30 15:48
---
Discovery & Implementation: Previous agent had written most code but failed to commit due to a patch verification error. Reconstructed from .pyc files. Implemented: (1) oompah/terminal_audit_health.py - new module with AuditHealthObservation, TerminalAuditHealth dataclasses, build_terminal_audit_health() function, terminal_audit_health_alerts() function; (2) oompah/config.py - new audit_stale_pending_seconds config field (default 3600s); (3) oompah/orchestrator.py - new _refresh_terminal_audit_health() method, extended _audit_metrics with launch_failure/transport_failure/retry_exhausted/stale_in_validation counters, _dispatch_audit_lane() now collects AuditHealthObservation per In Validation issue and calls refresh, get_snapshot() includes terminal_audit_health and health.status fields; (4) oompah/templates/dashboard.html - new #terminal-audit-health banner (accessible, hidden by default), renderTerminalAuditHealth() JS function using only safe numeric facts.
---
author: oompah
created: 2026-07-30 15:51
---
Verification: all 50 new tests pass.

Ran focused test suite:
  python -m pytest tests/test_terminal_audit_health.py tests/test_terminal_audit_health_api.py tests/test_dashboard_terminal_audit_health.py -v
  Result: 50 passed in 1.06s

Coverage:
- test_terminal_audit_health.py (32 tests): empty backlog, fresh queue, aged backlog, stale validation (distinct alerts), launch/transport failure counts, retry exhaustion, successful recovery/clear, restart persistence (to_dict/from_dict roundtrip), redaction (no provider secrets or reason text in alert messages), quarantine, alert prefix namespace
- test_terminal_audit_health_api.py (2 tests): snapshot shape with degraded=True on launch failures; graceful handling of missing _audit_health
- test_dashboard_terminal_audit_health.py (16 tests): banner hidden by default, aria attributes (role=status, aria-live=polite, aria-label), detail element presence, renderTerminalAuditHealth uses all numeric fields, banner.hidden toggling, handleStateUpdate reads state.terminal_audit_health, null guard

Acceptance criteria met:
- A state with failed auditor launches or materially stale pending audits cannot show an empty healthy alert list ✓
- Recovered normal operation clears the alert deterministically ✓
---
author: oompah
created: 2026-07-30 15:51
---
Completion: OOMPAH-592 Alert on terminal-audit launch failures and backlog age — delivered.

Files changed:
- oompah/terminal_audit_health.py (NEW): AuditHealthObservation, TerminalAuditHealth, build_terminal_audit_health, terminal_audit_health_alerts. Six alert types: launch_failures (error), retry_exhausted (error), backlog_age (warning), stale_validation (warning), scan (warning), metadata_quarantine (error). Redaction enforced — failure reasons classified by phrase matching, never included in alert text.
- oompah/orchestrator.py: _refresh_terminal_audit_health() method, observation collection in _dispatch_audit_lane, terminal_audit_health/health exposed in get_snapshot
- oompah/config.py: audit_stale_pending_seconds field + OOMPAH_AUDIT_STALE_PENDING_SECONDS env var (default 3600)
- oompah/templates/dashboard.html: accessible #terminal-audit-health banner (role=status, aria-live=polite, renderTerminalAuditHealth JS)
- tests/test_terminal_audit_health.py (32 tests)
- tests/test_terminal_audit_health_api.py (2 tests)
- tests/test_dashboard_terminal_audit_health.py (16 tests)

Commit: 7d0b36307 on epic-OOMPAH-585--task-OOMPAH-592
---
author: oompah
created: 2026-07-30 15:51
---
Add terminal-audit health alert surface: launch/transport failure counts, oldest pending age, retry exhaustion, stale In Validation records. New terminal_audit_health.py module + orchestrator integration + accessible dashboard banner + 50 tests. All acceptance criteria met.
---
author: oompah
created: 2026-07-30 15:52
---
Run #2 [attempt=2, profile=standard, role=standard -> Claude/sonnet]
- Turns: 0, Tool calls: 149
- Tokens: 12 in / 546 out [558 total]
- Cost: $0.0000
- Exit: terminated, Duration: 26m 52s
- Log: OOMPAH-592__20260730T152536Z.jsonl
---
author: oompah
created: 2026-07-30 18:56
---
Queued for terminal transition to Done. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-07-30 18:57
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-07-30 18:57
---
Focus: Completion Auditor
---
author: oompah
created: 2026-07-30 19:06
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- commit: 64b9b00c55f34d164d4eca2dd6071887ea5b5bb3
- branch: epic-OOMPAH-585--task-OOMPAH-592
- branch_up_to_date: true
- new_module: oompah/terminal_audit_health.py
- orchestrator_integration: oompah/orchestrator.py:1419 _refresh_terminal_audit_health; 4580 dispatch call site; 25387 snapshot terminal_audit_health + health.status
- config_field: audit_stale_pending_seconds default 3600 with OOMPAH_AUDIT_STALE_PENDING_SECONDS env var and positive validation
- dashboard_banner: oompah/templates/dashboard.html:2103 accessible banner (role=status, aria-live=polite, hidden by default); 2490 renderTerminalAuditHealth using only numeric fields; 2571 handleStateUpdate integration
- alert_types: launch_failures, retry_exhausted, backlog_age, stale_validation, scan, metadata_quarantine (prefix terminal_audit_health:)
- redaction_mechanism: failure classification via phrase matching against LAUNCH_PHRASES/TRANSPORT_PHRASES; raw reason strings never included in alert titles or details
- focused_tests_new: 50 passed in tests/test_terminal_audit_health.py, tests/test_terminal_audit_health_api.py, tests/test_dashboard_terminal_audit_health.py
- focused_tests_neighboring: 155 passed in terminal_audit + terminal_audit_enforcement + terminal_audit_scanner + terminal_audit_metadata + terminal_transition_coordinator; 362 passed in orchestrator_handlers + config; dashboard refresh + state read warnings pass
- acceptance_criterion_1: Verified: terminal_audit_health_alerts() returns non-empty list whenever any degraded counter is non-zero; scan_complete=false preserves prior alerts.
- acceptance_criterion_2: Verified: on a complete scan, prior terminal_audit_health: alerts are filtered and replaced from durable numeric facts; empty backlog yields zero alerts.
---
author: oompah
created: 2026-07-30 19:06
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 0, Tool calls: 61
- Tokens: 77 in / 3.7K out [3.8K total]
- Cost: $0.0000
- Exit: terminated, Duration: 8m 38s
- Log: OOMPAH-592__20260730T185845Z.jsonl
---
author: oompah
created: 2026-07-30 23:32
---
The parent epic OOMPAH-585 merged from epic-OOMPAH-585, but this task was Done with work branch epic-OOMPAH-585--task-OOMPAH-592. Its work is not proven to be in the merged epic. Git evidence: OOMPAH-592 branch epic-OOMPAH-585--task-OOMPAH-592 has 3 unlanded commit(s), including cc261493377c. Inspect the task's agent history and remote branches, recover any missing commits through a new recovery epic or approved follow-up PR, then move this task to Done only after the recovered work is verified on the target branch.
---
author: oompah
created: 2026-07-30 23:50
---
Operator revalidation after OOMPAH-630 diagnosis: origin/epic-OOMPAH-585--task-OOMPAH-592 is a direct ancestor of merged target origin/epic-OOMPAH-584 at c45e47bb3. The prior Needs Human transition was caused by a stale remote-tracking target ref, not missing work. Requesting a fresh audited Done transition.
---
author: oompah
created: 2026-07-30 23:51
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-07-30 23:51
---
Focus: Completion Auditor
---
author: oompah
created: 2026-07-30 23:51
---
The parent epic OOMPAH-585 merged from epic-OOMPAH-585, but this task was In Validation with work branch epic-OOMPAH-585--task-OOMPAH-592. Its work is not proven to be in the merged epic. Inspect the task's agent history and remote branches, recover any missing commits through a new recovery epic or approved follow-up PR, then move this task to Done only after the recovered work is verified on the target branch.
---
author: oompah
created: 2026-07-30 23:52
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- commit: 64b9b00c55f34d164d4eca2dd6071887ea5b5bb3
- branch: epic-OOMPAH-585--task-OOMPAH-592
- branch_up_to_date_with_origin: true
- landed_in_merged_target: origin/epic-OOMPAH-584 contains 64b9b00c (verified via git branch -r --contains)
- landed_in_parent_epic: origin/epic-OOMPAH-585 contains 64b9b00c
- stale_ref_diagnosis_resolved: OOMPAH-630 fixed the stale target-ref rollup race; operator revalidation confirms branch is ancestor of merged target c45e47bb3
- prior_alleged_unlanded_commit: cc261493377c is also contained in origin/epic-OOMPAH-584 and origin/epic-OOMPAH-585
- new_module: oompah/terminal_audit_health.py (16291 bytes)
- config_field: audit_stale_pending_seconds default 3600 with OOMPAH_AUDIT_STALE_PENDING_SECONDS env var
- dashboard_banner: oompah/templates/dashboard.html #terminal-audit-health banner: role=status, aria-live=polite, hidden by default; renderTerminalAuditHealth uses only numeric fields
- alert_types: launch_failures, retry_exhausted, backlog_age, stale_validation, scan, metadata_quarantine (prefix terminal_audit_health:)
- redaction_mechanism: phrase-matched classification via LAUNCH_PHRASES/TRANSPORT_PHRASES; raw reason strings excluded from alert titles/details
- focused_tests: 50 passed in tests/test_terminal_audit_health.py, tests/test_terminal_audit_health_api.py, tests/test_dashboard_terminal_audit_health.py
- acceptance_criterion_1: Verified: terminal_audit_health_alerts() returns non-empty when any degraded counter is non-zero; scan_complete=false preserves prior alerts
- acceptance_criterion_2: Verified: on a complete scan, prior terminal_audit_health: alerts are replaced from durable numeric facts; empty backlog yields zero alerts
---
author: oompah
created: 2026-07-30 23:53
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 0, Tool calls: 17
- Tokens: 23 in / 4.6K out [4.7K total]
- Cost: $0.0000
- Exit: terminated, Duration: 1m 51s
- Log: OOMPAH-592__20260730T235115Z.jsonl
---
author: oompah
created: 2026-08-02 18:24
---
Override by oompah-cli: terminal transition to Merged applied by project owner.

Reason: Owner reconciliation: parent OOMPAH-585 is Merged and its accepted rollup contains this previously audited Done child; durable integration-queue/rollup evidence survives branch pruning. OOMPAH-699 tracks automatic convergence.
---
author: oompah
created: 2026-08-03 20:03
---
Lifecycle reconciliation restored OOMPAH-592 to audited Done: Cannot transition shared-epic child OOMPAH-592 to Merged: parent epic OOMPAH-585 could not be verified. The parent review must land on its configured target branch first.
---
<!-- COMMENTS:END -->
