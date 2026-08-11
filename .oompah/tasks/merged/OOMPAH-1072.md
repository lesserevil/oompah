---
id: OOMPAH-1072
type: bug
status: Merged
priority: 1
title: Aggregate structured terminal-enforcement errors by stable diagnostic class
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T08:11:28.178710Z'
updated_at: '2026-08-11T11:02:31.262951Z'
work_branch: OOMPAH-1072
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/809
review_number: '809'
review_head: 4da80c799a785da5112eec35773025224e6f1d3c
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: oompah-1015-terminal-enforcement-error-class-20260811
  request_fingerprint: 9a96a455c48226019ec01857992ed13ccb8f9c92ac8092a9644b9b38ba3c01ec
oompah.review_url: https://github.com/lesserevil/oompah/pull/809
oompah.review_number: '809'
oompah.work_branch: OOMPAH-1072
oompah.target_branch: main
oompah.review_head: 4da80c799a785da5112eec35773025224e6f1d3c
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-00d5d7755c13
    project_id: proj-14849f1b
    task_id: OOMPAH-1072
    digest: 43f2ef7389581c89fbf3b0d8956fe3787efa5637914147b2245dc54cc1b5aa8c
  - version: 1
    audit_id: audit-078f5a8faba5
    project_id: proj-14849f1b
    task_id: OOMPAH-1072
    digest: 43f2ef7389581c89fbf3b0d8956fe3787efa5637914147b2245dc54cc1b5aa8c
  applied_result_attempts:
    '["proj-14849f1b","OOMPAH-1072","audit-00d5d7755c13","attempt-c5d09f31dc08"]': '2026-08-11T10:43:03.960523+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1072
    target_state: Done
    evidence_fingerprint: 43f2ef7389581c89fbf3b0d8956fe3787efa5637914147b2245dc54cc1b5aa8c
    workflow_revision: null
    selected_ref: origin/OOMPAH-1072
    selected_sha: 4da80c799a785da5112eec35773025224e6f1d3c
    landing_revision: null
    audit_ids:
    - audit-00d5d7755c13
    kind: result
    applied: true
    retired_at: '2026-08-11T10:43:03.960539+00:00'
  - project_id: proj-14849f1b
    task_id: OOMPAH-1072
    target_state: Merged
    evidence_fingerprint: 43f2ef7389581c89fbf3b0d8956fe3787efa5637914147b2245dc54cc1b5aa8c
    workflow_revision: null
    selected_ref: origin/OOMPAH-1072
    selected_sha: 4da80c799a785da5112eec35773025224e6f1d3c
    landing_revision: null
    audit_ids:
    - audit-00d5d7755c13
    - audit-078f5a8faba5
    kind: override
    applied: true
    retired_at: '2026-08-11T11:02:29.645867+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1072
    audit_id: audit-00d5d7755c13
    attempt_id: attempt-c5d09f31dc08
    target_state: Done
    evidence_fingerprint: 43f2ef7389581c89fbf3b0d8956fe3787efa5637914147b2245dc54cc1b5aa8c
    status: In Validation
    audit_ids:
    - audit-00d5d7755c13
    kind: result
    applied: true
    created_at: '2026-08-11T10:43:03.960549+00:00'
    applied_at: '2026-08-11T10:43:11.331644+00:00'
    retired_by_override: true
  oompah.terminal_override_records:
  - version: 1
    override_id: override-6748b960edb0
    project_id: proj-14849f1b
    task_id: OOMPAH-1072
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 43f2ef7389581c89fbf3b0d8956fe3787efa5637914147b2245dc54cc1b5aa8c
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: In-flight finalization workaround. Audit audit-00d5d7755c13 returned PASS
      at exact head 4da80c799a785da5112eec35773025224e6f1d3c with the recorded 171.3s
      make test gate and complete safe evidence, but submitted target_state Done against
      the task requested terminal state Merged; the API accepted it with applied_status
      In Validation and failed to finalize across restart. Apply the original requested
      Merged state while the target-mismatch bug is filed.
    created_at: '2026-08-11T11:02:19.636591+00:00'
    selected_ref: origin/OOMPAH-1072
    selected_sha: 4da80c799a785da5112eec35773025224e6f1d3c
    applied: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-00d5d7755c13
    project_id: proj-14849f1b
    task_id: OOMPAH-1072
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 43f2ef7389581c89fbf3b0d8956fe3787efa5637914147b2245dc54cc1b5aa8c
    attempts:
    - version: 1
      attempt_id: attempt-c5d09f31dc08
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 43f2ef7389581c89fbf3b0d8956fe3787efa5637914147b2245dc54cc1b5aa8c
      created_at: '2026-08-11T10:21:19.770199+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-11T10:21:19.770199+00:00'
      branch_key: OOMPAH-1072
      selected_ref: origin/OOMPAH-1072
      selected_sha: 4da80c799a785da5112eec35773025224e6f1d3c
      verdict: pass
      completed_at: '2026-08-11T10:43:03.960368+00:00'
      ended_at: '2026-08-11T10:43:03.960368+00:00'
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: In Review
    created_at: '2026-08-11T08:56:12.618014+00:00'
    selected_ref: origin/OOMPAH-1072
    selected_sha: 4da80c799a785da5112eec35773025224e6f1d3c
    updated_at: '2026-08-11T10:43:03.960368+00:00'
  - version: 1
    audit_id: audit-078f5a8faba5
    project_id: proj-14849f1b
    task_id: OOMPAH-1072
    target_state: Merged
    request_state: cancelled
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 43f2ef7389581c89fbf3b0d8956fe3787efa5637914147b2245dc54cc1b5aa8c
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: In Review
    created_at: '2026-08-11T08:56:12.618014+00:00'
    selected_ref: origin/OOMPAH-1072
    selected_sha: 4da80c799a785da5112eec35773025224e6f1d3c
    updated_at: '2026-08-11T11:02:29.645831+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-c5d09f31dc08
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 43f2ef7389581c89fbf3b0d8956fe3787efa5637914147b2245dc54cc1b5aa8c
    created_at: '2026-08-11T10:21:19.770199+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-11T10:21:19.770199+00:00'
    branch_key: OOMPAH-1072
    selected_ref: origin/OOMPAH-1072
    selected_sha: 4da80c799a785da5112eec35773025224e6f1d3c
