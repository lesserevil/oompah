---
id: OOMPAH-1334
type: bug
status: In Review
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
updated_at: '2026-08-26T09:10:20.823470Z'
work_branch: OOMPAH-1334
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/932
review_number: '932'
review_head: 54945b27c2558ecfb7949b7c20794149841c687d
merged_at: null
oompah.lifecycle_revision: 4
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: e0cd2b77f43728f834e3be4a42ef4726942676842c4590fe2c09b52d09db6c5c
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-26T05:03:13.214959+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: OOMPAH-1334 reports a git authentication failure during\
    \ state branch fetch in backend:server, distinct from OOMPAH-10's rebase strategy\
    \ issue (archived), OOMPAH-1015's metadata malformation errors (merged), and OOMPAH-270's\
    \ git lock retry logic (archived). No active task addresses the same StateBranchFetchError\
    \ with permission denied root cause.\nLooking at OOMPAH-1334 and the supplied\
    \ task corpus, I need to determine if this is a duplicate of an existing active\
    \ task.\n\n## Analysis\n\n**OOMPAH-1334 Core Issue:**\n- Error: `StateBranchFetchError`\
    \ when trying to sync state branch via `git fetch origin`\n- Root cause: Authentication/permission\
    \ failure (`git@gitlab-master.nvidia.com: Permission denied`)\n- Context: Triggered\
    \ during Create issue API in `backend:server`\n- Error type: Git authentication/network\
    \ access failure, auto-filed by error_watcher\n\n**Reviewing Active Tasks in Corpus:**\n\
    \n1. **OOMPAH-10** (Archived - not a candidate): \"Fix native markdown tracker\
    \ default-branch sync failures\"\n   - Different error: `git pull --rebase origin\
    \ main` \u2192 `Cannot rebase onto multiple branches`\n   - Different scope: Tracker\
    \ metadata sync, not state branch sync\n   - Different backend: Tracker dispatch\
    \ path, not backend:server\n   - Already resolved via fetch+ff-only strategy\n\
    \n2. **OOMPAH-1000, OOMPAH-1002** (Merged - terminal states): Terminal audit and\
    \ quality gate issues\n   - Different error types entirely, unrelated to git auth\n\
    \n3. **OOMPAH-1015 and OOMPAH-1016..1044** (Merged/Archived - terminal states):\
    \ Terminal audit enforcement metadata errors\n   - Different error type: Metadata\
    \ malformation, not git auth\n   - Different backend: `backend:terminal_audit_enforcement`,\
    \ not `backend:server`\n   - Different root cause: Schema compatibility, not network/credential\
    \ issues\n\n4. **OOMPAH-270** (Archived): \"Add retry-with-backoff for transient\
    \ git lock errors\"\n   - Different error type: Git lock errors, not authentication\
    \ failures\n\n## Verdict\n\nOOMPAH-1334 describes a distinct issue: git authentication\
    \ failures during state branch fetch operations in the backend:server component.\
    \ While the corpus contains related auto-filed error tasks from error_watcher\
    \ (notably OOMPAH-1015 startup flood), none represent the same underlying problem.\
    \ The authentication/network access issue is fundamentally different from the\
    \ metadata validation or r"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: null
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
  - run_id: 4ce3081336dc4eaaa7f0fe4f95405e30--contributor-86e3ac8153e1
    provider_id: prov-6cf41c89
    provider_name: Opencode/Switchyard
    model_id: switchyard/auto
    focus: duplicate_detector
    source_branch: OOMPAH-1334
    source_sha: null
    completed_at: ''
  - run_id: 82afd37cee14461bb7d162d9dcccaa7f--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1334
    source_sha: null
    completed_at: ''
  - run_id: 51289540d0db455583caacbe1ac40327--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1334
    source_sha: dfbc5213ec2b5d83682f1f744cd2b3a5d6afa1cc
    completed_at: '2026-08-26T05:03:13.221523+00:00'
  - run_id: 4b445e3e4ca8411c8960f051534e1eab--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: security
    source_branch: OOMPAH-1334
    source_sha: null
    completed_at: ''
  - run_id: aaea5160b8d248c4b36a8f8209e922f1--contributor-86e3ac8153e1
    provider_id: prov-6cf41c89
    provider_name: Opencode/Switchyard
    model_id: switchyard/auto
    focus: security
    source_branch: OOMPAH-1334
    source_sha: b149dbc8aafc583f248d223a176ba1c4817323c7
    completed_at: '2026-08-26T06:54:55.320043+00:00'
  - run_id: 59dfd6b695e74064a3f4b1bb9a508b1d--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: security
    source_branch: OOMPAH-1334
    source_sha: null
    completed_at: ''
oompah.task_costs:
  total_input_tokens: 162
  total_output_tokens: 1887
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 162
      output_tokens: 1887
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1773
    cost_usd: 0.0
    recorded_at: '2026-08-26T05:03:13.213487+00:00'
  - profile: default
    model: haiku
    input_tokens: 152
    output_tokens: 114
    cost_usd: 0.0
    recorded_at: '2026-08-26T06:54:55.313327+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1334
  base_branch: main
  base_sha: 4ecdda1ab1112659549b3098134997d02bb42b5f
  head_sha: 54945b27c2558ecfb7949b7c20794149841c687d
  submitted_at: '2026-08-26T07:23:15.057184+00:00'
  updated_at: '2026-08-26T09:10:18.422636+00:00'
  wait_reason: review_generation_requeue
  wait_generation: review:98804c2202ba0a81bce403bf2d9f161f863a633f9924d85e9c8df2a4e45b0620
