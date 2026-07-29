---
id: OOMPAH-538
type: task
status: Backlog
priority: null
title: Make spawned-agent task handoffs authenticate without exposing service credentials
parent: null
children: []
blocked_by: []
labels:
- needs:backend
- needs:test
assignee: null
created_at: '2026-07-29T00:37:23.786577Z'
updated_at: '2026-07-29T00:37:46.580348Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Production follow-up from OOMPAH-469. A spawned Codex implementation worker completed, committed, and pushed commit 4ee93839f, then followed the project bootstrap instruction to run 'oompah task set-status OOMPAH-469 Done --project proj-14849f1b'. The command returned HTTP 401 Unauthorized because the worker session lacked usable task-service authentication. The task stayed Open and was redundantly dispatched again after restart until an operator repaired the handoff.\n\nImplementation scope:\n- Provide spawned agents a safe supported way to execute their authorized oompah task comments/status handoff. Prefer server-owned/session-scoped task tooling or narrowly scoped credentials; do not expose the operator's reusable HTTP password to untrusted task content or the repository.\n- Ensure generated prompts/bootstrap instructions select the working handoff path in ACP/API/subprocess provider modes.\n- Treat an implementation that pushed successfully but cannot update the tracker as an observable handoff failure that cannot silently look dispatchable.\n- Preserve authority-boundary checks and project scoping.\n\nRequired tests:\n- An authenticated spawned worker can comment and transition its own task through the documented command/tool path.\n- A worker cannot mutate another project/task outside its grant or read/reuse the operator credential.\n- Authentication failure is recorded and prevents immediate redundant redispatch of the completed commit.\n- Cover ACP Codex plus at least one other backend/session path and run make test.\n\nAcceptance criteria:\nA worker completing the AGENTS.md session checklist can update its assigned task without HTTP 401; no reusable service secret is exposed in prompts/logs/environment-readable repository files; failed handoffs are visible and do not cause duplicate implementation runs; project and action-policy authorization remains enforced.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

