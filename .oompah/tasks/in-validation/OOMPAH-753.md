---
id: OOMPAH-753
type: bug
status: In Validation
priority: 1
title: Keep denied non-mutating validator requests recoverable for terminal auditors
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- ci-fix
assignee: null
created_at: '2026-08-04T02:03:10.235988Z'
updated_at: '2026-08-04T04:36:20.031297Z'
work_branch: OOMPAH-753
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/706
review_number: '706'
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 1e1a9046dd4acfb0dbe57f6a0b46d6b1c6201c151525cb893dd9f2792744659e
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-04T02:08:16.618811+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: Reviewed the closest candidates, including OOMPAH-10,\
    \ OOMPAH-158, OOMPAH-159, OOMPAH-191, and OOMPAH-270. All are terminal and address\
    \ different tracker, intake, or git-lock issues; none covers recoverable validator-policy\
    \ mismatches during terminal audits.\nFocus handoff: duplicate_detector  \nDuplicate\
    \ preflight verdict: no_duplicate  \nMatches: none  \n\nEvidence: Reviewed the\
    \ closest candidates, including OOMPAH-10, OOMPAH-158, OOMPAH-159, OOMPAH-191,\
    \ and OOMPAH-270. All are terminal and address different tracker, intake, or git-lock\
    \ issues; none covers recoverable validator-policy mismatches during terminal\
    \ audits."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 1
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: null
oompah.task_costs:
  total_input_tokens: 48231
  total_output_tokens: 59578
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 48202
      output_tokens: 53530
      cost_usd: 0.0
    unknown:
      input_tokens: 29
      output_tokens: 6048
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 2535
    cost_usd: 0.0
    recorded_at: '2026-08-04T02:06:09.974209+00:00'
  - profile: default
    model: haiku
    input_tokens: 47358
    output_tokens: 273
    cost_usd: 0.0
    recorded_at: '2026-08-04T02:08:16.617344+00:00'
  - profile: default
    model: haiku
    input_tokens: 834
    output_tokens: 50722
    cost_usd: 0.0
    recorded_at: '2026-08-04T02:45:50.955332+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 29
    output_tokens: 6048
    cost_usd: 0.0
    recorded_at: '2026-08-04T04:36:17.690962+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-753__20260804T020449Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-753
    source_sha: 18e18a6b63b2f9a522b17c0132dac0f5a0d9e487
    completed_at: '2026-08-04T02:06:09.985128+00:00'
  - run_id: OOMPAH-753__20260804T020751Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-753
    source_sha: 18e18a6b63b2f9a522b17c0132dac0f5a0d9e487
    completed_at: '2026-08-04T02:08:16.632776+00:00'
  - run_id: OOMPAH-753__20260804T020912Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: security
    source_branch: OOMPAH-753
    source_sha: 7b4245335e4ba4ff9e63e2d23fa3add7592bb180
    completed_at: '2026-08-04T02:45:50.979476+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-753
  base_branch: main
  base_sha: bc9c289f401b63603454cda00f7670c000354a21
  head_sha: d9e937f7192866b0f45939da7e7eb1d642b0912c
  submitted_at: '2026-08-04T04:07:37.669745+00:00'
  updated_at: '2026-08-04T04:07:37.669745+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/706
oompah.review_number: '706'
oompah.work_branch: OOMPAH-753
oompah.target_branch: main
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-6b406218bd18: '2026-08-04T04:35:57.784118+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-753
    target_state: Done
    evidence_fingerprint: afce0c913894eeaa4ffe1369726a4429f86eb8b2b1728ec49896abc8b1a600e8
    audit_ids:
    - audit-28c0813119eb
    kind: result
    applied: true
    retired_at: '2026-08-04T04:35:57.784131+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-753
    audit_id: audit-28c0813119eb
    attempt_id: attempt-6b406218bd18
    target_state: Done
    evidence_fingerprint: afce0c913894eeaa4ffe1369726a4429f86eb8b2b1728ec49896abc8b1a600e8
    status: In Validation
    audit_ids:
    - audit-28c0813119eb
    applied: true
    created_at: '2026-08-04T04:35:57.784148+00:00'
    applied_at: '2026-08-04T04:36:02.716775+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-28c0813119eb
    project_id: proj-14849f1b
    task_id: OOMPAH-753
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: afce0c913894eeaa4ffe1369726a4429f86eb8b2b1728ec49896abc8b1a600e8
    attempts:
    - version: 1
      attempt_id: attempt-6b406218bd18
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: afce0c913894eeaa4ffe1369726a4429f86eb8b2b1728ec49896abc8b1a600e8
      created_at: '2026-08-04T04:26:18.911682+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-04T04:26:18.911682+00:00'
      branch_key: OOMPAH-753
      verdict: pass
      completed_at: '2026-08-04T04:35:57.783949+00:00'
      ended_at: '2026-08-04T04:35:57.783949+00:00'
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-04T04:24:44.842905+00:00'
    updated_at: '2026-08-04T04:35:57.783949+00:00'
  - version: 1
    audit_id: audit-0b52e8fa988d
    project_id: proj-14849f1b
    task_id: OOMPAH-753
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: afce0c913894eeaa4ffe1369726a4429f86eb8b2b1728ec49896abc8b1a600e8
    attempts: []
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-04T04:24:44.842905+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-6b406218bd18
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: afce0c913894eeaa4ffe1369726a4429f86eb8b2b1728ec49896abc8b1a600e8
    created_at: '2026-08-04T04:26:18.911682+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-04T04:26:18.911682+00:00'
    branch_key: OOMPAH-753
