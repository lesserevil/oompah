---
id: OOMPAH-654
type: task
status: In Progress
priority: null
title: Keep service lifecycle identity metadata out of git worktree status
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T10:29:49.323393Z'
updated_at: '2026-07-31T10:32:54.714385Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 8636c86f6d347afd10831ff399fc2b9d01193f270c6c2981b38987c794a9a5b9
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-31T10:32:21.579375+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector  \nDuplicate preflight verdict: no_duplicate\
    \  \nMatches: none  \nEvidence: Reviewed OOMPAH-36, OOMPAH-32, and OOMPAH-38;\
    \ all are archived and cover unrelated beads cleanup, documentation, or release\
    \ work. No active task matches the PID metadata/git-status regression."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: fc45554e-d0f5-4f0a-b99f-edb1a44f941b
oompah.task_costs:
  total_input_tokens: 496817
  total_output_tokens: 2667
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 496817
      output_tokens: 2667
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 496817
    output_tokens: 2667
    cost_usd: 0.0
    recorded_at: '2026-07-31T10:32:21.577657+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-654__20260731T103119Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-654
    source_sha: ec0ec7d89fb8804571fcf7e780558e6d979b73ea
    completed_at: '2026-07-31T10:32:21.590256+00:00'
---
## Summary

Regression found immediately after deploying OOMPAH-652 on merged main ec0ec7d89: normal make restart safely creates .oompah.pid.meta beside the ignored .oompah.pid, but .gitignore ignores only *.pid. Canonical main becomes dirty solely because the service is running. Implementation scope: add the exact lifecycle metadata and any atomic temporary variants created by Makefile identity capture to the appropriate gitignore rules without broadly ignoring unrelated metadata; audit Makefile cleanup/start/restart paths and documentation if necessary. Add a regression test that creates the configured PID_FILE/PID_META_FILE artifacts in a representative checkout and proves git status remains clean while unrelated *.meta files remain visible, and verify make restart/status lifecycle tests. Acceptance: a normal running service with .oompah.pid and .oompah.pid.meta (including transient .tmp.* files if observable) does not dirty a clean checkout; unrelated metadata is not hidden; focused tests and git diff --check pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-31 10:31
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-31 10:31
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-31 10:32
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 10
- Tokens: 496.8K in / 2.7K out [499.5K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 7s
- Log: OOMPAH-654__20260731T103119Z.jsonl
---
author: oompah
created: 2026-07-31 10:32
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-31 10:32
---
Focus: Refactoring Specialist
---
author: oompah
created: 2026-07-31 10:32
---
**Understanding & Plan**: The regression from OOMPAH-652 causes .oompah.pid.meta to dirty git status because .gitignore only ignores *.pid files. Plan: (1) Find .gitignore and Makefile to understand PID file handling, (2) Add .oompah.pid.meta and atomic temporary files to .gitignore, (3) Add test to verify git status remains clean during lifecycle operations, (4) Verify make restart/status tests pass.
---
<!-- COMMENTS:END -->
