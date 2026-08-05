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
updated_at: '2026-08-05T00:38:37.873309Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Live reproduction on 2026-08-05: while the exact OOMPAH-813 four-worker combined-tree gate was running in isolated gate root oompah-quality-gate-cnd_e1it, the OOMPAH-508 completion auditor independently launched make test-serial in its audit attempt worktree. Both full pytest trees then had workers/processes blocked in jbd2_log_wait_commit. The preceding OOMPAH-807 and OOMPAH-814 gates each passed more than 15,000 tests but lost one unrelated five-second fixture under similar load. OOMPAH-814 fixes concrete leaky fixtures and OOMPAH-809 reserves scheduler/provider lanes; neither arbitrates host CPU/disk consumed by heavyweight commands after agents launch. Implementation scope: introduce a process-safe, restart-safe host/project validation resource lease shared by BranchQualityGate and auditor MCP run_command execution. Classify full Makefile gates/test/test-serial and equivalent complete-suite commands as heavyweight without blocking bounded read-only/focused audit checks. Exact integration/review gates should own the authoritative lane; auditor heavyweight work waits with durable informational state and resumes fairly, or reuses exact compatible gate evidence when policy permits. Preserve command timeouts, cancellation, output delivery, audit independence, multi-project fairness, and never terminate an unrelated running gate. Expose current owner, waiter count/age, and capacity disposition without actionable warnings for normal waits. Required tests: auditor full suite concurrent with exact gate; two projects; restart with held/waiting lease; owner crash/expiry; cancellation; focused commands continue; exact compatible evidence reuse; fairness/no starvation; and proof no concurrent heavyweight pytest trees launch. Acceptance: the service never oversubscribes configured heavyweight validation capacity, exact gates cannot fail because a completion auditor launched a competing full suite, and normal capacity waits clear automatically.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

