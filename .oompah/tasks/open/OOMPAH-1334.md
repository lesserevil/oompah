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
updated_at: '2026-08-25T18:40:39.912606Z'
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
  evidence: 'RuntimeError: Codex exec exited with code 1:'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 1
  retry_after: '2026-08-25T18:41:27.750316+00:00'
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 0c1ae80f-d874-42bd-8823-4aa8c1dae08b
oompah.work_contributors:
  runs:
  - run_id: bea67738991e4257ac1a7695dd8b76ec--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1334
    source_sha: null
    completed_at: ''
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
author: oompah
created: 2026-08-25 18:38
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-25 18:39
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-25 18:40
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 38s
- Log: OOMPAH-1334__20260825T183946Z.jsonl
---
<!-- COMMENTS:END -->
