---
id: OOMPAH-816
type: task
status: Open
priority: null
title: Serialize heavyweight auditor validation with exact quality gates
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-05T00:38:32.940940Z'
updated_at: '2026-08-05T00:39:51.266493Z'
work_branch: epic-OOMPAH-763--task-OOMPAH-816
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: a3b09053b57c13511868aae9880d1dd498d09e7a9890e0decc3294148e57bf88
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: f78a5c36-c469-4e59-8622-b0aa4bcf9f12
  claim_owner: 209db773-bcba-4efb-b625-7acd11d20c5f
  claimed_at: '2026-08-05T00:39:21.379072+00:00'
  claim_expires_at: '2026-08-05T01:09:21.379072+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: eedd2876-22b5-4ed4-a8c6-71ca05c452fe
oompah.work_branch: epic-OOMPAH-763--task-OOMPAH-816
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-763--task-OOMPAH-816
  base_branch: epic-OOMPAH-763
  base_sha: 30dc2b2075a48c6c542da55a46ad0285f492d527
  updated_at: '2026-08-05T00:39:45.354876+00:00'
---
## Summary

Live reproduction on 2026-08-05: while the exact OOMPAH-813 four-worker combined-tree gate was running in isolated gate root oompah-quality-gate-cnd_e1it, the OOMPAH-508 completion auditor independently launched make test-serial in its audit attempt worktree. Both full pytest trees then had workers/processes blocked in jbd2_log_wait_commit. The preceding OOMPAH-807 and OOMPAH-814 gates each passed more than 15,000 tests but lost one unrelated five-second fixture under similar load. OOMPAH-814 fixes concrete leaky fixtures and OOMPAH-809 reserves scheduler/provider lanes; neither arbitrates host CPU/disk consumed by heavyweight commands after agents launch. Implementation scope: introduce a process-safe, restart-safe host/project validation resource lease shared by BranchQualityGate and auditor MCP run_command execution. Classify full Makefile gates/test/test-serial and equivalent complete-suite commands as heavyweight without blocking bounded read-only/focused audit checks. Exact integration/review gates should own the authoritative lane; auditor heavyweight work waits with durable informational state and resumes fairly, or reuses exact compatible gate evidence when policy permits. Preserve command timeouts, cancellation, output delivery, audit independence, multi-project fairness, and never terminate an unrelated running gate. Expose current owner, waiter count/age, and capacity disposition without actionable warnings for normal waits. Required tests: auditor full suite concurrent with exact gate; two projects; restart with held/waiting lease; owner crash/expiry; cancellation; focused commands continue; exact compatible evidence reuse; fairness/no starvation; and proof no concurrent heavyweight pytest trees launch. Acceptance: the service never oversubscribes configured heavyweight validation capacity, exact gates cannot fail because a completion auditor launched a competing full suite, and normal capacity waits clear automatically.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-05 00:39
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-05 00:39
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
