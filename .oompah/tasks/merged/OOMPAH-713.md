---
id: OOMPAH-713
type: task
status: Merged
priority: null
title: Do not terminate completion audits for harmless read-only shell syntax
parent: null
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-710
labels: []
assignee: null
created_at: '2026-08-03T00:59:11.573065Z'
updated_at: '2026-08-03T02:23:59.633202Z'
work_branch: OOMPAH-713
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/673
review_number: '673'
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 83b22617bbe0d0a84d3ab9d7fda32fbe2344e8a7fec6be711ffed1420494f147
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-03T01:01:18.331725+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: OOMPAH-713 is a unique root-cause issue addressing auditor\
    \ shell-command policy classification in authority_boundary.py and policy-denial\
    \ vs transport-failure accounting in orchestrator.py. The task corpus includes\
    \ many completed tasks on tracker integration, GitHub intake, and epic workflows,\
    \ but none address completion auditor command validation or the specific policy-denial\
    \ recovery mechanism required here. This is a novel implementation scope triggered\
    \ by OOMPAH-709 and promoted to Open by the project owner.\nLooking at the task\
    \ OOMPAH-713 and comparing it against the current project task corpus, I need\
    \ to determine if this is a duplicate of an existing active issue.\n\n## Analysis\n\
    \n**OOMPAH-713 Description:**\n- Root-cause follow-up from OOMPAH-709 completion\
    \ audit failures\n- Issue: Harmless read-only shell commands (`git branch -a --contains\
    \ <sha> | head -30`, `git log ... 2>&1 | head -5`, `grep -n <patterns> <file>`)\
    \ are incorrectly denied as \"mutating or compound shell command\"\n- Impact:\
    \ Policy denials exhaust auditor limits, terminate sessions, get recorded as transport\
    \ failures, raise false alerts\n- Scope: Distinguish read-only syntax from mutations\
    \ in authority_boundary.py; prevent policy denials from consuming transport budget;\
    \ allow auditor recovery\n\n**Task Corpus Review:**\n\nExamining all tasks in\
    \ the provided corpus:\n- **Terminal state tasks** (Archived): OOMPAH-1, 10-15,\
    \ 100-175\n  - None of these address shell command validation in the auditor context\n\
    \  - None concern authority_boundary.py policy classification\n  - None address\
    \ the policy-denial vs transport-failure distinction\n  \n- **Active tasks**:\
    \ Only OOMPAH-713 itself is listed as Open\n\nThe corpus includes completed work\
    \ on:\n- Tracker bugs (OOMPAH-10, 160)\n- GitHub intake issues (OOMPAH-11, 12,\
    \ 13, 14, 158, 159)\n- Error watching (OOMPAH-15, 156)\n- Epic workflow (OOMPAH-166-175)\n\
    - Dashboard features (OOMPAH-12, 13)\n\n**None of these tasks** address:\n1. Completion\
    \ auditor shell command policy classification\n2. Read-only compound command validation\n\
    3. Recovery from policy denials without terminating audits\n4. Health metrics\
    \ distinguishing policy incompatibility from transport failure\n\nThis is a unique,\
    \ specific root-cause issue that originated from OOMPAH-709 and was promoted to\
    \ Open by the project owner. There is no prior completed task covering this auditor\
    \ policy scope.\n\n---\n\nFocus handoff: duplicate_detector\n\nDuplicate preflight\
    \ verdict: no_duplicate\n\nMatches: none\n\nEvidence: OOMPAH-713 is a unique root-caus"
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
oompah.task_costs:
  total_input_tokens: 48
  total_output_tokens: 8785
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 1368
      cost_usd: 0.0
    unknown:
      input_tokens: 38
      output_tokens: 7417
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1368
    cost_usd: 0.0
    recorded_at: '2026-08-03T01:01:18.330934+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 38
    output_tokens: 7417
    cost_usd: 0.0
    recorded_at: '2026-08-03T02:20:19.843743+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-713__20260803T010056Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-713
    source_sha: 8b6f368252e653d56f0c1c9a07da0fc825a9cb10
    completed_at: '2026-08-03T01:01:18.338134+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-713
  head_sha: ac442ca4573e98fed6057b84c65b9113d1913ed7
  submitted_at: '2026-08-03T01:47:19.078322+00:00'
  updated_at: '2026-08-03T01:47:19.078322+00:00'
