---
id: OOMPAH-623
type: bug
status: Backlog
priority: 1
title: Keep the canonical user CLI synchronized with the running server
parent: OOMPAH-619
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T21:32:18.734139Z'
updated_at: '2026-07-30T21:32:18.734139Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

System contract: /home/shedwards/.local/bin/oompah is the canonical CLI used by operators, automation, and spawned processes on this host. It must not silently drift from the running Oompah server while a project-local virtualenv happens to contain newer code. Add a machine-readable build identity containing the source revision to both the standalone CLI and the server health or state surface, while retaining a human-readable oompah --version command. Add a Makefile lifecycle target that installs or upgrades the UV tool at the canonical user path from the exact clean pushed revision selected for the server, verifies command resolution and revision equality, and is invoked by normal source-managed start, restart, and graceful deployment flows at the safe point. Never replace the known-good CLI with a dirty, unpushed, failed, or non-review-ready source state; preserve the old executable on installation failure and report an actionable operator alert. Tests must isolate HOME and UV tool directories, simulate initial install, upgrade, already-current no-op, version mismatch, failed install rollback, dirty checkout refusal, wrong PATH resolution, and successful authenticated task/admin requests after synchronization. Document the canonical path and recovery command. Acceptance criteria: after merged main is deployed, command -v oompah resolves /home/shedwards/.local/bin/oompah; CLI and server report the same git revision; task and admin requests authenticate; every supported graceful lifecycle path either preserves that equality or fails clearly without disrupting the running known-good pair.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

