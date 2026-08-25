---
id: OOMPAH-1334
type: bug
status: Open
priority: 2
title: '[backend:server] Create issue API error: StateBranchFetchError(''Cannot sync
  state branch \''oompah/state/proj-3e4e9214\'': git fetch origin \''oompah/state/proj-3e4e9214\''
  failed: ** WARNING: connecti...'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-24T21:31:41.109952Z'
updated_at: '2026-08-25T18:38:46.767218Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.lifecycle_revision: 1
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: e0cd2b77f43728f834e3be4a42ef4726942676842c4590fe2c09b52d09db6c5c
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 38007e8ff77fc1f9230aa50e381863d187767d32ba72b9c447ed5be00a58d84c:168359
  claim_owner: 829de7a5-1741-4215-9113-036b82d27d43
  claimed_at: '2026-08-25T18:38:22.670193+00:00'
  claim_expires_at: '2026-08-25T19:08:22.670193+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 0c1ae80f-d874-42bd-8823-4aa8c1dae08b
---
## Summary

### Problem
Oompah detected a backend error from `backend:server`:

> Create issue API error: StateBranchFetchError('Cannot sync state branch \'oompah/state/proj-3e4e9214\': git fetch origin \'oompah/state/proj-3e4e9214\' failed: ** WARNING: connection is not using a post-quantum key exchange algorithm.\n** This session may be vulnerable to "store now, decrypt later" attacks.\n** The server may need to be upgraded. See https://openssh.com/pq.html\n#################\n##\nIf you are trying to clone, you are using the incorrect port, use 12051\n##\n##################\nUse of this network is restricted to authorized users only.  All access attempts and activities on this network are subject to being monitored, logged and audited.  The network operator reserves the right to consent to valid law enforcement requests to search the network and to institute legal or disciplinary action against any misuse of the network.\ngit@gitlab-master.nvidia.com: Permission denied (publickey,gssapi-keyex,gssapi-with-mic,password).\nfatal: Could not read from remote repository.\n\nPlease make sure you have the correct access rights\nand the repository exists.. Remediation: verify network access and remote URL (git remote get-url origin).')

### Steps to Reproduce
1. Run oompah with `backend:server` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:server` and is recorded by oompah's `error_watcher`:

> Create issue API error: StateBranchFetchError('Cannot sync state branch \'oompah/state/proj-3e4e9214\': git fetch origin \'oompah/state/proj-3e4e9214\' failed: ** WARNING: connection is not using a post-quantum key exchange algorithm.\n** This session may be vulnerable to "store now, decrypt later" attacks.\n** The server may need to be upgraded. See https://openssh.com/pq.html\n#################\n##\nIf you are trying to clone, you are using the incorrect port, use 12051\n##\n##################\nUse of this network is restricted to authorized users only.  All access attempts and activities on this network are subject to being monitored, logged and audited.  The network operator reserves the right to consent to valid law enforcement requests to search the network and to institute legal or disciplinary action against any misuse of the network.\ngit@gitlab-master.nvidia.com: Permission denied (publickey,gssapi-keyex,gssapi-with-mic,password).\nfatal: Could not read from remote repository.\n\nPlease make sure you have the correct access rights\nand the repository exists.. Remediation: verify network access and remote URL (git remote get-url origin).')

### Expected Behavior
The operation in `backend:server` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Acceptance Criteria
- The error from `backend:server` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: proj-14849f1b
- tracker: provenanceguardedtracker
- tracker_kind: provenanceguardedtracker
- fingerprint: a2e6526d28290e20
- dedup_fingerprint: a2e6526d28290e20

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-24 21:43
---
Duplicate error_watcher occurrence suppressed; this task already tracks the same dedup fingerprint.

Source: `backend:server`

Message: Create issue API error: StateBranchFetchError('Cannot sync state branch \'oompah/state/proj-3e4e9214\': git fetch origin \'oompah/state/proj-3e4e9214\' failed: ** WARNING: connection is not using a post-quantum key exchange algorithm.\n** This session may be vulnerable to "store now, decrypt later" attacks.\n** The server may need to be upgraded. See https://openssh.com/pq.html\n#################\n##\nIf you are trying to clone, you are using the incorrect port, use 12051\n##\n##################\nUse of this network is restricted to authorized users only.  All access attempts and activities on this network are subject to being monitored, logged and audited.  The network operator reserves the right to consent to valid law enforcement requests to search the network and to institute legal or disciplinary action against any misuse of the network.\ngit@gitlab-master.nvidia.com: Permission denied (publickey,gssapi-keyex,gssapi-with-mic,password).\nfatal: Could not read from remote repository.\n\nPlease make sure you have the correct access rights\nand the repository exists.. Remediation: verify network access and remote URL (git remote get-url origin).')
---
<!-- COMMENTS:END -->
