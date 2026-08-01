---
id: OOMPAH-687
type: task
status: In Progress
priority: null
title: Isolate branch-gate runtime from task worktree environments
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-01T23:00:54.291962Z'
updated_at: '2026-08-01T23:04:36.150663Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: ffd42ada9b286512cc865307feb964a72bc954abe5d14f511ce7f0407ad28b23
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-01T23:04:16.018806+00:00'
  matched_identifiers: []
  evidence: "Based on my comprehensive search of the task tracker, I have completed\
    \ my duplicate investigation for OOMPAH-687.\n\n## Investigation Summary\n\nI\
    \ searched systematically through the oompah task tracker for any existing active\
    \ (open or backlog) tasks that might duplicate OOMPAH-687's scope:\n\n**Search\
    \ Coverage:**\n- All `.oompah/tasks/` directories (open, backlog, merged, archived)\n\
    - Keywords: venv, worktree, editable, sandbox, quality_gate, branch-gate, smoke\
    \ tests, test-setup, make, provider, agent, environment, python, isolation, concurrent,\
    \ immutable, workspace, and references to OOMPAH-683/684\n- File pattern searches\
    \ across the repository\n\n**Results:**\n- **Open tasks**: 1 task found (OOMPAH-281)\
    \ \u2014 about containerized GitHub Actions runners, unrelated to venv/worktree\
    \ isolation\n- **Backlog tasks**: 1 task found (OOMPAH-282) \u2014 about a Unicode\
    \ encoding error in state branch migration, unrelated\n- **Merged/Archived tasks**:\
    \ Reviewed samples; none address the branch-gate runtime isolation problem\n-\
    \ **References to OOMPAH-683/684**: No existing task files; these appear to be\
    \ incident identifiers mentioned in context only\n\nOOMPAH-687 addresses a unique\
    \ problem: ensuring the quality-gate trusted Python/CLI runtime remains immutable\
    \ to concurrent task worktrees, preventing `uv` from rewriting the service venv's\
    \ editable install mappings. This specific isolation issue has not been captured\
    \ in an existing active task.\n\n---\n\n**Focus handoff: duplicate_detector**\n\
    \n**Duplicate preflight verdict: no_duplicate**\n\n**Matches: none**\n\n**Evidence:**\
    \ Searched all task states across .oompah/tasks (open, backlog, merged, archived)\
    \ using 12+ keywords covering venv/worktree isolation, quality gates, provider\
    \ setup, and Makefile infrastructure. Found OOMPAH-281 (GitHub Actions runners,\
    \ unrelated) and OOMPAH-282 (Unicode encoding, unrelated). No references to OOMPAH-683/684\
    \ as task files; no existing active or completed tasks cover the branch-gate runtime\
    \ isolation problem described in OOMPAH-"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 48514e94-4986-43f1-8bd9-e096dfb5a273
oompah.task_costs:
  total_input_tokens: 250
  total_output_tokens: 6063
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 250
      output_tokens: 6063
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 250
    output_tokens: 6063
    cost_usd: 0.0
    recorded_at: '2026-08-01T23:04:16.017591+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-687__20260801T230204Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-687
    source_sha: 3d50e86c334e8a6318b767b281bc254fa6d93cc2
    completed_at: '2026-08-01T23:04:16.030188+00:00'
---
## Summary

Context\nWhile recovering OOMPAH-683/684 on 2026-08-01, a managed task worktree contained a thin .venv/bin/python wrapper that resolved to the service checkout's .venv. Running the task worktree's normal make test-setup caused uv to rewrite the service venv editable install from /home/shedwards/src/oompah to the OOMPAH-684 worktree. The branch-quality sandbox later mounted that service-owned venv as its trusted runtime, but the editable .pth target was outside the sandbox. Eight tests/test_installed_cli_smoke.py commands then failed on the otherwise-valid OOMPAH-683 head. Reinstalling the service checkout through make test-setup restored the editable path and all 13 current-install CLI smoke tests passed.\n\nImplementation scope\n- Make the quality-gate trusted Python/CLI runtime immutable to task worktrees and concurrent agent setup. A managed worktree must never cause uv/pip to rewrite the service venv's editable source mapping.\n- Audit task-worktree .venv creation/wrappers, Makefile setup discovery, provider environment inheritance, BranchQualityGate._sandbox_command runtime binds, and the current-install CLI smoke fixture.\n- Give workers either a real task-private test environment or a read-only trusted environment with setup targets safely disabled. Do not use a writable wrapper that makes uv select the operator/service venv.\n- Before every branch gate, validate that the mounted trusted runtime imports oompah from the deployed service checkout or from the exact immutable candidate mapping. Classify a mismatched editable mapping as executor/runtime corruption, repair or replace it safely, and do not report it as candidate CI failure.\n- Preserve gate isolation: candidate code must not gain write access to the service venv, operator checkout, credentials, or lifecycle state.\n- Add diagnostics that identify the expected and actual editable source roots without exposing secrets.\n\nRelevant code and tests\n- Makefile setup/test-setup targets and generated worktree runtime helpers.\n- oompah/quality_gate.py snapshot/runtime bind construction.\n- ProjectStore/workspace/provider setup that prepares task worktrees.\n- tests/test_quality_gate.py, tests/test_makefile_setup.py, tests/test_installed_cli_smoke.py, plus provider/worktree tests.\n\nAcceptance criteria\n- Running make test-setup from two task worktrees concurrently cannot change the service venv's editable source mapping.\n- A branch gate always executes its installed CLI against the exact candidate head using an immutable trusted runtime.\n- A deliberately poisoned service editable mapping is detected and recovered or reported as infrastructure failure, never as task CI failure.\n- The OOMPAH-683 eight-smoke-test reproduction passes deterministically under concurrent task gates.\n- Focused quality-gate/worktree/setup tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-01 23:01
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-01 23:01
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-01 23:04
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 65, Tool calls: 30
- Tokens: 250 in / 6.1K out [6.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 20s
- Log: OOMPAH-687__20260801T230204Z.jsonl
---
author: oompah
created: 2026-08-01 23:04
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-01 23:04
---
Focus: Callback Auth Validation Specialist
---
<!-- COMMENTS:END -->
