---
id: OOMPAH-1072
type: bug
status: In Review
priority: 1
title: Aggregate structured terminal-enforcement errors by stable diagnostic class
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T08:11:28.178710Z'
updated_at: '2026-08-11T08:27:02.820516Z'
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
<!-- COMMENTS:END -->
