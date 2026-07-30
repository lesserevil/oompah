---
id: OOMPAH-623
type: bug
status: Open
priority: 1
title: Keep the canonical user CLI synchronized with the running server
parent: OOMPAH-619
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-621
labels: []
assignee: null
created_at: '2026-07-30T21:32:18.734139Z'
updated_at: '2026-07-30T21:36:55.804349Z'
work_branch: epic-OOMPAH-619--task-OOMPAH-623
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.start_blocked_by: *id001
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: c575bdc25a7ca3f085c125da3e650427c8a0bcb34cac3f817ac757f4f7ae0a16
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 945cd0eb-1846-403d-bacb-50ad6f710290
  claim_owner: c1f4a4cb-217d-4c2a-aad6-f768a3cdbb4b
  claimed_at: '2026-07-30T21:36:48.314423+00:00'
  claim_expires_at: '2026-07-30T22:06:48.314423+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: a0be7eff-b4fb-4755-94fd-1d387b5bb4e9
oompah.work_branch: epic-OOMPAH-619--task-OOMPAH-623
oompah.integration:
  version: 1
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-619--task-OOMPAH-623
  base_branch: epic-OOMPAH-619
  base_sha: c048ba706cbe9b1342b80a67576a49b82887e84a
  updated_at: '2026-07-30T21:36:53.228749+00:00'
---
## Summary

System contract: /home/shedwards/.local/bin/oompah is the canonical CLI used by operators, automation, and spawned processes on this host. It must not silently drift from the running Oompah server while a project-local virtualenv happens to contain newer code. Add a machine-readable build identity containing the source revision to both the standalone CLI and the server health or state surface, while retaining a human-readable oompah --version command. Add a Makefile lifecycle target that installs or upgrades the UV tool at the canonical user path from the exact clean pushed revision selected for the server, verifies command resolution and revision equality, and is invoked by normal source-managed start, restart, and graceful deployment flows at the safe point. Never replace the known-good CLI with a dirty, unpushed, failed, or non-review-ready source state; preserve the old executable on installation failure and report an actionable operator alert. Tests must isolate HOME and UV tool directories, simulate initial install, upgrade, already-current no-op, version mismatch, failed install rollback, dirty checkout refusal, wrong PATH resolution, and successful authenticated task/admin requests after synchronization. Document the canonical path and recovery command. Acceptance criteria: after merged main is deployed, command -v oompah resolves /home/shedwards/.local/bin/oompah; CLI and server report the same git revision; task and admin requests authenticate; every supported graceful lifecycle path either preserves that equality or fails clearly without disrupting the running known-good pair.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 21:32
---
Immediate bootstrap completed: the stale canonical CLI at commit 148184aa could not authenticate to the running server and returned HTTP 401. It was replaced through uv tool install with exact clean main revision 12f63352ba017c6ffe88b0ca730bf3f7f973304e, the revision active when the current server process started. ~/.local/bin/oompah now authenticates successfully. Permanent lifecycle synchronization remains the scope of this task.
---
author: oompah
created: 2026-07-30 21:36
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-30 21:36
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
