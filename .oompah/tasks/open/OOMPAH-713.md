---
id: OOMPAH-713
type: task
status: Open
priority: null
title: Do not terminate completion audits for harmless read-only shell syntax
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-03T00:59:11.573065Z'
updated_at: '2026-08-03T01:00:55.885956Z'
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
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 431240af-4556-427b-bca0-23054e4e63dd
  claim_owner: ac52e8ec-836b-4534-92a2-d2acfef0120b
  claimed_at: '2026-08-03T01:00:48.715625+00:00'
  claim_expires_at: '2026-08-03T01:30:48.715625+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 46d8bc34-14d8-406c-8719-4f954a6a3160
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
<!-- COMMENTS:END -->
