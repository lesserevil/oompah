---
id: OOMPAH-713
type: task
status: In Progress
priority: null
title: Do not terminate completion audits for harmless read-only shell syntax
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-03T00:59:11.573065Z'
updated_at: '2026-08-03T01:09:28.191621Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
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
oompah.agent_run_id: b73e1306-647d-4a61-81fa-f23488f5f91c
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 1368
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 1368
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1368
    cost_usd: 0.0
    recorded_at: '2026-08-03T01:01:18.330934+00:00'
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
<!-- COMMENTS:END -->