oompah.task_costs:
  total_input_tokens: 226
  total_output_tokens: 8529
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 226
      output_tokens: 8529
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 226
    output_tokens: 8529
    cost_usd: 0.0
    recorded_at: '2026-08-11T10:43:20.946633+00:00'
---
## Summary

Triggered by: OOMPAH-1015

Problem: On 2026-08-11, startup emitted 31 pre_recovery_finalization_metadata_malformed:<project>:<task> and 25 inactive_status_override_records_malformed:<project>:<task> errors, producing OOMPAH-1015..1070. OOMPAH-156 suppresses identical durable fingerprints, but each project/task suffix survives conservative free-form normalization, so every affected task gets a different fingerprint. Broadening generic normalization risks merging unrelated errors. ErrorWatcher already supports explicit error_class, and _TaskLoggingHandler forwards it.

Implementation: In TerminalAuditEnforcement._error, derive the structured diagnostic name from code.partition(":")[0] and log with a namespaced class such as terminal_audit_enforcement.<diagnostic_name>. Preserve the complete original code in self.errors and operator-visible log text, including exception-type detail. Apply this consistently to every _error code so task/project suffix variation aggregates by diagnostic kind while different kinds remain distinct. Reuse ErrorWatcher class fingerprinting, its in-memory window, and OOMPAH-156 persistent nonterminal lookup; do not widen generic free-form fingerprint regexes.

Relevant files: oompah/terminal_audit_enforcement.py, tests/test_terminal_audit_enforcement.py, and tests/test_error_watcher.py. No production change to oompah/error_watcher.py should be necessary.

Required tests and acceptance criteria: same diagnostic prefix with different project/task suffixes emits the same namespaced error_class; different prefixes remain distinct; complete exact codes remain in enforcer.errors and log text with exception types visible; the exact 31+25 startup-shaped batch creates at most two error tasks and bounds tracker lookup/create work by diagnostic-class count; a fresh ErrorWatcher suppresses both classes when matching nonterminal tasks already exist, proving restart durability; unrelated free-form errors remain distinct; focused tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-11 08:26
---
Branch quality gate passed for `4da80c799a785da5112eec35773025224e6f1d3c` using `make test` in 171.3s. Review creation may proceed.
---
author: oompah
created: 2026-08-11 08:56
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-11 10:21
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-11 10:21
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-11 10:43
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- quality_gate: passed at exact head SHA 4da80c799a785da5112eec35773025224e6f1d3c; make test 171.3s
- files_modified[0]: oompah/terminal_audit_enforcement.py
- files_modified[1]: tests/test_error_watcher.py
- files_modified[2]: tests/test_terminal_audit_enforcement.py
- implementation: diagnostic_name = code.partition(':')[0]; logger.error(..., extra={'error_class': 'terminal_audit_enforcement.<diagnostic_name>'})
- diagnostic_extraction: PASS
- namespaced_logging: PASS
- code_preservation: PASS - self.errors and log text
- exception_detail: PASS - type(exc).__name__ included
- same_prefix_aggregation: PASS - test_structured_errors verifies identical error_class
- distinct_prefixes: PASS - different prefixes remain distinct
- startup_burst: PASS - 56 errors create 2 tasks
- restart_durability: PASS - fresh ErrorWatcher suppresses both classes
- free_form_distinct: PASS - unrelated errors separate
- no_errorwatcher_changes: PASS - only terminal_audit_enforcement modified
---
author: oompah
created: 2026-08-11 10:43
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/haiku]
- Turns: 60, Tool calls: 27
- Tokens: 226 in / 8.5K out [8.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 21m 58s
- Log: OOMPAH-1072__20260811T102136Z.jsonl
---
author: oompah
created: 2026-08-11 11:02
---
Override by oompah-cli: terminal transition to Merged applied by project owner.

Reason: In-flight finalization workaround. Audit audit-00d5d7755c13 returned PASS at exact head 4da80c799a785da5112eec35773025224e6f1d3c with the recorded 171.3s make test gate and complete safe evidence, but submitted target_state Done against the task requested terminal state Merged; the API accepted it with applied_status In Validation and failed to finalize across restart. Apply the original requested Merged state while the target-mismatch bug is filed.
---
<!-- COMMENTS:END -->
