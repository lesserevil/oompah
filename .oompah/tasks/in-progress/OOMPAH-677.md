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
- focus-complete:chore
assignee: null
created_at: '2026-08-01T11:56:19.836343Z'
updated_at: '2026-08-01T14:39:12.881531Z'
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
oompah.agent_run_id: ba9a2f07-2c25-468d-baae-f62c902923d6
oompah.task_costs:
  total_input_tokens: 3543882
  total_output_tokens: 20808
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 3543845
      output_tokens: 19897
      cost_usd: 0.0
    opus:
      input_tokens: 37
      output_tokens: 911
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 234
    output_tokens: 4829
    cost_usd: 0.0
    recorded_at: '2026-08-01T14:27:38.918413+00:00'
  - profile: default
    model: haiku
    input_tokens: 3543611
    output_tokens: 15068
    cost_usd: 0.0
    recorded_at: '2026-08-01T14:33:41.264936+00:00'
  - profile: deep
    model: opus
    input_tokens: 37
    output_tokens: 911
    cost_usd: 0.0
    recorded_at: '2026-08-01T14:36:58.792301+00:00'
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
  - run_id: OOMPAH-677__20260801T142800Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: frontend
    source_branch: OOMPAH-677
    source_sha: 95371a0da020a1f82bd0e4fb48c2202e8a8a91d6
    completed_at: '2026-08-01T14:33:41.269262+00:00'
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
author: oompah
created: 2026-08-01 14:33
---
Agent completed successfully in 346s (3558679 tokens)
---
author: oompah
created: 2026-08-01 14:33
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 59
- Tokens: 3.5M in / 15.1K out [3.6M total]
- Cost: $0.0000
- Exit: normal, Duration: 5m 46s
- Log: OOMPAH-677__20260801T142800Z.jsonl
---
author: oompah
created: 2026-08-01 14:33
---
Focus handoff from `frontend` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-08-01 14:34
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-08-01 14:34
---
Focus: Maintenance Engineer
---
author: oompah
created: 2026-08-01 14:36
---
Understanding (chore focus): the remaining work described in the previous frontend handoff — shared owner-identity resolution/validation for project create+update (covering GitLab and oompah_md, not just GitHub), extending the transition_gate owner check for GitLab configurations, repairing/flagging existing ownerless projects, and adding regression tests for the NodeVirt configuration — is backend feature scope, not maintenance. The current maintenance-engineer role explicitly forbids scope expansion and refactors. The task's needs:feature label already requests the correct next specialist; this dispatch to chore appears to be a routing skip. Handing off to feature.
---
author: oompah
created: 2026-08-01 14:36
---
Focus handoff: chore
1. Outcome: no code changes. This dispatch to the maintenance-engineer role is out of scope — the remaining work is backend feature scope (shared owner-identity resolution/validation on project create+update, GitLab and oompah_md coverage, transition_gate GitLab wiring, ownerless-project repair/flagging, and NodeVirt-shaped regression tests), and the chore role is explicitly forbidden from expanding scope or refactoring surrounding code.
2. Relevant files/evidence: oompah/projects.py (create ~L918, update UPDATABLE_FIELDS ~L1160 and validators ~L1290-1420 — no owner identity resolution/validation for GitLab or oompah_md; only GitHub owner is inferred from repo URL for GitHub-backed trackers around L1091-1103), oompah/actor_mapping.py (server principal → project actor login mapping, healthy for reuse), oompah/transition_gate.py (is_project_owner + check_intake_transition — logic is tracker-agnostic but the callers/config surface still assume GitHub owners; verify GitLab coverage during implementation), oompah/intake_promotion.py, oompah/gitlab_tracker.py, oompah/github_tracker.py. Previous UI work is committed as 95371a0da on origin/OOMPAH-677 and 106 focused UI tests plus 157 project CRUD tests were green.
3. Remaining work/risks: (a) add a shared _resolve_owner_identity helper used by ProjectStore.create and ProjectStore.update that derives status_actor_login from the repo_url or authenticated tracker credentials for GitHub, GitLab, and native Markdown (when github_issue_intake_enabled is False the derivation must still succeed for the operator's forge or fall back to the authenticated server principal), and rejects a dispatchable project that would end up ownerless — never trusting client-supplied actor fields; (b) at update time, block clearing status_actor_login/status_label_authorized_logins/tracker_owner if the project would become ownerless while paused=False, and surface a structured error with error.authenticated_actor and error.project_owner_config that the dashboard already tolerates; (c) run a one-shot repair on load that marks any pre-existing ownerless project with a health flag consumed by projects.html (already renders it); (d) confirm the transition_gate protected-owner set covers GitLab configurations (add unit tests where the project has forge_kind=gitlab and only status_actor_login set); (e) regression tests reproducing NodeVirt (tracker_kind=oompah_md, no status_actor_login/tracker_owner/status_label_authorized_logins) that prove: creation is now rejected or the project is created paused-with-warning, update to un-pause without owner is rejected, authenticated owner promotes Backlog→Open successfully, non-owner is still rejected. Preserve server-side authenticated actor binding via oompah.actor_mapping.ActorMap.resolve; do not authorize from client actor fields.
4. Recommended next focus: feature (backend). The task already carries needs:feature.
---
author: oompah
created: 2026-08-01 14:37
---
Run #1 [attempt=1, profile=deep, role=deep -> Claude/opus]
- Turns: 0, Tool calls: 19
- Tokens: 37 in / 911 out [948 total]
- Cost: $0.0000
- Exit: terminated, Duration: 2m 29s
- Log: OOMPAH-677__20260801T143437Z.jsonl
---
author: oompah
created: 2026-08-01 14:37
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-01 14:37
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-01 14:39
---
**Understanding**: NodeVirt project regression where oompah_md tracker without status_actor_login/tracker_owner blocked all Backlog→Open transitions. Frontend agent added UI warnings/fields. I will now implement backend owner-identity resolution/validation for project create/update (GitHub, GitLab, oompah_md), extend transition_gate for GitLab, repair pre-existing ownerless projects, and add regression tests.

Implementation approach:
1. Add _resolve_owner_identity helper to derive status_actor_login from repo_url/tracker credentials
2. Validate during create that dispatchable projects have an owner
3. In update, block clearing owner fields if project would become ownerless while active
4. Extend transition_gate.is_project_owner to cover GitLab tracker_owner
5. One-shot repair on load for pre-existing ownerless projects
6. Regression tests for NodeVirt (oompah_md, no owner) configuration
---
<!-- COMMENTS:END -->
