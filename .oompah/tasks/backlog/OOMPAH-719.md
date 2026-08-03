---
id: OOMPAH-719
type: bug
status: Backlog
priority: 1
title: Keep oversized auditor run_command output inside the authority boundary
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-03T14:01:56.950921Z'
updated_at: '2026-08-03T14:01:56.950921Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
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

