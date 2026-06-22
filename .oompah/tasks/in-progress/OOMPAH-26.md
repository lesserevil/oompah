---
id: OOMPAH-26
type: task
status: In Progress
priority: 2
title: Document the 1.0 CLI and API compatibility surface
parent: OOMPAH-22
children: []
blocked_by:
- OOMPAH-25
labels: []
assignee: null
created_at: '2026-06-22T01:16:48.515360Z'
updated_at: '2026-06-22T02:53:11.500514Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 9a4b1821-2c69-46be-af8b-6253a5a84f97
---
## Summary

Plan: plans/oompah-1.0-release.md#cli-and-api-contract

WHAT TO DO
Document the supported 1.0 CLI and API compatibility surface, including OOMPAH_SERVER_URL as the server locator and the commands that managed-project AGENTS.md files may depend on.

HOW TO VERIFY
Docs identify the stable 1.0 commands and avoid documenting deprecated OOMPAH_SERVER_HOST or OOMPAH_SERVER_PORT usage.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-22 02:49
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-06-22 02:49
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-06-22 02:51
---
UNDERSTANDING: Not a duplicate. Searched all tasks for overlap (OOMPAH-9 updated AGENTS.md templates for optional CLI use; OOMPAH-18 updated version-number examples; neither creates a dedicated 1.0 CLI/API compatibility surface doc). OOMPAH-33 is blocked by OOMPAH-26, confirming it's distinct work. Plan: create docs/cli-api-surface.md documenting (1) OOMPAH_SERVER_URL as the canonical server locator, (2) the stable oompah task subcommands (view, comment, create, child-create, set-status, add-label, remove-label, set-dependency), (3) oompah project-bootstrap as the other stable top-level command, and (4) what NOT to depend on (no OOMPAH_SERVER_HOST, OOMPAH_SERVER_PORT is the service's own port — not a client-side server locator). Also update docs/cli-install.md 'Agent usage' section to clarify OOMPAH_SERVER_URL is the single stable locator.
---
author: oompah
created: 2026-06-22 02:53
---
DISCOVERY: No existing task covers a dedicated 1.0 CLI/API compatibility surface document. Confirmed: (1) OOMPAH_SERVER_URL is already the primary client-side locator in oompah/task_cli.py; (2) OOMPAH_SERVER_HOST does not exist in the codebase at all; (3) OOMPAH_SERVER_PORT in .env.example is a service-listening-port variable, NOT a client-side locator — using it as a client locator would silently be ignored; (4) docs/cli-install.md currently documents both OOMPAH_SERVER_URL and --port flag as ways to configure the server, but AGENTS.md templates only use OOMPAH_SERVER_URL. Plan: create docs/cli-api-surface.md with the stable 1.0 surface (OOMPAH_SERVER_URL + 8 oompah task subcommands + oompah project-bootstrap), update docs/cli-install.md Agent usage section to clarify OOMPAH_SERVER_URL is the stable locator, add tests to test_cli_release_packaging.py verifying the doc exists with required content.
---
<!-- COMMENTS:END -->
