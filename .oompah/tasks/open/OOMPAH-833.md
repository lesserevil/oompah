---
id: OOMPAH-833
type: task
status: Open
priority: null
title: Bootstrap durable ACP command-result delivery onto main
parent: null
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-810
labels: []
assignee: null
created_at: '2026-08-05T15:59:15.045452Z'
updated_at: '2026-08-05T23:59:50.982407Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 779fe688ccb7347578c5880808cb71d52c21e909a221be6514cd43f9674d8e09
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 30e4c8b9-4568-4705-83ad-f699acbf8825
  claim_owner: f7278be4-f84b-419e-8352-94d46afbf29e
  claimed_at: '2026-08-05T23:59:22.093909+00:00'
  claim_expires_at: '2026-08-06T00:29:22.093909+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: e4870fae-206f-49e5-9431-fec75aa1fedd
---
## Summary

Triggered by: OOMPAH-810.

OOMPAH-810 is implemented on the systemic OOMPAH-763 branch, but the running main server must execute many expensive worker and auditor gates before that root can land. Live OOMPAH-523 proves the completed-command/result-delivery race affects ordinary implementation workers as well as terminal auditors. After OOMPAH-810 reaches reviewed Done, port the same logical repair patch-equivalently onto then-current main.

Implementation scope:
- Apply only the reviewed ACP run_command completion, bounded result delivery, liveness/result_pending state, exact-once retirement/retry, and observability changes from OOMPAH-810.
- Preserve validation-resource arbitration, command deadlines, cancellation, output redaction/paging, per-session authority, exact worker/audit identity, and current main-only lifecycle fixes.
- Do not pull unrelated durable-workflow epic changes or weaken auditor/task-handoff authority.

Required tests:
- Run the complete OOMPAH-810 focused ACP/tool-liveness/result-output/provider-retirement matrix against the standalone composition.
- Replay both OOMPAH-793 auditor and OOMPAH-523 implementation-worker command-exit races, including child exit concurrent with stall scan, and prove exactly one bounded tool_result or precise delivery-timeout outcome.
- Prove a successful expensive gate is not blindly rerun when durable compatible evidence is safely reusable, while failed/unknown outcomes remain fail-closed.
- Run terminal mutation and secret scans plus the configured full Makefile gate.

Acceptance criteria:
- The standalone reviewed head contains no unrelated systemic-epic work and is merged to main.
- A controlled make restart deploys the exact main revision after active agents drain.
- A live worker and terminal auditor each receive command completion without an immediate accumulated-idle stall, duplicate retry, hidden provider, or stale alert.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-05 23:59
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-05 23:59
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
