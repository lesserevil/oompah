---
id: OOMPAH-677
type: bug
status: In Progress
priority: 1
title: Prevent ownerless projects from deadlocking intake promotion
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- focus-complete:frontend
- needs:feature
assignee: null
created_at: '2026-08-01T11:56:19.836343Z'
updated_at: '2026-08-01T14:33:21.377336Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 6cdbdaeba8a7b84ac3ed57dc13ef68a811eafaf4f7d6cace04b58274b3c4ab92
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-01T14:27:38.921376+00:00'
  matched_identifiers: []
  evidence: "Based on my comprehensive investigation of the oompah task tracker, I\
    \ have completed the duplicate screening for OOMPAH-677.\n\n## Investigation Summary\n\
    \nI searched across all task states:\n- **Open tasks** (1 found): OOMPAH-281 \u2014\
    \ GitHub Actions self-hosted runner setup (unrelated)\n- **Backlog tasks** (1\
    \ found): OOMPAH-282 \u2014 UnicodeEncodeError in state branch migration (unrelated)\n\
    - **Merged tasks** (7 found): Reviewed, all unrelated to project ownership/intake\
    \ promotion\n- **Archived tasks** (200+ found): Searched with patterns: ownerless,\
    \ status_actor_login, tracker_owner, intake promotion, project owner, actor identity,\
    \ dispatch gate, managed project, project configuration, identity, etc.\n\nI also\
    \ searched the codebase (oompah/, src/, docs/, plans/) for references to:\n- Field\
    \ names: `status_actor_login`, `tracker_owner`, `status_label_authorized_logins`\n\
    - Related concepts: intake backlog transitions, project owner gates, actor mapping\n\
    - Project event: NodeVirt regression, deadlocking, configuration warnings\n\n\
    **Results:** No matches found for any active tasks covering the same ground as\
    \ OOMPAH-677.\n\nThe closest historical context is OOMPAH-249 (archived, completed),\
    \ which addressed wiring SCM provider and managed_repo into the server factory\
    \ for release delivery, but that is architecturally distinct from the project\
    \ identity / owner-gate validation problem described in OOMPAH-677.\n\n---\n\n\
    **Focus handoff: duplicate_detector**\n\n**Duplicate preflight verdict: no_duplicate**\n\
    \n**Matches: none**\n\n**Evidence:** Exhaustive search across all task states,\
    \ source code, and documentation found no active tasks addressing project owner\
    \ configuration validation, intake promotion deadlocking, or the specific NodeVirt\
    \ regression. OOMPAH-677 is the first task to address the problem of projects\
    \ being created without owner-capable actor identity (status_actor_login, tracker_owner,\
    \ status_label_authorized_logins), causing all Backlog-to-Open transitions to\
    \ fail the owner gate and leaving ta"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 487d7f93-122e-456e-9b1a-cf6ab373a868
oompah.task_costs:
  total_input_tokens: 234
  total_output_tokens: 4829
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 234
      output_tokens: 4829
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 234
    output_tokens: 4829
    cost_usd: 0.0
    recorded_at: '2026-08-01T14:27:38.918413+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-677__20260801T142515Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-677
    source_sha: 62ca0ca696d08b754e03a200d7227455786da960
    completed_at: '2026-08-01T14:27:38.939916+00:00'
---
## Summary

Live regression discovered on the NodeVirt managed project on 2026-08-01. The project was accepted with tracker_kind=oompah_md and intake Backlog tasks but had no status_actor_login, tracker_owner, or status_label_authorized_logins. Consequently every human Backlog to Open transition failed the project-owner gate even for the repository owner, leaving 21 tasks non-dispatchable until an operator manually patched project identity configuration. Implementation scope: validate or derive an owner-capable actor identity when creating and updating managed projects; cover GitLab and native Markdown tracker combinations where tracker_owner may be absent; expose the resolved authenticated actor and project owner configuration in an actionable dashboard rejection; do not weaken the owner-only dispatch boundary or trust client-supplied actor fields. Relevant areas: project create/update routes and models, actor mapping, transition gate, dashboard project forms/error handling, and project onboarding tests. Acceptance criteria: a newly configured dispatchable project cannot silently become ownerless; existing ownerless projects receive a visible health/configuration warning with a safe remediation; authenticated configured owners can promote Backlog to Open; non-owners remain rejected; regression tests reproduce the NodeVirt configuration and prove the repaired behavior.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-01 14:25
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-01 14:25
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-01 14:27
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 59, Tool calls: 28
- Tokens: 234 in / 4.8K out [5.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 29s
- Log: OOMPAH-677__20260801T142515Z.jsonl
---
author: oompah
created: 2026-08-01 14:27
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-01 14:27
---
Focus: Frontend Developer
---
author: oompah
created: 2026-08-01 14:28
---
Understanding: ownerless managed projects currently reject every human Backlog-to-Open promotion. I will trace project create/update identity handling, actor resolution, the owner-only transition gate, and dashboard rejection rendering; then add safe owner derivation/validation, actionable health feedback, regression tests, and verify with focused Make targets.
---
author: oompah
created: 2026-08-01 14:32
---
Implementation: updated oompah/templates/projects.html with accessible owner-identity health warnings for oompah_md, GitHub Issues, and GitLab Issues; added onboarding fields for status actor and authorized logins; and documented server-side actor resolution. Updated oompah/templates/dashboard.html to render authenticated actor, project owner configuration, and remediation details from structured intake-transition rejections in the board alert, including intake actions. Added UI contract coverage in tests/test_projects_gitlab_ui.py and tests/test_dashboard_intake_actions.py.
---
author: oompah
created: 2026-08-01 14:32
---
Verification: PYTHONPATH=. pytest -q tests/test_projects_gitlab_ui.py tests/test_dashboard_intake_actions.py -> 106 passed; PYTHONPATH=. pytest -q tests/test_projects_crud.py -> 157 passed; git diff --check passed. The first pytest invocation hit an environment ImportPathMismatchError from /home/shedwards/src/oompah, resolved by explicitly prioritizing this worktree on PYTHONPATH.
---
author: oompah
created: 2026-08-01 14:33
---
Focus handoff: frontend
1. Outcome: completed the dashboard/projects UI portion. Protected projects now show an accessible ownerless configuration warning with a Configure owner identity action; onboarding accepts status_actor_login and status_label_authorized_logins; transition/intake failures render the authenticated actor, project owner configuration, and remediation in the board alert.
2. Relevant files/evidence: oompah/templates/projects.html, oompah/templates/dashboard.html, tests/test_projects_gitlab_ui.py, tests/test_dashboard_intake_actions.py. Focused checks: PYTHONPATH=. pytest -q tests/test_projects_gitlab_ui.py tests/test_dashboard_intake_actions.py (106 passed); PYTHONPATH=. pytest -q tests/test_projects_crud.py (157 passed); git diff --check passed. Commit 95371a0da is pushed to origin/OOMPAH-677.
3. Remaining work/risks: backend project create/update still only resolves token ownership for GitHub; GitLab and native Markdown configurations can remain ownerless. The API transition evaluator also needs the GitLab tracker included in the protected owner gate. Add structured rejection fields such as error.authenticated_actor and error.project_owner_config (the UI tolerates compatible aliases). Preserve server-side authenticated actor binding and do not authorize from client actor fields.
4. Recommended next focus: backend/feature agent should implement shared owner identity resolution/validation for create and update, repair or clearly flag existing ownerless projects, extend gate coverage to GitLab, and add regression tests for the NodeVirt configuration and authenticated-owner/non-owner transitions.
---
<!-- COMMENTS:END -->
