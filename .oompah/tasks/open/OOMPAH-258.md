---
id: OOMPAH-258
type: task
status: Open
priority: null
title: Configure Git state branches in project-bootstrap and operator documentation
parent: OOMPAH-253
children: []
blocked_by:
- OOMPAH-256
labels: []
assignee: null
created_at: '2026-07-20T16:29:48.958577Z'
updated_at: '2026-07-20T16:31:25.817215Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Scope

Update project-bootstrap so every newly bootstrapped native-tracker project receives a dedicated Oompah state branch and corresponding project configuration. Update user-facing documentation for setup, permissions, verification, troubleshooting, and recovery.

Implementation requirements

- Extend project-bootstrap templates/scripts to create or initialize the configured state branch with the canonical task-tree layout and set the project state-branch configuration.
- Bootstrap must be idempotent: rerunning it recognizes a valid existing state branch and never overwrites task data.
- Document required repository permissions, branch protection considerations, how to verify state-branch tracking, checkpoint timing configuration in .env, and how to troubleshoot failed state pushes.
- Document the distinction between code branches and the Oompah state branch, including why state commits do not appear in code or release histories.
- Do not add an external service or database dependency.

Tests

- End-to-end bootstrap fixture starts with an empty remote repository and verifies the state branch, project configuration, and initial task layout are created.
- Idempotency test reruns bootstrap with existing state data and proves no data is lost or duplicated.
- Template/documentation test verifies the generated configuration contains the state-branch setting.

Acceptance criteria

- A newly bootstrapped managed project is state-branch enabled by default.
- Bootstrap is safe to rerun.
- docs/ contains complete operator setup and recovery instructions.
- make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

