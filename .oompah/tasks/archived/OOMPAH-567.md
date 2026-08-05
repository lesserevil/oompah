---
id: OOMPAH-567
type: task
status: Archived
priority: null
title: Install complete test dependencies in fresh Makefile worktrees
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-29T22:48:39.126282Z'
updated_at: '2026-08-05T23:26:17.507832Z'
work_branch: OOMPAH-567
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/584
review_number: '584'
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 74a23c6d090c22ea61528ddfcf61a260aa0aac54abbcc720f6217632de107b58
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-29T22:51:59.901868+00:00'
  matched_identifiers: []
  evidence: 'Focus handoff: duplicate_detector


    Duplicate preflight verdict: no_duplicate


    Matches: none


    Evidence: No active task covers fresh-worktree test dependency setup. Reviewed
    active OOMPAH-281 (self-hosted runner) and archived OOMPAH-25/31 (packaging/bootstrap),
    which are distinct. No files or tracker state were modified.'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 0f6e797a-df52-41e5-aa88-1fe927890b1d
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-567__20260729T225056Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-567
    source_sha: 9fab41077abdd6d02c19624c9713a144f8c84b9e
    completed_at: '2026-07-29T22:51:59.906486+00:00'
oompah.task_costs:
  total_input_tokens: 430116
  total_output_tokens: 2444
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 430116
      output_tokens: 2444
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 429814
    output_tokens: 2360
    cost_usd: 0.0
    recorded_at: '2026-07-29T22:51:59.900737+00:00'
  - profile: default
    model: haiku
    input_tokens: 302
    output_tokens: 84
    cost_usd: 0.0
    recorded_at: '2026-07-29T23:06:49.624577+00:00'
oompah.integration:
  version: 1
  state: ready
  attempts: 0
  task_branch: OOMPAH-567
  head_sha: 98c4cd0fe44ee8ba55f0a88ab52693cc53af31bf
  submitted_at: '2026-07-29T22:59:57.952992+00:00'
  updated_at: '2026-07-29T22:59:57.952992+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/584
oompah.review_number: '584'
oompah.work_branch: OOMPAH-567
oompah.target_branch: main
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-843c6d79e322: '2026-08-05T23:26:06.573394+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-567
    target_state: Archived
    evidence_fingerprint: c75beae79487946d7e08ba63c0c7d8dd562fcf1e4d1e7e74dd7c0a3c61566873
    audit_ids:
    - audit-e19146ff10c8
    kind: result
    applied: true
    retired_at: '2026-08-05T23:26:06.573406+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-567
    audit_id: audit-e19146ff10c8
    attempt_id: attempt-843c6d79e322
    target_state: Archived
    evidence_fingerprint: c75beae79487946d7e08ba63c0c7d8dd562fcf1e4d1e7e74dd7c0a3c61566873
    status: Archived
    audit_ids:
    - audit-e19146ff10c8
    applied: true
    created_at: '2026-08-05T23:26:06.573423+00:00'
    applied_at: '2026-08-05T23:26:15.559395+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-e19146ff10c8
    project_id: proj-14849f1b
    task_id: OOMPAH-567
    target_state: Archived
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: c75beae79487946d7e08ba63c0c7d8dd562fcf1e4d1e7e74dd7c0a3c61566873
    attempts:
    - version: 1
      attempt_id: attempt-843c6d79e322
      target_state: Archived
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: c75beae79487946d7e08ba63c0c7d8dd562fcf1e4d1e7e74dd7c0a3c61566873
      created_at: '2026-08-05T23:22:01.238165+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-05T23:22:01.238165+00:00'
      branch_key: OOMPAH-567
      verdict: pass
      completed_at: '2026-08-05T23:26:06.573212+00:00'
      ended_at: '2026-08-05T23:26:06.573212+00:00'
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-05T23:21:34.882840+00:00'
    updated_at: '2026-08-05T23:26:06.573212+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-843c6d79e322
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: c75beae79487946d7e08ba63c0c7d8dd562fcf1e4d1e7e74dd7c0a3c61566873
    created_at: '2026-08-05T23:22:01.238165+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-05T23:22:01.238165+00:00'
    branch_key: OOMPAH-567
---
## Summary

