---
id: OOMPAH-1152
type: bug
status: Archived
priority: 2
title: '[backend:server] Add comment API error: StateBranchFetchError(''Cannot sync
  state branch \''oompah/state/proj-3e4e9214\'': git fetch origin \''oompah/state/proj-3e4e9214\''
  failed: ** WARNING: connectio...'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-08-12T15:24:03.095156Z'
updated_at: '2026-08-12T20:18:10.295058Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-2d30814f4ba4
    project_id: proj-14849f1b
    task_id: OOMPAH-1152
    target_state: Archived
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: c6bbce73ed34f6b7af09826b7c137050206ef935ce5b632ebca4204d611a53e6
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Historical auto-filed occurrence from the state-branch and dispatch-convergence
      incident, consolidated into completed roots OOMPAH-1127, OOMPAH-1128, and OOMPAH-1177.
      PRs #836 and #837 delivered durable transport fencing, stable incident identity,
      and fail-closed provider admission with passing full CI; this occurrence requires
      no independent implementation.'
    created_at: '2026-08-12T20:18:04.983550+00:00'
    applied: false
  version: 1
  pending_chain: []
  attempt_history: []
oompah.lifecycle_revision: 1
---
## Summary

### Problem
Oompah detected a backend error from `backend:server`:

> Add comment API error: StateBranchFetchError('Cannot sync state branch \'oompah/state/proj-3e4e9214\': git fetch origin \'oompah/state/proj-3e4e9214\' failed: ** WARNING: connection is not using a post-quantum key exchange algorithm.\n** This session may be vulnerable to "store now, decrypt later" attacks.\n** The server may need to be upgraded. See https://openssh.com/pq.html\n#################\n##\nIf you are trying to clone, you are using the incorrect port, use 12051\n##\n##################\nUse of this network is restricted to authorized users only.  All access attempts and activities on this network are subject to being monitored, logged and audited.  The network operator reserves the right to consent to valid law enforcement requests to search the network and to institute legal or disciplinary action against any misuse of the network.\nPermission denied, please try again.\nPermission denied, please try again.\ngit@gitlab-master.nvidia.com: Permission denied (publickey,gssapi-keyex,gssapi-with-mic,password).\nfatal: Could not read from remote repository.\n\nPlease make sure you have the correct access rights\nand the repository exists.. Remediation: verify network access and remote URL (git remote get-url origin).')

### Steps to Reproduce
1. Run oompah with `backend:server` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:server` and is recorded by oompah's `error_watcher`:

> Add comment API error: StateBranchFetchError('Cannot sync state branch \'oompah/state/proj-3e4e9214\': git fetch origin \'oompah/state/proj-3e4e9214\' failed: ** WARNING: connection is not using a post-quantum key exchange algorithm.\n** This session may be vulnerable to "store now, decrypt later" attacks.\n** The server may need to be upgraded. See https://openssh.com/pq.html\n#################\n##\nIf you are trying to clone, you are using the incorrect port, use 12051\n##\n##################\nUse of this network is restricted to authorized users only.  All access attempts and activities on this network are subject to being monitored, logged and audited.  The network operator reserves the right to consent to valid law enforcement requests to search the network and to institute legal or disciplinary action against any misuse of the network.\nPermission denied, please try again.\nPermission denied, please try again.\ngit@gitlab-master.nvidia.com: Permission denied (publickey,gssapi-keyex,gssapi-with-mic,password).\nfatal: Could not read from remote repository.\n\nPlease make sure you have the correct access rights\nand the repository exists.. Remediation: verify network access and remote URL (git remote get-url origin).')

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
- fingerprint: 389ac17ab3c6385b
- dedup_fingerprint: 389ac17ab3c6385b

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