oompah.start_blocked_by: *id001
oompah.review_url: https://github.com/lesserevil/oompah/pull/673
oompah.review_number: '673'
oompah.work_branch: OOMPAH-713
oompah.target_branch: main
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-44ba399a4290: '2026-08-03T02:20:04.706736+00:00'
    attempt-b78a8f23c4bc: '2026-08-03T02:23:36.477914+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-713
    target_state: Done
    evidence_fingerprint: 13d704910879f223de0b07d61ce68830eb3a0df352d0e37c95e1c52bd84531d0
    audit_ids:
    - audit-28a9455c87c2
    kind: result
    applied: true
    retired_at: '2026-08-03T02:20:04.706746+00:00'
  - project_id: proj-14849f1b
    task_id: OOMPAH-713
    target_state: Merged
    evidence_fingerprint: 13d704910879f223de0b07d61ce68830eb3a0df352d0e37c95e1c52bd84531d0
    audit_ids:
    - audit-01088260c2be
    kind: result
    applied: true
    retired_at: '2026-08-03T02:23:36.477928+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-713
    audit_id: audit-28a9455c87c2
    attempt_id: attempt-44ba399a4290
    target_state: Done
    evidence_fingerprint: 13d704910879f223de0b07d61ce68830eb3a0df352d0e37c95e1c52bd84531d0
    status: In Validation
    audit_ids:
    - audit-28a9455c87c2
    applied: true
    created_at: '2026-08-03T02:20:04.706759+00:00'
    applied_at: '2026-08-03T02:20:08.716122+00:00'
  - project_id: proj-14849f1b
    task_id: OOMPAH-713
    audit_id: audit-01088260c2be
    attempt_id: attempt-b78a8f23c4bc
    target_state: Merged
    evidence_fingerprint: 13d704910879f223de0b07d61ce68830eb3a0df352d0e37c95e1c52bd84531d0
    status: Merged
    audit_ids:
    - audit-01088260c2be
    applied: true
    created_at: '2026-08-03T02:23:36.477942+00:00'
    applied_at: '2026-08-03T02:23:43.101133+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-28a9455c87c2
    project_id: proj-14849f1b
    task_id: OOMPAH-713
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 13d704910879f223de0b07d61ce68830eb3a0df352d0e37c95e1c52bd84531d0
    attempts:
    - version: 1
      attempt_id: attempt-44ba399a4290
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 13d704910879f223de0b07d61ce68830eb3a0df352d0e37c95e1c52bd84531d0
      created_at: '2026-08-03T02:16:49.648262+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-03T02:16:49.648262+00:00'
      branch_key: OOMPAH-713
      verdict: pass
      completed_at: '2026-08-03T02:20:04.706605+00:00'
      ended_at: '2026-08-03T02:20:04.706605+00:00'
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-03T02:15:32.584140+00:00'
    updated_at: '2026-08-03T02:20:04.706605+00:00'
  - version: 1
    audit_id: audit-01088260c2be
    project_id: proj-14849f1b
    task_id: OOMPAH-713
    target_state: Merged
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 13d704910879f223de0b07d61ce68830eb3a0df352d0e37c95e1c52bd84531d0
    attempts:
    - version: 1
      attempt_id: attempt-b78a8f23c4bc
      target_state: Merged
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 13d704910879f223de0b07d61ce68830eb3a0df352d0e37c95e1c52bd84531d0
      created_at: '2026-08-03T02:20:27.088592+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-03T02:20:27.088592+00:00'
      branch_key: OOMPAH-713
      verdict: pass
      completed_at: '2026-08-03T02:23:36.477799+00:00'
      ended_at: '2026-08-03T02:23:36.477799+00:00'
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-03T02:15:32.584140+00:00'
    updated_at: '2026-08-03T02:23:36.477799+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-44ba399a4290
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 13d704910879f223de0b07d61ce68830eb3a0df352d0e37c95e1c52bd84531d0
    created_at: '2026-08-03T02:16:49.648262+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-03T02:16:49.648262+00:00'
    branch_key: OOMPAH-713
  - version: 1
    attempt_id: attempt-b78a8f23c4bc
    target_state: Merged
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 13d704910879f223de0b07d61ce68830eb3a0df352d0e37c95e1c52bd84531d0
    created_at: '2026-08-03T02:20:27.088592+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-03T02:20:27.088592+00:00'
    branch_key: OOMPAH-713
---
## Summary

