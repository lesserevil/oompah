---
id: OOMPAH-188
type: task
status: Archived
priority: null
title: '[backend:webhooks] WebhookForwarder: disabling webhook forwarding for project
  coroot: gh: Resource not accessible by personal access token (HTTP 403)'
parent: null
children: []
blocked_by: []
labels:
- external:github
assignee: null
created_at: '2026-07-13T14:19:41.967141Z'
updated_at: '2026-07-20T15:57:58.354490Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.external.github:
  id: lesserevil/oompah#409
  owner: lesserevil
  repo: oompah
  number: '409'
  url: https://github.com/lesserevil/oompah/issues/409
  requestor_login: NVShawn
  imported_comment_ids: []
  last_synced_status: Archived
  last_synced_at: '2026-07-20T15:57:57.543202+00:00'
  last_github_state: closed
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
  last_validated_at: '2026-07-13T14:20:04.311608+00:00'
oompah.agent_run_id: ed2a0bc7-84aa-4b63-b433-2c27f0ba6a46
oompah.task_costs:
  total_input_tokens: 90
  total_output_tokens: 2467
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 90
      output_tokens: 2467
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 90
    output_tokens: 2467
    cost_usd: 0.0
    recorded_at: '2026-07-13T15:05:25.957843+00:00'
---
## Summary

### Problem

Oompah detected a backend error from `backend:webhooks`:

> WebhookForwarder: disabling webhook forwarding for project coroot: gh: Resource not accessible by personal access token (HTTP 403)

### Desired Behavior

The operation in `backend:webhooks` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Steps to Reproduce

1. Run oompah with `backend:webhooks` active.
2. Let oompah execute the operation that involves `backend:webhooks` (tracker: `github_issues:lesserevil/oompah`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior

An error occurs in `backend:webhooks` and is recorded by oompah's `error_watcher`:

> WebhookForwarder: disabling webhook forwarding for project coroot: gh: Resource not accessible by personal access token (HTTP 403)

### Acceptance Criteria

- The error from `backend:webhooks` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: global
- tracker: github_issues:lesserevil/oompah
- tracker_kind: github_issues
- fingerprint: 19757d16e7ee9e94
- dedup_fingerprint: 19757d16e7ee9e94
- tracker_owner: lesserevil
- tracker_repo: oompah

## External GitHub Issue

- URL: https://github.com/lesserevil/oompah/issues/409
- Requestor: @NVShawn
- Reference: lesserevil/oompah#409

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-13 14:52
---
Root cause confirmed: the fine-grained GitHub PAT used by gh webhook forward lacked the repository Webhooks: Read and write permission. The operator has updated the coroot PAT. Updating operator, onboarding, webhook-forwarding, and .env example documentation so webhook administration is explicitly required whenever forwarding is enabled.
---
author: oompah
created: 2026-07-13 14:56
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-13 14:56
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-13 15:05
---
Understanding & Discovery: Investigated OOMPAH-188 for duplicates.

OOMPAH-188 is about project 'coroot' failing with HTTP 403 'Resource not accessible by personal access token'. This is NOT a duplicate of the existing OOMPAH-58 series (and its ~90 archived clones), all of which concern project 'trickle' with HTTP 404 'Not Found'. These are different root causes:
- HTTP 404 = webhook API endpoint not found / insufficient admin permission on repo
- HTTP 403 = fine-grained PAT lacks the specific 'Webhooks: Read and write' repository permission

The work for OOMPAH-188 has already been completed:
1. The operator updated the coroot PAT to include Webhooks: Read and write permission (operational fix, done before this task was dispatched).
2. Commit b58265d6 ('Document webhook PAT permission') on main already added documentation to four files:
   - .env.example: Added warning that webhook forwarding requires 'Webhooks: Read and write' on fine-grained PATs
   - docs/webhook-forwarding.md: Added 'Token permission' setup section + troubleshooting entry for HTTP 403 'Resource not accessible by personal access token'
   - docs/managed-project-onboarding.md: Added webhook permission requirement
   - docs/operator-runbook.md: Updated GITHUB_TOKEN description to include webhook permission

The code behavior is correct as-is: _is_fatal_forwarder_error() correctly classifies HTTP 403 as fatal and disables that project's forwarder (preventing noisy retry loops), and the configuration-change detection (old_config != new_config) correctly re-enables it when the PAT is updated without requiring a restart.

No code changes required. No duplicate found. Closing as complete.
---
author: oompah
created: 2026-07-13 15:05
---
Not a duplicate. Root cause (PAT missing Webhooks: Read and write permission) was fixed operationally by the operator updating the coroot PAT. Documentation was updated in commit b58265d6 across .env.example, docs/webhook-forwarding.md, docs/managed-project-onboarding.md, and docs/operator-runbook.md to explicitly require this permission for all projects using webhook forwarding. No code changes needed; error handling behavior (fatal 403 disables the forwarder, config-change clears the disabled flag) is correct.
---
author: oompah
created: 2026-07-13 15:05
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 0, Tool calls: 55
- Tokens: 90 in / 2.5K out [2.6K total]
- Cost: $0.0000
- Exit: terminated, Duration: 8m 48s
- Log: OOMPAH-188__20260713T145643Z.jsonl
---
<!-- COMMENTS:END -->
