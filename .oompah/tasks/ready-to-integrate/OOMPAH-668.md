---
id: OOMPAH-668
type: bug
status: Ready to Integrate
priority: 1
title: Use the trusted test virtualenv without reinstalling inside quality-gate sandbox
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T21:35:20.853943Z'
updated_at: '2026-07-31T21:45:42.609283Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 8e4e3574b1f58ffe3b7c489be06bd9da31962659f65aef9ed6a6ca88664ecc25
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-31T21:38:04.351516+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector  \nDuplicate preflight verdict: no_duplicate\
    \  \nMatches: none  \n\nEvidence: Reviewed active `OOMPAH-281`, backlog `OOMPAH-282`,\
    \ and archived `OOMPAH-38`; none covers this trusted-virtualenv quality-gate failure.\
    \ No files or tracker state were changed."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 03c8150f-ab5a-4de4-82f5-c45f850c8c13
oompah.task_costs:
  total_input_tokens: 634211
  total_output_tokens: 4078
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 634211
      output_tokens: 4078
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 634211
    output_tokens: 4078
    cost_usd: 0.0
    recorded_at: '2026-07-31T21:38:04.349772+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-668__20260731T213635Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-668
    source_sha: 16362384be835d1485d1121ce3c8329743391c79
    completed_at: '2026-07-31T21:38:04.362153+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-668
  head_sha: 1fe2181a2c26b792fa3e6e15e16398f2dcddf34c
  submitted_at: '2026-07-31T21:45:37.292015+00:00'
  updated_at: '2026-07-31T21:45:37.292015+00:00'
---
## Summary

Triggered by: OOMPAH-664