oompah.work_branch: OOMPAH-1334
oompah.review_url: https://github.com/lesserevil/oompah/pull/932
oompah.review_number: '932'
oompah.target_branch: main
oompah.review_head: 54945b27c2558ecfb7949b7c20794149841c687d
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
author: oompah
created: 2026-08-26 01:57
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-26 01:58
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-26 01:59
---
Run #1 [attempt=1, profile=default, role=fast -> Opencode/Switchyard/switchyard/auto]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 9s
- Log: OOMPAH-1334__20260826T015900Z.jsonl
---
author: oompah
created: 2026-08-26 03:34
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-26 03:34
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-26 03:35
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 47s
- Log: OOMPAH-1334__20260826T033441Z.jsonl
---
author: oompah
created: 2026-08-26 03:35
---
Duplicate screening was inconclusive 3 times. Human action required: a project owner must review the authoritative task corpus and use the authenticated duplicate-screening owner-resolution action (POST /api/v1/issues/OOMPAH-1334/duplicate-screening/owner-resolution) with a conclusive verdict and reason. This records the owner decision, resets the retry budget, and returns no_duplicate tasks to Open (or routes a verified duplicate to Duplicate Candidate). A plain verdict comment is not authoritative.
---
author: oompah
created: 2026-08-26 05:01
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-26 05:02
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-26 05:03
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.8K out [1.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 26s
- Log: OOMPAH-1334__20260826T050237Z.jsonl
---
author: oompah
created: 2026-08-26 05:49
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-26 05:50
---
Focus: Security Auditor
---
author: oompah
created: 2026-08-26 05:51
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 39s
- Log: OOMPAH-1334__20260826T055046Z.jsonl
---
author: oompah
created: 2026-08-26 06:42
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-26 06:43
---
Focus: Security Auditor
---
author: oompah
created: 2026-08-26 06:54
---
Implemented: server.create_issue now catches StateBranchFetchError and degrades gracefully (503 + WARNING) instead of logging ERROR, preventing error_watcher auto-filing. Files: oompah/server.py, tests/test_server_create_issue.py. Test: pytest -q tests/test_server_create_issue.py::TestCreateIssueStateBranchFetchError::test_state_branch_fetch_error_returns_503_and_logs_warning. Note: Unable to submit because current worktree branch is OOMPAH-1219, but task expects OOMPAH-1334.
---
author: oompah
created: 2026-08-26 06:54
---
Run #1 [attempt=1, profile=default, role=fast -> Opencode/Switchyard/switchyard/auto]
- Turns: 67, Tool calls: 67
- Tokens: 152 in / 114 out [90.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 12m 23s
- Log: OOMPAH-1334__20260826T064403Z.jsonl
---
author: oompah
created: 2026-08-26 07:09
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-26 07:10
---
Focus: Security Auditor
---
author: oompah
created: 2026-08-26 07:15
---
**Understanding**: The issue is that when the api_create_issue endpoint encounters a StateBranchFetchError (e.g., due to network/auth issues with git), it logs the error using logger.error() which triggers error_watcher auto-filing. The fix is to catch StateBranchFetchError specifically and log it as WARNING instead of ERROR, while returning a 503 (Service Unavailable) status instead of 500. This degrades gracefully without triggering error_watcher.

**Planned approach**: 
1. Add StateBranchFetchError import at the api_create_issue function level
2. Add a specific except handler for StateBranchFetchError after the existing handlers but before the generic Exception handler
3. Log with logger.warning() and return 503 status code
4. Add comprehensive unit tests to verify behavior
5. Run tests to verify no regressions
---
author: oompah
created: 2026-08-26 07:22
---
**Discovery & Implementation**: Found and fixed the issue in oompah/server.py api_create_issue endpoint.

**Root cause**: When the tracker.create_issue() call raises StateBranchFetchError (git fetch failures), it was caught by the generic Exception handler which logs at ERROR level, triggering error_watcher auto-filing.

**Fix applied**:
1. Added import: from oompah.tracker import StateBranchFetchError
2. Added specific exception handler for StateBranchFetchError before generic Exception handler
3. Changed logging from ERROR to WARNING (prevents error_watcher trigger)
4. Return 503 Service Unavailable (not 500) with retryable=True flag
5. Error code: state_branch_fetch_failed

**Tests added**: 
- test_state_branch_fetch_error_returns_503_and_logs_warning: Verifies 503 response and WARNING log
- test_generic_exception_still_returns_500_and_logs_error: Verifies other exceptions still log ERROR 
- test_state_branch_fetch_error_does_not_trigger_error_watcher: Confirms WARNING-level logging

**Test results**: All 24 tests pass (3 new + 21 existing, no regressions)
Files modified: oompah/server.py, tests/test_server_create_issue.py
---
author: oompah
created: 2026-08-26 07:23
---
**Verification**: 
- Code changes committed to branch OOMPAH-1334
- All 24 tests pass (3 new + 21 existing)
- StateBranchFetchError now: logs WARNING, returns 503, sets retryable=true
- Generic exceptions still: log ERROR, return 500 (no regression)
- Git branch up to date with origin/OOMPAH-1334

Ready for submission.
---
author: oompah
created: 2026-08-26 07:23
---
Fixed StateBranchFetchError handling in api_create_issue to degrade gracefully (503 + WARNING) instead of triggering error_watcher. Added comprehensive tests verifying correct logging level and HTTP status code.
---
author: oompah
created: 2026-08-26 08:17
---
Branch quality gate passed for `54945b27c2558ecfb7949b7c20794149841c687d` using `make test` in 186.0s. Review creation may proceed.
---
<!-- COMMENTS:END -->
