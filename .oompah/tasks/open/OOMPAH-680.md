---
id: OOMPAH-680
type: task
status: Open
priority: null
title: Use project forge credentials for all managed Git network operations
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-01T17:31:44.735248Z'
updated_at: '2026-08-01T17:43:25.618511Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 26e4c605cd4b174aae95ca9bca020dcfc7f0aa3165acc75318ef4df395d353b8
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-01T17:43:21.075561+00:00'
  matched_identifiers: []
  evidence: 'Focus handoff: duplicate_detector


    Duplicate preflight verdict: no_duplicate


    Matches: none


    Evidence: Reviewed active OOMPAH-282 (state-branch migration Unicode failure)
    and OOMPAH-281 (GitHub Actions runner); neither covers forge-aware credentials
    for managed Git operations. Related state-branch tasks are terminal and excluded.'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 8904b37e-d4f9-4212-ac47-503356b91b86
oompah.task_costs:
  total_input_tokens: 226343
  total_output_tokens: 1354
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 226343
      output_tokens: 1354
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 226343
    output_tokens: 1354
    cost_usd: 0.0
    recorded_at: '2026-08-01T17:43:21.073572+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-680__20260801T174212Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-680
    source_sha: 6f6909fb85fa4194ee11f991e86ad290160bec2f
    completed_at: '2026-08-01T17:43:21.092891+00:00'
---
## Summary

Live NodeVirt failure on 2026-08-01: the GitLab project has a valid configured access token and forge API calls succeed, but ordinary Oompah-managed git pushes run without forge credentials. Publishing epic-NODEVIRT-* and checkpointing oompah/state/proj-bbba976d failed with `fatal: could not read Username for https://gitlab-master.nvidia.com`, sending NODEVIRT-7 through NODEVIRT-21 to Needs Human before duplicate screening began. State-branch migration already has an ephemeral, redacted GIT_ASKPASS mechanism in oompah/git_credentials.py, but normal ProjectStore, worktree/epic publication, integration, branch cleanup, and oompah_md state-branch checkpoint Git commands do not consistently use it. Implementation scope: route every managed network Git operation through a shared forge-aware credential environment derived from the target Project access_token; cover clone/fetch/ls-remote/push/delete/verification paths in oompah/projects.py, oompah/oompah_md_tracker.py, integration/review helpers, and any other managed Git callers. Never place tokens in argv, remote URLs, persisted Git config, stdout/stderr, exceptions, or logs; preserve noninteractive failure and redact credential-bearing output. Required tests: private GitLab-style remotes accept the configured project token for epic publication and state checkpoints; missing/invalid tokens fail with forge-neutral actionable diagnostics and no partial state; GitHub behavior remains unchanged; concurrent projects cannot receive each other credentials; worktrees inherit the safe behavior; secret scans pass. Acceptance: a configured GitLab project can dispatch a new epic child, publish its epic/task branches, checkpoint native task state, and clean branches without operator Git credential configuration, while tokens remain absent from process listings, config, URLs, and logs.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-01 17:42
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-01 17:42
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-01 17:43
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 5
- Tokens: 226.3K in / 1.4K out [227.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 20s
- Log: OOMPAH-680__20260801T174212Z.jsonl
---
<!-- COMMENTS:END -->
