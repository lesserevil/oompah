---
id: OOMPAH-303
type: bug
status: In Progress
priority: 1
title: Use private ~/.oompah/tmp for Oompah and agent temporary files
parent: null
children: []
blocked_by: []
labels:
- needs:backend
- needs:operations
assignee: null
created_at: '2026-07-21T15:33:58.183374Z'
updated_at: '2026-07-21T15:34:44.028466Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Replace Oompah’s reliance on the shared system /tmp directory with an Oompah-owned temporary root at ~/.oompah/tmp. This prevents per-user tmpfs quota exhaustion from blocking agent command execution, Git operations, and final commit/push checks.\n\nImplementation requirements:\n- Add a documented OOMPAH_TEMP_ROOT environment setting. Its safe default is ~/.oompah/tmp; expand ~ and require an absolute resolved path.\n- At service startup, create the root and required children with owner-only permissions (0700). Fail clearly and before dispatch if it cannot be created or written.\n- Set TMPDIR, TMP, and TEMP for the Oompah server process and every agent/backend subprocess, including Codex, Claude, OpenCode, shell/git/build commands, and background worker commands. Preserve explicitly configured child-environment overrides only where they are safe and documented.\n- Default OOMPAH_WORKSPACE_ROOT below the Oompah home area (for example ~/.oompah/workspaces) rather than /tmp/oompah_workspaces.\n- Allocate isolated per-agent-session temporary directories; clean them on normal completion, cancellation, and startup recovery. Do not delete unrelated files or an active session directory.\n- Update .env.example and operator documentation. Do not put tunable configuration in WORKFLOW.md.\n\nTests:\n- Unit-test default/override path expansion, validation, directory creation, and 0700 permissions.\n- Unit-test all agent/backend environment builders receive TMPDIR, TMP, and TEMP pointing beneath the configured root.\n- Integration-test a temporary Oompah home: an agent command and git subprocess create temporary files there, not in system /tmp.\n- Test cleanup for successful, failed, cancelled, and stale-session paths, including protection against deleting outside the configured root.\n- Regression-test that a full /tmp does not prevent agent finalization when OOMPAH_TEMP_ROOT is writable.\n\nAcceptance criteria:\n- A fresh default installation no longer creates Oompah workspaces or agent temporary files in /tmp.\n- Agents can complete Git commit/push/status work when system /tmp has exhausted its user quota but ~/.oompah/tmp is writable.\n- Operators can relocate the root through .env and can diagnose an unusable root from a clear startup/runtime error.\n- No external service is introduced, and all relevant Makefile/service startup paths are covered by automated tests.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