Production reproduction on 2026-07-31 after OOMPAH-664 rebased onto deployed main: the OS-enforced branch gate mounts the service-owned complete test virtualenv read-only at candidate .venv, but git-archive timestamps make candidate pyproject.toml newer than .venv/.uv-setup. make test therefore runs uv pip install -e server before tests; the fail-closed sandbox intentionally exposes only /usr and cannot see the operator uv launcher, producing make: uv: No such file or directory. Even projecting uv would then attempt to mutate the protected read-only trusted runtime. Fix the Makefile quality-gate path so OOMPAH_PYTEST_GATE uses and validates the server-provided test virtualenv without invoking setup or dependency installation, while normal operator and developer make test behavior still installs declared dev dependencies. Preserve sandbox isolation and fail closed if the trusted Python or required test modules are absent. Add regressions for stale pyproject and marker mtimes, no uv visibility, read-only mounted runtime, missing trusted runtime, and unchanged non-gate test-setup behavior; extend the real bubblewrap make-target test to exercise the project Makefile dependency path. Acceptance: OOMPAH-664 exact-head gate reaches pytest instead of failing setup, candidate code cannot mutate the host runtime, focused quality-gate and Makefile tests pass, and the full project gate passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-31 21:35
---
Claimed directly for operator recovery because OOMPAH-664 is otherwise deadlocked in Ready delivery. Reproduction is the production gate on head 9b0696866: make test enters .venv/.uv-setup and fails before pytest because uv is deliberately absent from the sandbox. I will separate gate-mode trusted-runtime validation from normal dependency installation, add regression coverage, run focused and full gates, and deploy before requeueing OOMPAH-664.
---
author: oompah
created: 2026-07-31 21:36
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-31 21:36
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-31 21:38
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 15
- Tokens: 634.2K in / 4.1K out [638.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 35s
- Log: OOMPAH-668__20260731T213635Z.jsonl
---
author: oompah
created: 2026-07-31 21:38
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-31 21:38
---
Agent failed: could not stage recovery snapshot for OOMPAH-668: The following paths are ignored by one of your .gitignore files:
.oompah-no-hooks
hint: Use -f if you really want to add them.
hint: Disable this message with "git config set advice.addIgnoredFile false". Retrying in 10s (attempt #1)
---
author: oompah
created: 2026-07-31 21:38
---
Run #1 [attempt=1, profile=default, role=— -> Claude/haiku]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1s
---
author: oompah
created: 2026-07-31 21:38
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-31 21:38
---
Agent failed: could not stage recovery snapshot for OOMPAH-668: The following paths are ignored by one of your .gitignore files:
.oompah-no-hooks
hint: Use -f if you really want to add them.
hint: Disable this message with "git config set advice.addIgnoredFile false". Retrying in 20s (attempt #2)
---
author: oompah
created: 2026-07-31 21:38
---
Run #2 [attempt=2, profile=deep, role=— -> Claude/opus]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 3s
---
author: oompah
created: 2026-07-31 21:39
---
Retrying (attempt #2, agent: deep)
---
author: oompah
created: 2026-07-31 21:39
---
Agent failed: could not stage recovery snapshot for OOMPAH-668: The following paths are ignored by one of your .gitignore files:
.oompah-no-hooks
hint: Use -f if you really want to add them.
hint: Disable this message with "git config set advice.addIgnoredFile false". Retrying in 40s (attempt #3)
---
author: oompah
created: 2026-07-31 21:39
---
Run #3 [attempt=3, profile=deep, role=— -> Claude/opus]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 2s
---
author: oompah
created: 2026-07-31 21:39
---
Retrying (attempt #3, agent: deep)
---
author: oompah
created: 2026-07-31 21:39
---
Agent failed: could not stage recovery snapshot for OOMPAH-668: The following paths are ignored by one of your .gitignore files:
.oompah-no-hooks
hint: Use -f if you really want to add them.
hint: Disable this message with "git config set advice.addIgnoredFile false". Retrying in 80s (attempt #4)
---
author: oompah
created: 2026-07-31 21:39
---
Run #4 [attempt=4, profile=deep, role=— -> Claude/opus]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 2s
---
author: oompah
created: 2026-07-31 21:41
---
Retrying (attempt #4, agent: deep)
---
author: oompah
created: 2026-07-31 21:41
---
Agent failed: could not stage recovery snapshot for OOMPAH-668: The following paths are ignored by one of your .gitignore files:
.oompah-no-hooks
hint: Use -f if you really want to add them.
hint: Disable this message with "git config set advice.addIgnoredFile false". Retrying in 160s (attempt #5)
---
author: oompah
created: 2026-07-31 21:41
---
Run #5 [attempt=5, profile=deep, role=— -> Claude/opus]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 2s
---
author: oompah
created: 2026-07-31 21:44
---
Retrying (attempt #5, agent: deep)
---
author: oompah
created: 2026-07-31 21:44
---
Agent failed: could not stage recovery snapshot for OOMPAH-668: The following paths are ignored by one of your .gitignore files:
.oompah-no-hooks
hint: Use -f if you really want to add them.
hint: Disable this message with "git config set advice.addIgnoredFile false". Retrying in 300s (attempt #6)
---
author: oompah
created: 2026-07-31 21:44
---
Run #6 [attempt=6, profile=deep, role=— -> Claude/opus]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 2s
---
author: oompah
created: 2026-07-31 21:45
---
Implemented the quality-gate deadlock fix at commit 1fe2181a2. Gate mode now validates and uses the service-owned read-only test virtualenv without invoking uv or mutating the trusted runtime; normal developer/operator test setup remains uv-managed. Regression coverage includes success without uv, missing/incomplete runtime fail-closed behavior, normal-mode installation, and the real bubblewrap gate path. Focused checks: 58 passed. Complete gate: 14,540 passed, 7 skipped, 1 xfailed in 388.07s. Branch is pushed.
---
author: oompah
created: 2026-07-31 21:45
---
Quality gates now use the trusted projected test runtime without reinstalling inside the read-only sandbox; regression and complete test gates pass.
---
<!-- COMMENTS:END -->
