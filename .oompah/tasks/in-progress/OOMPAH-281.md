---
id: OOMPAH-281
type: task
status: In Progress
priority: null
title: Run Oompah CI on a containerized self-hosted GitHub Actions runner
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-20T21:39:55.510108Z'
updated_at: '2026-07-20T21:45:29.847469Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: b7406609-ad3f-496e-909f-faf8fbd89745
---
## Summary

Provide a Docker-compatible self-hosted GitHub Actions runner for the Oompah repository on the current host, so CI does not depend on GitHub-hosted runners. Use the existing Docker-compatible Podman installation; do not add a new service or database.

Scope

- Add a containerized runner definition, host setup/start/stop/status commands, and .env configuration.
- Register the runner against lesserevil/oompah with labels self-hosted, linux, x64, and oompah.
- Update CI workflows to target the oompah runner label.
- Document that GitHub Actions does not provide an OR expression between GitHub-hosted and self-hosted labels; this setup makes the local runner the reliable required capacity.
- Document required PAT permission: Self-hosted runners Read and write.

Tests

- Validate container configuration and scripts without exposing secrets.
- Add workflow tests that assert CI targets the required self-hosted labels.
- Verify registration/status through GitHub API after permission is granted.

Acceptance criteria

- This host runs a healthy containerized runner registered to the Oompah repository.
- CI jobs run successfully when GitHub-hosted runners are unavailable.
- Runner lifecycle and troubleshooting are documented.
- make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-20 21:45
---
Agent dispatched (profile: default)
---
<!-- COMMENTS:END -->
