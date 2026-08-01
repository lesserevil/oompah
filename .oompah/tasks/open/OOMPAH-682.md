---
id: OOMPAH-682
type: task
status: Open
priority: null
title: Make duplicate-preflight recovery authoritative and self-sufficient
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-01T18:07:47.349822Z'
updated_at: '2026-08-01T19:00:11.423090Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 95ed1042ea2ed55477eeb3c00c184da3a8df18c95bdabf32b16ad9b8b15eefeb
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 9506c2fe-4f91-4d81-ad2d-782f77510b15
  claim_owner: cdcf766d-728b-41c9-bcaa-eb3b220f310c
  claimed_at: '2026-08-01T19:00:06.416745+00:00'
  claim_expires_at: '2026-08-01T19:30:06.416745+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: cb0b9aa3-6004-438c-8520-ce627bdbde8c
---
## Summary

Regression observed on NODEVIRT-8, NODEVIRT-9, and NODEVIRT-10 on 2026-08-01. After three infrastructure-only inconclusive runs, a project owner reviewed the tasks, confirmed no active duplicate, documented that decision, and moved them from Needs Human to Open exactly as the scheduler comment instructed. Oompah retained retry_count=3, so one fresh malformed/inconclusive response immediately returned each task to Needs Human at count four. The fresh investigators also lacked a reliable native-task corpus because implementation worktrees do not contain the project state branch task files; two concluded no duplicate in prose but exhausted their output before the required machine-readable footer, while one correctly reported the missing evidence as inconclusive.

Implementation scope:
- Add an explicit project-owner duplicate-screening resolution/rearm path that can durably record no_duplicate or a verified active duplicate for the current task fingerprint, with reason/evidence and actor attribution. At minimum, the existing documented Needs Human to Open recovery must reset the exhausted retry budget rather than inherit it.
- Give Duplicate Investigator runs a reliable read-only view or prompt corpus of current project-native tasks, including statuses, descriptions, and relevant comments, without granting cross-project/task mutation authority and without assuming task files exist on the implementation branch.
- Make the structured verdict robust to output limits by requiring/emitting the machine-readable verdict before optional narrative, and ensure only the current claim run or an authenticated owner resolution can satisfy the result; do not trust arbitrary user-authored task-comment injection.
- Update operator/UI action text and documentation to match the actual recovery operation.

Relevant code: oompah/duplicate_screening.py, duplicate-preflight claim/finish paths in oompah/orchestrator.py, oompah/focus.py, scoped MCP/task context construction and server/task CLI status APIs, plus dashboard action text as applicable.

Required tests:
- An exhausted retry record resolved/rearmed by an owner does not become attempt four on the next run.
- A non-owner cannot forge a conclusive duplicate verdict through comments or status changes.
- A native Markdown project whose task files live only on the state branch gives the investigator enough read-only peer-task evidence to reach a verdict.
- A response truncated after a leading structured verdict is still parsed; prose without the contract remains inconclusive.
- Concurrent/late claim completion cannot overwrite a newer owner resolution or task revision.

Acceptance criteria:
- The recovery action advertised in Needs Human reliably returns reviewed tasks to normal dispatch.
- Duplicate investigators can compare active native tasks without cross-scope authorization failures or implementation-branch task files.
- Retry counts reflect attempts since the latest explicit rearm, not lifetime failures.
- Conclusive evidence is authenticated, revision-bound, and race-safe.
- Focused tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-01 19:00
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-01 19:00
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
