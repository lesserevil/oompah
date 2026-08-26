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
updated_at: '2026-08-26T01:57:36.072285Z'
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
  claim_id: bf2baa518454d2a442b68b1f5958439ce7bbe957d07a045b8c8d3a8265eb8ae8:169299
  claim_owner: 59c949b7-50e0-4ac7-8d28-d26753aebdc9
  claimed_at: '2026-08-26T01:57:29.143580+00:00'
  claim_expires_at: '2026-08-26T02:27:29.143580+00:00'
  retry_count: 1
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 01856b12-d621-4f80-8a5b-d1fb7ff80313
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
  - run_id: 8ea7504851674b408b69fb6cd9212567--contributor-86e3ac8153e1
    provider_id: prov-6cf41c89
    provider_name: Opencode/Switchyard
    model_id: switchyard/auto
    focus: duplicate_detector
    source_branch: OOMPAH-1334
    source_sha: null
    completed_at: ''
  - run_id: 8233cd92adbc43b495674d3784bd6051--contributor-86e3ac8153e1
    provider_id: prov-6cf41c89
    provider_name: Opencode/Switchyard
    model_id: switchyard/auto
    focus: duplicate_detector
    source_branch: OOMPAH-1334
    source_sha: null
    completed_at: ''
  - run_id: a48194fcccfe4b7faef72b41239a6af8--contributor-86e3ac8153e1
    provider_id: prov-6cf41c89
    provider_name: Opencode/Switchyard
    model_id: switchyard/auto
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
author: oompah
created: 2026-08-25 21:15
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-25 21:16
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-25 21:16
---
Run #1 [attempt=1, profile=default, role=fast -> Opencode/Switchyard/switchyard/auto]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 16s
- Log: OOMPAH-1334__20260825T211616Z.jsonl
---
author: oompah
created: 2026-08-25 23:16
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-25 23:17
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-25 23:18
---
Run #1 [attempt=1, profile=default, role=fast -> Opencode/Switchyard/switchyard/auto]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 30s
- Log: OOMPAH-1334__20260825T231748Z.jsonl
---
author: oompah
created: 2026-08-25 23:18
---
Duplicate screening was inconclusive 3 times. Human action required: a project owner must review the authoritative task corpus and use the authenticated duplicate-screening owner-resolution action (POST /api/v1/issues/OOMPAH-1334/duplicate-screening/owner-resolution) with a conclusive verdict and reason. This records the owner decision, resets the retry budget, and returns no_duplicate tasks to Open (or routes a verified duplicate to Duplicate Candidate). A plain verdict comment is not authoritative.
---
author: oompah
created: 2026-08-26 00:36
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-26 00:37
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-26 00:37
---
Run #1 [attempt=1, profile=default, role=fast -> Opencode/Switchyard/switchyard/auto]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 27s
- Log: OOMPAH-1334__20260826T003739Z.jsonl
---
<!-- COMMENTS:END -->
