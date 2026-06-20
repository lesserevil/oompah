---
id: OOMPAH-13
type: bug
status: In Progress
priority: 1
title: Use project status actor by default for dashboard intake actions
parent: null
children: []
blocked_by: []
labels:
- bug
- native-tracker
- intake
- ui
- auth
assignee: null
created_at: '2026-06-20T03:02:36.629755Z'
updated_at: '2026-06-20T03:44:36.994950Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 415c4b44-baa2-4bbf-92bf-71761f2d9a3d
---
## Summary

The dashboard Proposed-intake action flow still relies on a manually entered `oompah_intake_actor` value in localStorage. If the operator has not set that value, `openDetailPanel()` fetches detail without an actor, `action_permissions()` returns no owner actions, and owner-only buttons such as Request Changes, Override Readiness, and Promote to Backlog can disappear or require a prompt even though the project already has `status_actor_login` configured.

This is the same class of bug as the Backlog -> Open drag/drop failure: protected owner actions should use the project-configured status actor by default instead of behaving as anonymous/non-owner.

Expected behavior:
- For protected tracker workflows (`github_issues` and `oompah_md`), the dashboard should default owner actions to the project status actor (`status_actor_login`, then allowlist/tracker owner fallback) when no explicit local override is set.
- The detail endpoint should receive that actor so owner buttons render correctly.
- Intake action POSTs should send the same actor by default.
- Users may still override the actor explicitly when needed.

Acceptance criteria:
- Reuse or share the existing `projectStatusActorLogin(project)` logic for detail panel intake actions.
- `openDetailPanel()` can resolve the project config and include the default actor in detail requests for native and GitHub-backed projects.
- `performIntakeAction()` sends the default project actor without prompting during normal owner workflows.
- Add dashboard tests for `oompah_md` Proposed tasks showing owner actions with configured `status_actor_login`.
- Do not hard-code any user names in tests.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-20 03:36
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-06-20 03:36
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-06-20 03:39
---
Understanding: OOMPAH-13 is NOT a duplicate. Prior commits (b56adf0, 1cb1bff, 82c9846) fixed the drag/drop status-change paths to use projectStatusActorLogin(project), but the *intake action button path* in openDetailPanel() and performIntakeAction() still only reads from localStorage('oompah_intake_actor'). When the operator has not set that localStorage key, the detail request omits the actor, action_permissions() returns no owner actions, and buttons like 'Request Changes', 'Override Readiness', 'Promote to Backlog' disappear. Plan: (1) Modify openDetailPanel() to fall back to projectStatusActorLogin(project) when no localStorage actor, (2) Modify performIntakeAction() to use project status actor instead of prompting, (3) Add tests for oompah_md Proposed tasks showing owner actions with status_actor_login configured, (4) Verify no hardcoded user names in tests.
---
author: oompah
created: 2026-06-20 03:44
---
Discovery: Confirmed NOT a duplicate. Prior commits fixed drag/drop status-change paths but the intake action button path was still broken. In openDetailPanel(), intakeActor only used localStorage('oompah_intake_actor'); in performIntakeAction(), missing actor went straight to prompt(). The fix: (1) openDetailPanel now resolves project from currentProjects and uses effectiveIntakeActor = intakeActor || projectStatusActorLogin(project), (2) performIntakeAction moves projectId extraction to the top and inserts a projectStatusActorLogin(project) fallback before the prompt() call.
---
<!-- COMMENTS:END -->
