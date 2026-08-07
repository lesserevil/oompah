# OOMPAH-576 Verification

## Summary
Verification complete for "Reject integration submissions from the wrong checkout before mutating task worktrees"

## Original Implementation
- Commit: 6f5a859b215c0a9a4744984e89b27e3fe990050d
- PR: #599
- Status: Merged to main

## Verification Results
All focused test suites pass:
- tests/test_projects.py: 125 passed
- tests/test_integration_executor.py: 16 passed
- tests/test_integration_record.py: 11 passed
- tests/test_task_handoff.py: 75 passed
- tests/test_worker_submission.py: 14 passed

Total: 241 tests passed

## Acceptance Criteria Verified
✓ Wrong-checkout submission from default branch returns actionable error before any tracker/queue/worktree mutation
✓ Correct submissions from assigned task checkout still integrate normally  
✓ Registered worktree with divergent branch is never reset/clean/checkout by stale queue rows
✓ Branch validation at submit time (ACP + HTTP endpoints) prevents wrong-checkout submissions
✓ Integration executor returns branch_mismatch status without attempting reset

## Implementation Details
1. validate_submission_branch() in oompah/integration.py validates submitted branch matches expected branch
2. ProjectStore._reset_existing_worktree() in oompah/projects.py checks branch identity before reset
3. execute_integration() in oompah/integration_executor.py checks for branch mismatch before proceeding
4. HTTP submit endpoint in oompah/server.py uses validate_submission_branch
5. ACP direct-submit in oompah/acp_tools.py uses validate_submission_branch

This hardening prevents the OOMPAH-483 regression where a wrong-checkout submission overwrote the recorded work branch and reset a live worktree.