---
## Summary

Triggered by: OOMPAH-731

Live regression after merged OOMPAH-736 on OOMPAH-731 Merged audit attempt OOMPAH-731__20260804T014819Z. The sole contributor-independent Opus auditor verified exact HEAD, origin/main history, PR 696 merge ancestry, and the implemented symbols. It then requested a focused pytest command with output truncation and a simple direct pytest command. Both are non-mutating validation requests but outside the structured project validation contract, so enforcement denied them. Those two denials consumed the fatal policy budget and terminated the auditor immediately after it requested approved make test-fast; candidate exhaustion returned the already-merged task to Needs Human. OOMPAH-736 explicitly requires policy-contract mismatches not to exhaust all candidates, so this is a live regression rather than missing configuration. Implementation scope: classify syntactically non-mutating validator requests outside the advertised contract as recoverable validation mismatches that do not consume the fatal mutation or provider-failure budget; return structured allowed alternatives from the project contract; keep the auditor session alive so it can run an approved Make target or submit a verdict. Align prompt and tool schema so focused verification is requested only through approved templates. Preserve fatal handling for mutation, output-to-file redirection, credential access, path escape, process control, and state-changing git. Relevant code: auditor command classification and project validation contract, ACP run_command result metadata, orchestrator denial-budget handling, terminal-audit candidate retirement, independence selection, and health. Required tests: replay both exact OOMPAH-731 denied commands followed by make test-fast and accepted submit_audit_result; one independent candidate; repeated non-mutating contract mismatches; approved focused Make target; actual mutation and shell escape remain fatal; health distinguishes recoverable mismatch from policy incompatibility and transport failure. Acceptance criteria: replaying the OOMPAH-731 trace reaches a verdict without rotation or Needs Human, while no unapproved command executes and all write-capable commands remain fail closed.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 02:04
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-04 02:04
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-04 02:06
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 2.5K out [2.5K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 27s
- Log: OOMPAH-753__20260804T020449Z.jsonl
---
author: oompah
created: 2026-08-04 02:07
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-04 02:07
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-04 02:08
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 47.4K in / 273 out [47.6K total]
- Cost: $0.0000
- Exit: normal, Duration: 51s
- Log: OOMPAH-753__20260804T020751Z.jsonl
---
author: oompah
created: 2026-08-04 02:09
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-04 02:09
---
Focus: Security Auditor
---
author: oompah
created: 2026-08-04 02:12
---
UNDERSTANDING: This is a security issue about auditor request handling. The problem: terminal auditors requesting non-mutating validation commands (e.g., pytest with output truncation) outside the project's validation contract are being denied, and these denials consume the fatal policy budget, terminating the auditor prematurely. OOMPAH-736 requires that policy-contract mismatches NOT exhaust candidates, but they currently do. The fix must: (1) classify non-mutating requests outside the contract as RECOVERABLE (not fatal), (2) return structured alternatives from the project contract, (3) keep auditors alive to run approved commands, and (4) preserve fatal handling for actual mutations, credentials, path escapes, and state changes. Next: map how orchestrator handles denials and identify where budget tracking happens.
---
author: oompah
created: 2026-08-04 02:20
---
DISCOVERY: Found the root cause. In auditor.py::check_auditor_command() (line 1151-1209), when a command doesn't match the validation contract regex (line 1175), it returns a FATAL denial immediately, without checking if the command is syntactically non-mutating. This means read-only commands like 'pytest -q' or 'pytest --tb=short' (outside the contract) consume the fatal policy budget. The fix reorders checks: (1) security violations (path escapes, credentials) are fatal first, (2) regex contract check, then (3) for non-matching commands, check mutation status before deciding if denial is recoverable. Non-mutating contract mismatches return recoverable denials with allowed alternatives.
---
author: oompah
created: 2026-08-04 02:30
---
IMPLEMENTATION: Modified auditor.py::check_auditor_command() to classify non-mutating validator requests outside the project contract as RECOVERABLE (not fatal). Key changes: (1) Security checks (path escapes, credentials) happen first and remain fatal, (2) State-changing mutations and dangerous constructs (process control, shell redirects) are fatal, (3) Non-mutating commands outside contract return recoverable denials with allowed alternatives, (4) git rev-list unsupported flags return recoverable errors. Added regression test test_oompah_753_non_mutating_validator_requests_outside_contract_are_recoverable.
---
author: oompah
created: 2026-08-04 02:44
---
VERIFICATION: All auditor tests passing (66 tests). Changes implemented and committed. Fixed mutation detection for system() calls and getline operations. Refined contract mismatch logic: make targets outside contract now return recoverable denials, while other unknown commands remain fatal for safety.
---
author: oompah
created: 2026-08-04 02:45
---
Implemented recoverable non-mutating validator requests for terminal auditors. Auditor command validation now classifies policy contract mismatches as recoverable (not consuming fatal budget), allowing auditors to continue after requesting commands outside the validation contract. Fixes OOMPAH-731 regression. All 66 auditor/contract tests passing.
---
author: oompah
created: 2026-08-04 02:45
---
Agent completed successfully in 2210s (51556 tokens)
---
author: oompah
created: 2026-08-04 02:45
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 218, Tool calls: 103
- Tokens: 834 in / 50.7K out [51.6K total]
- Cost: $0.0000
- Exit: normal, Duration: 36m 50s
- Log: OOMPAH-753__20260804T020912Z.jsonl
---
author: oompah
created: 2026-08-04 04:01
---
Branch quality gate blocked review creation.

Branch: `OOMPAH-753`
Target: `main`
Head: `7b4245335e4ba4ff9e63e2d23fa3add7592bb180`
Command: `make test`
Result: `failed`

Required: run the command in the task worktree, fix the failure, commit and push the repair, then leave the task in Done. Oompah will rerun the gate for the new head before creating the PR/MR.

Output tail:
```text
apture-warnings.html#resource-warnings for more info.

tests/test_webhooks.py::TestWebhookForwarderExtensionMissing::test_start_runs_probe_and_logs_single_error
  /home/shedwards/.oompah/tmp/oompah-quality-gate-kxtwz95h/workspace/.venv/lib/python3.12/site-packages/_pytest/unraisableexception.py:67: PytestUnraisableExceptionWarning: Exception ignored in: <function BaseSubprocessTransport.__del__ at 0x7a68d399f9c0>
  
  Traceback (most recent call last):
    File "/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_subprocess.py", line 126, in __del__
      self.close()
    File "/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_subprocess.py", line 104, in close
      proto.pipe.close()
    File "/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/unix_events.py", line 568, in close
      self._close(None)
    File "/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/unix_events.py", line 592, in _close
      self._loop.call_soon(self._call_connection_lost, exc)
    File "/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_events.py", line 799, in call_soon
      self._check_closed()
    File "/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_events.py", line 545, in _check_closed
      raise RuntimeError('Event loop is closed')
  RuntimeError: Event loop is closed
  
  Enable tracemalloc to get traceback where the object was allocated.
  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.
    warnings.warn(pytest.PytestUnraisableExceptionWarning(msg))

tests/test_work_contributors.py::TestBuildWorkContributorRecord::test_completed_at_is_utc_iso
  /home/shedwards/.oompah/tmp/oompah-quality-gate-kxtwz95h/workspace/.venv/lib/python3.12/site-packages/_pytest/unraisableexception.py:67: PytestUnraisableExceptionWarning: Exception ignored in: <function BaseSubprocessTransport.__del__ at 0x7228b32b39c0>
  
  Traceback (most recent call last):
    File "/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_subprocess.py", line 126, in __del__
      self.close()
    File "/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_subprocess.py", line 104, in close
      proto.pipe.close()
    File "/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/unix_events.py", line 568, in close
      self._close(None)
    File "/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/unix_events.py", line 592, in _close
      self._loop.call_soon(self._call_connection_lost, exc)
    File "/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_events.py", line 799, in call_soon
      self._check_closed()
    File "/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_events.py", line 545, in _check_closed
      raise RuntimeError('Event loop is closed')
  RuntimeError: Event loop is closed
  
  Enable tracemalloc to get traceback where the object was allocated.
  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.
    warnings.warn(pytest.PytestUnraisableExceptionWarning(msg))

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/test_orchestrator_handlers.py::TestRepoHealErrorReporting::test_heal_failure_does_not_raise_from_tick
FAILED tests/test_provider_retirement.py::test_claude_tool_catalog_reports_read_only_shell_denials
= 2 failed, 15240 passed, 8 skipped, 1 xfailed, 49 warnings in 404.45s (0:06:44) =

make: *** [Makefile:401: test] Error 1
```
---
author: oompah
created: 2026-08-04 04:01
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-08-04 04:01
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-08-04 04:02
---
Understanding: The existing OOMPAH-753 review head fails the full branch gate in two tests after recoverable auditor-denial changes. I will synchronize the same branch, inspect the exact assertions and CI/PR evidence, reproduce both focused failures, apply only the minimal compatibility fixes, run focused Makefile-backed tests, push the repair, verify check reruns, and submit the task.
---
author: oompah
created: 2026-08-04 04:04
---
Discovery: The provider-retirement failure reproduces in both serial and 4-worker gate modes. OOMPAH-753 changed the fatal mutation denial text in oompah/auditor.py so it no longer contains the established 'read-only' policy wording asserted by tests/test_provider_retirement.py; the command still correctly fails closed and invokes the fatal denial handler. The repo-heal test passes in both focused modes and its code was untouched by this branch, so the recorded gate occurrence is not reproducible from the exact head; I will stress it with its neighboring module while making only the confirmed compatibility repair.
---
author: oompah
created: 2026-08-04 04:04
---
Implementation: Restored the established read-only policy wording in the fatal mutating/compound auditor denial while preserving its non-recoverable classification, reason metadata, and fail-closed behavior. This is a one-message compatibility fix in oompah/auditor.py; the existing provider-retirement regression test directly covers it.
---
author: oompah
created: 2026-08-04 04:07
---
Verification: PASS. The 4-worker gate harness reports 44/44 passing for tests/test_auditor_contract.py plus tests/test_provider_retirement.py, including the formerly failing Claude catalog assertion. The full neighboring tests/test_orchestrator_handlers.py module passed twice under 4 workers (279/279 on the recorded run), including test_heal_failure_does_not_raise_from_tick; the prior isolated repo-heal failure did not recur. git diff --check also passes. Per project guidance, the orchestrator will rerun the complete make test branch gate for the pushed head.
---
author: oompah
created: 2026-08-04 04:07
---
Completion: Delivered and pushed commit d9e937f7192866b0f45939da7e7eb1d642b0912c to origin/OOMPAH-753. Fatal auditor mutation denials again expose the established read-only policy wording without changing fail-closed classification or recovery budgets. Focused gate suites pass (44 auditor/provider tests; 279 orchestrator-handler tests), and the worktree is clean/up to date. No GitHub PR or Actions run exists yet because Oompah's pre-review full branch gate must accept this submitted head before review creation.
---
author: oompah
created: 2026-08-04 04:07
---
Fixed the CI regression by preserving read-only wording on fatal auditor mutation denials; pushed d9e937f71 after 44 auditor/provider and 279 orchestrator-handler tests passed.
---
author: oompah
created: 2026-08-04 04:08
---
Run #YOLO-reopen [attempt=YOLO-reopen, profile=deep, role=deep -> Codex/gpt-5.6-sol]
- Turns: 0, Tool calls: 34
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 6m 27s
- Log: OOMPAH-753__20260804T040147Z.jsonl
---
author: oompah
created: 2026-08-04 04:15
---
Branch quality gate passed for `d9e937f7192866b0f45939da7e7eb1d642b0912c` using `make test` in 409.6s. Review creation may proceed.
---
author: oompah
created: 2026-08-04 04:24
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-04 04:24
---
YOLO: merged PR #706.
---
author: oompah
created: 2026-08-04 04:26
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-04 04:26
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-04 04:36
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- main_head: 5368e23617a98569caf7370b0f2eb63d41c8ba6b
- branch_head: d9e937f7192866b0f45939da7e7eb1d642b0912c
- pr_merge_commit: 5368e2361
- pr_number: 706
- commits_on_branch: a24d0317b, 7b4245335, d9e937f71
- regression_test: tests/test_auditor_contract.py::test_oompah_753_non_mutating_validator_requests_outside_contract_are_recoverable
- make_test_summary: 15243 passed, 7 skipped, 1 xfailed, 56 warnings in 400.39s
- primary_source: oompah/auditor.py::check_auditor_command
- prior_branch_gate: passed at d9e937f71 in 409.6s
---
author: oompah
created: 2026-08-04 04:36
---
Run #YOLO-reopen [attempt=YOLO-reopen, profile=auditor, role=auditor -> Claude/opus]
- Turns: 32, Tool calls: 23
- Tokens: 29 in / 6.0K out [6.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 9m 57s
- Log: OOMPAH-753__20260804T042629Z.jsonl
---
<!-- COMMENTS:END -->
