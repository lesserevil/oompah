---
id: OOMPAH-620
type: feature
status: Backlog
priority: 1
title: Resolve CLI Basic-auth credentials from argv, environment, and netrc
parent: OOMPAH-619
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T21:25:27.860280Z'
updated_at: '2026-07-30T21:25:27.860280Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Implementation scope: extend the shared client credential resolver and every standalone HTTP CLI parser so task and admin commands accept explicit --username and --password as well as the existing --password-file. Continue supporting OOMPAH_SERVER_USERNAME with OOMPAH_SERVER_PASSWORD or OOMPAH_SERVER_PASSWORD_FILE. When no higher-precedence value supplies a complete usable credential, read the entry for the normalized hostname of the resolved OOMPAH server URL from the default user netrc file. Username precedence is CLI, environment, then netrc; password precedence is one CLI password source, one environment password source, then the matching netrc password. Reject conflicting same-tier password sources, partial credentials, a netrc password paired with a different overridden login, malformed or unsafe default netrc data, and credentials embedded in URLs. Do not retry a 401 with a lower-precedence source. Keep secrets out of repr, errors, logs, telemetry, and request URLs. Explicit --password is an opt-in compatibility path whose help warns that argv can be visible in process listings; retain password-file as the safer explicit option. Relevant files include oompah/client_auth.py, oompah/task_cli.py, oompah/admin_cli.py, and their existing auth tests. Tests must cover each source independently, mixed field precedence compatible with existing behavior, conflicts, hostname and port normalization, missing and malformed netrc, permission behavior, IPv4 and IPv6 server URLs where supported, redaction, unauthenticated servers, and real task/admin requests through a local test server. Acceptance criteria: both task and admin CLI surfaces authenticate successfully with all three requested source families; precedence is deterministic and documented in help; no secret appears in observable errors or test logs; focused auth/CLI suites and the complete Makefile gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

