---
id: OOMPAH-854
type: task
status: Open
priority: null
title: Fence terminal-auditor admission during quiesce and restart drain
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-06T05:46:04.066694Z'
updated_at: '2026-08-06T05:46:16.059712Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Live reproduction at 2026-08-06T05:43Z: make restart had quiesced build fe6257b and drained the only running OOMPAH-821 auditor to an accepted Done verdict. Instead of reaching running=0, the terminal-audit scheduler launched two new provider processes for queued OOMPAH-791 and OOMPAH-852 audits while /api/v1/state still reported quiesced=true, increasing counts.running from 0 to 2 and extending the graceful cutover indefinitely. Implementation scope: apply the same dispatch-admission fence used for implementation workers to terminal-audit dequeue/claim/provider launch; atomically re-check quiesced/paused/restart state immediately before durable running transition and provider spawn; preserve queued audit records without incrementing attempts; allow already-running auditors to drain; resume queued audits exactly once after the new instance is healthy; fence quiesce versus audit completion/requeue races and direct restart with a generation/CAS so no late callback can launch after an empty drain observation. Relevant code: orchestrator terminal-audit enforcement/dequeue paths, auditor dispatch/provider launch, quiesce/restart lifecycle, running-count snapshot, and terminal audit persistence recovery. Required tests: queue two audits, quiesce as the current auditor exits, prove running reaches/stays zero and no provider/worktree launch occurs; restart and prove both preserved audits dispatch exactly once; cover audit retry/requeue racing quiesce, paused startup, failed provider launch, direct force-independent lifecycle recovery, and dashboard counts. Acceptance criteria: once quiesced, no new auditor can enter running or create a provider process; graceful restart time is bounded only by work already running at quiesce; queued audits survive and resume naturally on the healthy new instance; focused lifecycle/auditor tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