Fresh integration worktrees run the configured quality gate via make test. The Makefile test target currently depends on setup, which installs only .[server]; uv then adds only the dependency-group pytest packages, leaving the claude, codex, and granian test dependencies absent. Live reproduction on OOMPAH-564 and OOMPAH-565: both exact combined-tree gates produced 112 failures and 4 errors, including SDK install guards and authority/terminal interface tests, while the same heads pass CI where .[dev] is installed. Scope: give make test/test-serial an idempotent test-specific setup marker that installs .[dev] without changing production start/setup behavior; ensure the marker is invalidated by pyproject.toml; document target behavior if needed. Add Makefile/packaging regression tests that prove test targets depend on the complete dev extra and server startup remains server-only. Acceptance criteria: a clean worktree with no preexisting .venv can run make test with both agent SDKs and granian importable; focused tests pass; the full Makefile gate passes; committed work is pushed and submitted through oompah.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 22:49
---
Implementing the fresh-worktree Makefile test dependency fix directly from the primary checkout.
---
author: oompah
created: 2026-07-29 22:50
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-29 22:50
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-29 22:52
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 10
- Tokens: 429.8K in / 2.4K out [432.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 15s
- Log: OOMPAH-567__20260729T225056Z.jsonl
---
author: oompah
created: 2026-07-29 22:52
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-29 22:52
---
Focus: Test Engineer
---
author: oompah
created: 2026-07-29 22:52
---
Understanding: Fresh worktrees fail make test because test targets depend only on setup which installs .[server], leaving claude/codex/granian test deps absent. Need to: (1) Add idempotent test-specific setup marker installing .[dev] without changing prod start/setup; (2) Ensure marker invalidated by pyproject.toml; (3) Add regression tests proving test depends on dev extra + server startup remains server-only. Approach: Examine Makefile test targets and pyproject.toml structure, then implement cached marker pattern.
---
author: oompah
created: 2026-07-29 22:53
---
Discovery: Issue is in Makefile structure. Current setup installs only .[server] (no test backends). Test targets (make test/test-serial) depend on setup but need .[dev] which includes claude-agent-sdk, openai-agents, and granian. Solution: Add idempotent test marker $(VENV)/.uv-test-setup (like existing .uv-setup) that installs .[dev] if missing, invalidated by pyproject.toml changes. Keep setup unchanged (production server-only). Add regression tests verifying: (1) test target pulls in dev extra, (2) start/setup remain server-only.
---
author: oompah
created: 2026-07-29 22:54
---
Implementation: (1) Added test-setup target to Makefile that installs .[dev] with idempotent marker $(VENV)/.uv-test-setup invalidated by pyproject.toml. (2) Updated test and test-serial targets to depend on test-setup instead of setup. (3) Kept setup target unchanged (server-only). (4) Added comprehensive regression tests in tests/test_makefile_packaging.py that verify: dev extra with all backends is installed for tests, setup remains server-only, markers properly invalidated by pyproject changes.
---
author: oompah
created: 2026-07-29 23:00
---
Added an idempotent Makefile test-setup marker that installs .[dev] for test/test-serial while leaving production setup on .[server]. Added Makefile regression coverage. Verification: 23 focused tests passed; clean temporary venv imported claude_agent_sdk, agents, and granian; full make test passed with 13,600 passed and 7 skipped.
---
author: oompah
created: 2026-07-29 23:06
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 0, Tool calls: 15
- Tokens: 302 in / 84 out [386 total]
- Cost: $0.0000
- Exit: terminated, Duration: 14m 33s
- Log: OOMPAH-567__20260729T225225Z.jsonl
---
author: oompah
created: 2026-07-29 23:07
---
YOLO: merged PR #584.
---
author: oompah
created: 2026-08-05 23:21
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
author: oompah
created: 2026-08-05 23:22
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-05 23:22
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-05 23:26
---
Audit PASS — Archived

[REDACTED]

Safe evidence:
- merge_commit: 441c09132
- task_commit: 98c4cd0fe
- merged_at: 2026-07-29
- makefile_targets: test-setup depends on $(VENV)/.uv-test-setup; test/test-serial depend on test-setup; setup unchanged (server extra)
- regression_tests: tests/test_makefile_setup.py (test_test_targets_install_complete_dev_dependencies, test_setup_installs_server_dependencies_only); tests/test_pytest_parallel.py updated for test-serial
- worktree_state: clean; contained in main
- coordination_peers: OOMPAH-745 advisory only; not a blocker
---
<!-- COMMENTS:END -->
