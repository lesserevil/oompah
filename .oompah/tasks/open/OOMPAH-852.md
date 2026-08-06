---
id: OOMPAH-852
type: bug
status: Open
priority: 1
title: Protect exact gates from concurrent focused validation commands
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-06T04:51:38.786179Z'
updated_at: '2026-08-06T04:51:49.017748Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Live regression at 2026-08-06T04:52Z: while OOMPAH-821 owned the only validation-resource slot for its authoritative make test, completion auditor OOMPAH-826 ran `python -m pytest tests/test_epic_strategy.py -x -q` as service child PID 3113755 for at least 226 seconds. validation_resources still reported only the OOMPAH-821 exact_gate owner and no auditor waiter because the named single-module pytest command is classified as bounded/light. Earlier OOMPAH-847 single-module commands caused D-state contention and contributed to unrelated five-second exact-gate failures. Implementation scope: distinguish harmless inspection from actual validation, and require every pytest/py.test/unittest invocation plus configured Make/tox/nox/npm/cargo validation target to participate in ValidationResourceLease even when selectors are focused; keep help/version/static inspection outside the lane. Preserve priority so exact gates and terminal auditors cannot starve, and ensure waits begin before process creation with truthful tool_liveness. Relevant files: oompah/validation_resource_lease.py classifiers, api_agent/acp_tools/native guard launch paths, and validation telemetry. Required tests: named and absolute Python single-test/module commands wait behind an exact gate; bounded commands run when capacity is available; help/version and non-test inspection do not lease; API, Claude ACP, Codex native, auditor, worker, cancellation, timeout, and restart paths; a real exact gate plus attempted focused test proves no overlapping test process; make test. Acceptance criteria: while an exact gate owns capacity, no worker or auditor test process exists outside its process tree; all waiters are visible and cancellable; after release they run exactly once; ordinary inspection remains concurrent; no global timeout is raised.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

