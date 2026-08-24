---
id: OOMPAH-1333
type: task
status: Backlog
priority: null
title: OpenCode auditor cannot call submit_audit_result (oompah tools not injected
  into opencode run), so verdicts never finalize
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-24T21:06:31.866816Z'
updated_at: '2026-08-24T21:06:31.866816Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: aa0aa824-890f-4f81-8ef4-0c789e2d39af
  request_fingerprint: 20e48022221d5b75041780a786cbfbd171aefb30c6edf0543eb5b5506a5fdd9d
---
## Summary

### Problem
After OOMPAH-1332 fixed the policy-denial loop (opencode 'run --auto' now auto-approves the auditor's read-only inspection, and native denials escalate through policy_denial_handler), OpenCode-provider completion audits still never finalize a verdict. The auditor now runs its inspection successfully (dozens of bash/read tool calls, no denials, transport_failure_count=0, policy_incompatibility_count=0) but then 'exits (normal) without a result', is classified as a finalization_failure, and retries indefinitely — keeping workflow_liveness in restart_overdue and fencing all non-terminal work (64 Ready to Integrate, etc.).

### Root cause
The OpenCode ACP backend builds the oompah tool catalog (including the result tool 'submit_audit_result' plus read_file/list_files/search_files/read_command_output/run_command) but NEVER injects those tools into the 'opencode run' subprocess. In oompah/acp_backends/opencode.py the catalog is only emitted as an observability label ('tool_policy': 'opencode:tool_catalog', 'tool_catalog': tool_names) and the actual command is:
    opencode run --format json --auto [--model M] <prompt>
So the opencode agent only has opencode's OWN native tools; the oompah tools are not callable. The auditor therefore cannot invoke submit_audit_result and instead hallucinates a nonexistent submission path.

### Live evidence (build 0682f1e8e)
Agent log OOMPAH-1201__20260824T205215Z.jsonl:
- session_start tool_catalog lists ['read_file','list_files','search_files','read_command_output','run_command','submit_audit_result'] but these are labels only.
- The auditor emits a native 'task' tool call trying to 'Submit auditor verdict', then acp_text: 'I can't submit the auditor verdict: in this environment there's no submit_audit_result/completion-auditor submission command available (the tool call failed with "No oompah completion-auditor CLI command exists").'
- Task comments: 'Auditor attempt ended: auditor exited (normal) without a result. A different independent auditor will be tried on the next scheduler tick.' (repeats)
- terminal_audit_health: degraded=true, finalization_failure_count>0, transport_failure_count=0, policy_incompatibility_count=0.

Contrast: Claude bridges oompah tools via an in-process MCP server (create_sdk_mcp_server, mcp__oompah__*), and Codex via its bridged catalog / native read-only sandbox; both can call the result tool. OpenCode's one-shot 'run' has no equivalent tool injection.

### Investigation scope
- Determine how to expose oompah's tool callables (especially submit_audit_result and the read-only inspection tools) to the opencode agent. Options to evaluate:
  (a) Run an oompah MCP server and use 'opencode run --attach <server>' / opencode MCP config so mcp__oompah__* tools (incl. submit_audit_result) are callable, mirroring the Claude bridge.
  (b) Provide an oompah CLI/command the opencode agent can invoke to submit the verdict (e.g. a real 'oompah completion-auditor submit ...' path bound to audit_result_handler), since the agent already tried a CLI.
  (c) If neither is feasible, make the OpenCode backend ineligible for the auditor role (auditor candidate selector skips backend=opencode) and fail closed with an actionable configuration error instead of infinite finalization_failure retries.
- Ensure a bounded outcome: an auditor that cannot emit a verdict must escalate (policy/config incompatibility, action_required) rather than loop as transient finalization_failure forever.

### Tests
- OpenCode auditor session can call submit_audit_result (or the chosen submission path) and the verdict is accepted/finalized.
- If OpenCode is made ineligible for auditor, candidate selection excludes it and a clear configuration alert is raised; no infinite retry.
- Regression: 'exited normal without a result' does not loop unbounded; after N such attempts the audit escalates action_required.

### Acceptance Criteria
- OpenCode-provider completion audits either finalize a real verdict (submit_audit_result callable) or the backend is cleanly excluded from the auditor role with an actionable alert.
- terminal_audit_health.finalization_failure_count stops climbing; audits no longer loop 'without a result'.
- With verdicts finalizing (or an independent non-OpenCode auditor selected), restart reconstruction converges (scan_complete=true) and fenced non-terminal work is admitted.
- No regression for Claude/Codex auditors.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

