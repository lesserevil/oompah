---
id: OOMPAH-710
type: bug
status: Open
priority: null
title: Keep oversized auditor tool results inside the read-only authority boundary
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-02T23:45:39.918535Z'
updated_at: '2026-08-02T23:46:10.016766Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: f64744d5cece2f0044fdcdb2efdf7ceb2d7c11e4cc2e54b922d072574a454bd6
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 0c30d255-a080-47eb-83aa-62d29909ea42
  claim_owner: e66a0cec-af3d-4845-bbdc-4b14727350de
  claimed_at: '2026-08-02T23:46:02.953718+00:00'
  claim_expires_at: '2026-08-03T00:16:02.953718+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: ec2f0ad9-bcb8-4941-80f3-f57401c237c5
---
## Summary

Triggered by: OOMPAH-701 terminal audit audit-c521d3856622 on 2026-08-02.

Production evidence: two independent Claude completion auditors (opus and sonnet) were terminated by the bounded repeated-policy-denial guard after using the approved read_file tool on a large source file. The ACP backend persisted the oversized 1,452,395-character result under ~/.claude/projects/.../tool-results outside the read-only terminal-audit worktree and instructed the model that it MUST read that path. The strict auditor authority boundary then denied the required follow-up access. Both transports failed, OOMPAH-701 remained In Validation, terminal_audit_health:launch_failures alerted with two transport failures, and the public running-agent list was empty while terminal-audit running remained 1.

Implementation scope:
- Keep oversized read/search output needed by an auditor inside an explicitly approved read-only result channel or audit-scoped temp root; do not direct a strict auditor to provider-private paths outside its authority.
- Prefer bounded/chunked tool responses that the model can continue reading through the approved MCP surface.
- Classify repeated policy denial caused by provider output persistence precisely and continue through eligible independent transports without stranding the audit.
- Make queued/running/in-progress audit counters describe the same durable/provider lifecycle while between candidates or exhausted.
- Clear launch/transport health once the affected audit is resolved so later audits are not contaminated.

Relevant code: oompah/acp_backends/claude.py and ACP tool-result bridging/truncation; oompah/api_agent.py approved file tools; oompah/authority_boundary.py auditor policy; oompah/orchestrator.py terminal-audit retry bookkeeping; terminal-audit health snapshot code.

Required tests:
- Reproduce an auditor reading a >1 MB file and prove every continuation path remains within its approved read-only worktree/tool channel.
- Run two candidate failures followed by a healthy independent candidate and prove the audit retries and completes exactly once.
- Assert public running agents, audit queued/running counters, health in_progress_count, and process liveness agree between attempts and after exhaustion.
- Assert the transport-failure alert clears after successful recovery and does not leak into a later audit.
- Focused ACP/auditor tests and make test/check-secrets pass.

Acceptance criteria:
- A compliant read-only auditor cannot be forced into an authority denial by Oompah/provider oversized-output handling.
- OOMPAH-701-style audits either launch a visible candidate or expose a truthful queued/exhausted state, never running=1 with no provider and in_progress=0.
- Recovery completes the terminal transition and clears the alert without an owner override.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-02 23:46
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-02 23:46
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