Triggered by OOMPAH-709 completion audit attempts attempt-5cfed9c3692c and attempt-bf4a7d3278be on 2026-08-03. Both auditors correctly inspected the detached exact-head workspace, but harmless read-only commands such as `git branch -a --contains <sha> | head -30`, `git log ... 2>&1 | head -5`, and `grep -n <patterns> <file>` were returned as `auditor capability policy denied a mutating or compound shell command`. The denials counted against the auditor policy-denial limit, forcibly stopped the sessions, were recorded as transport failures, raised the terminal-audit launch-failure alert, and left the already-merged task In Validation until an owner override. No code-defect verdict was produced.\n\nImplementation scope:\n- Distinguish demonstrably read-only compound shell syntax from mutation attempts, or reject it as a recoverable tool-validation response that does not consume the fatal policy-denial transport budget.\n- Keep all actual mutation, redirection-to-file, state-changing git, process-control, and shell-escape paths fail-closed.\n- Ensure the completion-auditor prompt/tool catalog clearly directs search work to search_files and bounded reads when raw grep/pipelines are unsupported.\n- Do not classify an authority-policy rejection as an auditor transport outage; terminal-audit health must identify policy/tool incompatibility separately from unavailable provider transport.\n- Allow the auditor to recover from a denied read-only command and still submit a verdict.\n\nRelevant code: oompah/authority_boundary.py command classification, oompah/auditor_tools.py run_command/search_files schemas, oompah/orchestrator.py auditor policy-denial handling and transport-failure accounting, terminal-audit prompts, and dashboard health aggregation.\n\nRequired tests:\n- Reproduce both OOMPAH-709 command forms and prove they cannot exhaust a completion audit merely for read-only syntax.\n- Verify the agent can receive a validation response, use search_files/run_command safely, and submit an audit verdict.\n- Mutating commands, output redirection, chained mutation, and state-changing git remain denied and terminate or escalate according to policy.\n- Policy incompatibility does not increment transport-failure health counters; genuine provider transport failures still do.\n- Candidate rotation and alert clearing remain correct.\n\nAcceptance criteria:\n- Replaying either OOMPAH-709 audit trace reaches submit_audit_result without an owner override.\n- No write-capable shell command is admitted.\n- The UI no longer reports a provider transport outage for a local authority-policy denial.\n- Focused authority-boundary, auditor-tool, terminal-audit, orchestrator, and health tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-03 01:00
---
Project-owner promoted this root-cause follow-up to Open. Live evidence is preserved in OOMPAH-709 audit logs OOMPAH-709__20260803T005429Z.jsonl and OOMPAH-709__20260803T005655Z.jsonl; implementation must remain fail-closed for genuine mutations while preventing local policy/tool incompatibility from masquerading as provider transport failure.
---
author: oompah
created: 2026-08-03 01:00
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-03 01:00
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-03 01:01
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.4K out [1.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 26s
- Log: OOMPAH-713__20260803T010056Z.jsonl
---
author: oompah
created: 2026-08-03 01:01
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-03 01:01
---
Focus: Frontend Developer
---
author: oompah
created: 2026-08-03 01:02
---
Understanding: I will trace the authority-boundary command classifier, auditor tool validation/recovery, orchestrator policy-denial accounting, and terminal-audit health aggregation. I will preserve fail-closed mutation protections, make harmless read-only syntax recoverable with safe search/read guidance, add regression coverage for the OOMPAH-709 forms and transport-vs-policy health behavior, then run focused Makefile-backed checks.
---
author: oompah
created: 2026-08-03 01:03
---
Discovery: check_auditor_command() currently treats all shell separators, redirections, and shell metacharacters as the same fatal auditor policy denial. This rejects the OOMPAH-709 read-only pipelines and causes _record_auditor_policy_denial() to exhaust the three-denial retirement budget. I am tracing the structured failure/health paths to introduce a recoverable policy-validation classification while retaining fail-closed mutation checks.
---
author: oompah
created: 2026-08-03 01:09
---
Implementation: Added recoverable AuditorCommandDenial metadata for unsupported read-only shell separators, skipped those denials in API/ACP/orchestrator fatal-budget callbacks, and kept mutation/shell-escape/file-redirection paths fail-closed. Fatal policy exhaustion now records FailureClassification.POLICY_INCOMPATIBILITY, with dedicated health counters/alerts and dashboard wording distinct from transport outages. Auditor prompts and both tool catalogs now prefer bounded read_file/search_files and separate run_command calls.
---
author: oompah
created: 2026-08-03 01:11
---
Verification: after fixing an initial regex compilation error, the focused authority/auditor/health/coordinator/dashboard suites pass 341 tests. Recoverable OOMPAH-709 pipeline denials do not invoke the fatal callback; safe search/run calls and bounded reads continue successfully; policy incompatibility health is separate from transport health.
---
author: oompah
created: 2026-08-03 01:16
---
Verification complete: focused authority/auditor/health/coordinator/dashboard suites pass 341 tests; neighboring auditor dispatch (13), terminal-audit core (28), health API/dashboard (14), observability (18), and orchestrator handlers (277) pass. Terminal mutation scan passes (6 identified, 6 allowlisted). make test-setup remains unavailable only because uv transient-scope creation fails with the container DBus/kernel-thread error.
---
author: oompah
created: 2026-08-03 01:17
---
Implemented recoverable read-only auditor shell validation, preserved fail-closed mutation controls, separated policy incompatibility from transport health, updated auditor catalogs/prompts/dashboard, and added regression coverage.
---
author: oompah
created: 2026-08-03 01:17
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 130
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 15m 51s
- Log: OOMPAH-713__20260803T010140Z.jsonl
---
author: oompah
created: 2026-08-03 01:44
---
Direct owner is rebasing the submitted auditor-policy fix onto newly merged OOMPAH-710 to preserve both bounded read-tool behavior and recoverable read-only policy validation. I will also add the missing end-to-end tool-session regression proving a recoverable denial can be followed by submit_audit_result.
---
author: oompah
created: 2026-08-03 01:47
---
Direct owner rebase complete at exact head ac442ca4573e98fed6057b84c65b9113d1913ed7 on merged OOMPAH-710. Conflict resolution preserves offset/limit chunked reads across all provider tool schemas and keeps recoverable read-only command validation. Added an end-to-end regression that receives the validation error, continues with safe tools, and successfully submits an accepted audit verdict. Combined 710+713 focused suites: 433 passed; make check-secrets passed.
---
author: oompah
created: 2026-08-03 01:47
---
Rebased onto merged bounded-read implementation, preserved both behaviors, and added accepted-verdict recovery coverage.
---
author: oompah
created: 2026-08-03 02:06
---
Branch quality gate passed for `ac442ca4573e98fed6057b84c65b9113d1913ed7` using `make test` in 423.9s. Review creation may proceed.
---
author: oompah
created: 2026-08-03 02:07
---
Completion-audit guidance while this fix is not yet deployed: use approved read_file, list_files, search_files, and simple single read-only run_command calls only. Do not use grep, pipes, redirection, command chaining, or whole-file reads. Exact submitted head ac442ca4573e98fed6057b84c65b9113d1913ed7 passed the combined 433-test affected suite and make check-secrets.
---
author: oompah
created: 2026-08-03 02:15
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-03 02:15
---
YOLO: merged PR #673.
---
author: oompah
created: 2026-08-03 02:16
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-03 02:16
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-03 02:20
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- head_sha: ac442ca4573e98fed6057b84c65b9113d1913ed7
- merge_commit: 7e6974c3c (PR #673 into origin/main)
- recoverable_reason_marker: auditor_read_only_shell_syntax
- new_failure_classification: policy_incompatibility
- new_health_field: policy_incompatibility_count
- focused_authority_tests: 144 passed
- focused_auditor_contract_tests: 15 passed
- focused_terminal_audit_health_tests: 44 passed
- focused_terminal_transition_tests: 122 passed
- focused_auditor_dispatch_tests: 14 passed
- focused_terminal_audit_observability_tests: 19 passed
- focused_dashboard_health_tests: 16 passed
- focused_acp_tool_output_tests: 4 passed
---
author: oompah
created: 2026-08-03 02:20
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 42, Tool calls: 32
- Tokens: 38 in / 7.4K out [7.5K total]
- Cost: $0.0000
- Exit: normal, Duration: 3m 29s
- Log: OOMPAH-713__20260803T021656Z.jsonl
---
author: oompah
created: 2026-08-03 02:20
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-03 02:20
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-03 02:23
---
Audit PASS — Merged

[REDACTED]

Safe evidence:
- head_sha: ac442ca4573e98fed6057b84c65b9113d1913ed7
- merge_commit: 7e6974c3c
- pr_number: 673
- recoverable_reason_marker: auditor_read_only_shell_syntax
- new_failure_classification: policy_incompatibility
- new_health_field: policy_incompatibility_count
- focused_authority_boundary_tests: 144 passed
- focused_auditor_contract_tests: 15 passed
- focused_terminal_audit_health_tests: 44 passed
- focused_terminal_transition_coordinator_tests: 122 passed
- live_denial_observed: recoverable Error with reason=auditor_read_only_shell_syntax during audit
---
author: oompah
created: 2026-08-03 02:23
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 45, Tool calls: 33
- Tokens: 35 in / 6.0K out [6.0K total]
- Cost: $0.0000
- Exit: normal, Duration: 3m 27s
- Log: OOMPAH-713__20260803T022035Z.jsonl
---
<!-- COMMENTS:END -->
