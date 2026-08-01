---
id: OOMPAH-685
type: task
status: Open
priority: null
title: Forward project forge credentials through integration verification
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-01T21:46:41.297124Z'
updated_at: '2026-08-01T21:46:43.059650Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Regression of merged OOMPAH-680 observed on NODEVIRT-7 on 2026-08-01. The NodeVirt GitLab project has a valid configured access_token: a one-shot push and authenticated fetch using oompah.git_credentials.git_credential_environment both succeed, and local/remote task heads match at bb916af. The server integration executor nevertheless failed while verifying the submitted branch with GitLab HTTP Basic access denied and changed integration state to blocked/Open. Installing a token-free private repository credential helper backed by the same configured project token immediately made the identical fetch succeed.

Implementation scope:
- Trace integration queue verification/rebase/fetch/push operations and ensure every Git network subprocess receives git_credential_environment for the resolved Project, including subprocesses spawned after leases, retries, conflict checks, epic integration, branch-head verification, and cleanup.
- Remove any path that resolves only repo_path/URL while dropping the Project credential context.
- Preserve token redaction and noninteractive behavior: no token in URLs, argv, repository config, logs, comments, or persisted queue records.
- Detect absent/invalid token separately from missing credential forwarding so operator diagnostics are accurate.
- Ensure credential lifetime covers the complete network operation but is removed immediately afterward.
- Keep the integration executor compatible with GitHub and GitLab username conventions.

Relevant code: integration executor/queue, ProjectStore and Workspace Git helpers, epic integration/rebase verification, git_credentials.py, subprocess environment plumbing, and integration retry/error reporting.

Required tests:
- Private GitLab task submission reaches branch verification/rebase/push using a configured project token when no global/repository credential helper exists.
- All nested integration Git subprocesses receive the ephemeral askpass environment.
- Missing token fails noninteractively with an actionable credential-configuration error; an invalid token reports authentication failure.
- Token and encoded token never appear in captured argv, output, logs, task comments, queue persistence, or repo config.
- GitHub project token behavior remains correct.
- Retrying the exact blocked NODEVIRT-7 generation succeeds once credential forwarding is restored without changing its head.

Acceptance criteria:
- The NODEVIRT-7 integration sequence succeeds without an operator-installed repository credential shim.
- Every managed integration network operation uses the project forge credential boundary shipped by OOMPAH-680.
- Focused integration/credential tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

