---
id: OOMPAH-13
type: bug
status: Open
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
updated_at: '2026-06-20T03:35:59.418114Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
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

