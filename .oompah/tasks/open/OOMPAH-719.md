---
id: OOMPAH-719
type: bug
status: Open
priority: 1
title: Keep oversized auditor run_command output inside the authority boundary
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-03T14:01:56.950921Z'
updated_at: '2026-08-03T14:02:30.804630Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 9a37eb9b4c7585618306f307644e8e4d19b95e34cc765b76f0d9d0ddd57fa9e5
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: d7f7160e-d77d-42fe-8bc6-cd46ab466ab1
  claim_owner: 2dcc53e1-cdcd-4522-a08d-de6ce4222a8c
  claimed_at: '2026-08-03T14:02:20.649537+00:00'
  claim_expires_at: '2026-08-03T14:32:20.649537+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: a1b015a9-b482-4b4b-9c7d-766cca6bc6a4
---
## Summary

Production reproduction on current main b97187ab (2026-08-03): EXOCOMP-171 terminal audit audit-bad47351b510, attempt attempt-180165c919ab, correctly invoked the project configured make test command. The Claude transport persisted the oversized command result under ~/.claude/projects/.../tool-results and told the auditor to read that provider-private absolute path. The auditor then attempted grep/tail against that path, the strict read-only authority boundary denied it repeatedly, and the otherwise-valid completion audit was terminated. NODEVIRT-8 audit retries are also exhausting on policy denials. OOMPAH-710 covers oversized read_file/search responses, but not oversized output from an allowed run_command, so this remains reproducible after OOMPAH-710/713/716 are deployed.

Implementation scope:
- Bound and page output from configured auditor run_command invocations before provider transport, including make test and other approved Makefile gates.
- Keep every continuation inside the approved MCP result channel or an audit-scoped read-only temp root; never expose or instruct the model to read ~/.claude/provider-private result paths.
- Provide an approved continuation/read-result operation for truncated command output, and make the completion-auditor prompt use it instead of grep, pipes, or arbitrary absolute paths.
- Preserve accurate policy-incompatibility classification, candidate rotation, lifecycle counters, and alert clearing when a candidate encounters a provider output persistence failure.

Relevant code/context: oompah/acp_backends/claude.py; ACP run_command result bridging and truncation; oompah/api_agent.py; oompah/authority_boundary.py; terminal-audit retry/health bookkeeping in oompah/orchestrator.py and server snapshots.

Required tests:
- Reproduce more than 1 MB of output from an allowed configured run_command under the Claude transport and prove every continuation stays within the audit authority boundary.
- Prove the auditor can page/search the saved result through an approved read-only tool and submit a verdict without a policy denial.
- Cover candidate rotation after a forced continuation failure, exact queued/running/process-liveness counters, and clearing transport/policy alerts after recovery.
- Run focused ACP/auditor suites and the project Makefile gate.

Acceptance criteria:
- Large output from an allowed audit test command can never force a compliant auditor toward a provider-private path or disallowed shell pipeline.
- The live EXOCOMP-171/NODEVIRT-8 failure class completes through ordinary independent auditing without owner override.
- Audit lifecycle counters and web alerts remain truthful during retry and clear after resolution.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-03 14:02
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-03 14:02
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
