---
id: OOMPAH-459
type: epic
status: In Progress
priority: 1
title: Route all terminal-state producers through independent auditing
parent: null
children:
- OOMPAH-476
- OOMPAH-477
- OOMPAH-478
- OOMPAH-479
- OOMPAH-480
- OOMPAH-481
- OOMPAH-482
- OOMPAH-483
- OOMPAH-564
- OOMPAH-565
- OOMPAH-566
- OOMPAH-568
- OOMPAH-572
- OOMPAH-573
blocked_by:
- OOMPAH-458
labels:
- rebase-requested
- epic:rebasing
- ci-fix
assignee: null
created_at: '2026-07-28T13:03:46.877390Z'
updated_at: '2026-07-30T03:50:46.286062Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: c74020f8-72a8-4537-b791-6bead1249e3e
---
## Summary

Goal

Integrate the terminal-audit coordinator into every path that currently writes Done, Merged, or Archived so no agent, API, webhook, YOLO action, rollup, reconciler, or maintenance job can silently bypass validation.

Required behavior

- Agent and API requests for terminal status stage In Validation rather than writing the terminal status directly.
- Automatic Done, Merged, and Archived transitions use the same coordinator and target-specific audit contracts.
- A direct Merged observation chains completion and landing audits when required.
- Failed epic audits reopen the epic as Open with audit:repair-needed and permit one epic-planner repair run even when children already exist.
- A safety reconciliation pass detects terminal writes outside the coordinator while grandfathering the upgrade baseline.
- A static regression test rejects new direct terminal tracker mutations outside an explicit coordinator allowlist.
- Explicit authorized owner overrides remain available and auditable.

Constraints

Build on the foundation and auditor-dispatch epics. Preserve existing close, unpushed, CI, rebase, epic landing, and release gates as deterministic evidence inputs. Do not weaken status-label authorization. All code changes require tests.

Acceptance criteria

Every known terminal producer is covered by the coordinator, unaudited future terminal states are detected and staged, normal nonterminal behavior is unchanged, and focused integration tests plus make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 18:10
---
Queued for execution. Every child explicitly depends on OOMPAH-458, so no epic-OOMPAH-459 branch/worktree will be created until OOMPAH-458 has landed. Its first dispatch will therefore branch from the then-latest main.
---
author: oompah
created: 2026-07-30 03:31
---
Branch quality gate blocked review creation.

Branch: `epic-OOMPAH-459`
Target: `main`
Head: `11ea824f7e61f78d1de758ca9062df842c0ce397`
Command: `make test`
Result: `interrupted`

Required: run the command in the task worktree, fix the failure, commit and push the repair, then leave the task in Done. Oompah will rerun the gate for the new head before creating the PR/MR.

Output tail:
```text
make[1]: Entering directory '/home/shedwards/.oompah/worktrees/oompah/epic-OOMPAH-459'
uv pip install -e '.[server]'
Setup complete. Run 'make start' to launch oompah.
uv pip install -e '.[dev]'
Test dependencies installed.
Terminal mutation scan passed: 6 identified, 6 explicitly allowlisted.
Running pytest with 4 isolated workers under /home/shedwards/.oompah/tmp/pytest/run.91Rupq

Using CPython 3.12.12
Creating virtual environment at: .venv
Activate with: source .venv/bin/activate
Resolved 53 packages in 267ms
   Building oompah @ file:///home/shedwards/.oompah/worktrees/oompah/epic-OOMPAH-459
      Built oompah @ file:///home/shedwards/.oompah/worktrees/oompah/epic-OOMPAH-459
Prepared 1 package in 284ms
Installed 53 packages in 48ms
 + annotated-doc==0.0.5
 + annotated-types==0.8.0
 + anyio==4.14.2
 + attrs==26.1.0
 + babel==2.18.0
 + bcrypt==4.3.0
 + certifi==2026.7.22
 + cffi==2.1.0
 + click==8.4.2
 + cryptography==49.0.0
 + fastapi==0.141.1
 + h11==0.16.0
 + httpcore==1.0.9
 + httptools==0.8.0
 + httpx==0.28.1
 + httpx-sse==0.4.3
 + idna==3.18
 + jinja2==3.1.6
 + jsonschema==4.26.0
 + jsonschema-specifications==2025.9.1
 + markupsafe==3.0.3
 + mcp==1.29.0
 + oompah==0.1.0 (from file:///home/shedwards/.oompah/worktrees/oompah/epic-OOMPAH-459)
 + passlib==1.7.4
 + pycparser==3.0
 + pydantic==2.13.4
 + pydantic-core==2.46.4
 + pydantic-settings==2.14.2
 + pyjwt==2.13.0
 + python-dateutil==2.9.0.post0
 + python-dotenv==1.2.2
 + python-liquid==2.3.0
 + python-multipart==0.0.32
 + pytz==2026.3.post1
 + pyyaml==6.0.3
 + referencing==0.37.0
 + rpds-py==2026.6.3
 + six==1.17.0
 + sse-starlette==3.4.6
 + starlette==1.3.1
 + tree-sitter==0.26.0
 + tree-sitter-javascript==0.25.0
 + tree-sitter-markdown==0.5.1
 + tree-sitter-python==0.25.0
 + tree-sitter-rust==0.24.2
 + tree-sitter-typescript==0.23.2
 + tree-sitter-yaml==0.7.2
 + typing-extensions==4.16.0
 + typing-inspection==0.4.2
 + uvicorn==0.52.0
 + uvloop==0.22.1
 + watchfiles==1.2.0
 + websockets==17.0
Resolved 74 packages in 146ms
   Building oompah @ file:///home/shedwards/.oompah/worktrees/oompah/epic-OOMPAH-459
      Built oompah @ file:///home/shedwards/.oompah/worktrees/oompah/epic-OOMPAH-459
Prepared 1 package in 232ms
Uninstalled 2 packages in 1ms
Installed 23 packages in 59ms
 + charset-normalizer==3.4.9
 + claude-agent-sdk==0.2.128
 + distro==1.9.0
 + execnet==2.1.2
 + granian==2.7.9
 + griffelib==2.1.0
 + iniconfig==2.3.0
 + jiter==0.16.0
 ~ oompah==0.1.0 (from file:///home/shedwards/.oompah/worktrees/oompah/epic-OOMPAH-459)
 + openai==2.50.0
 + openai-agents==0.17.8
 + packaging==26.2
 + pluggy==1.6.0
 + pygments==2.20.0
 + pytest==9.1.1
 + pytest-asyncio==1.4.0
 + pytest-timeout==2.4.0
 + pytest-xdist==3.8.0
 + requests==2.34.2
 + sniffio==1.3.1
 + tqdm==4.70.0
 + urllib3==2.7.0
 - websockets==17.0
 + websockets==16.1.1
Uninstalled 8 packages in 8ms
Installed 8 packages in 23ms
make[1]: *** [Makefile:225: test] Terminated
```
---
author: oompah
created: 2026-07-30 03:32
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-30 03:32
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-07-30 03:34
---
Understanding: The failing gate at 11ea824f7 shows 'make[1]: *** [Makefile:225: test] Terminated' — a SIGTERM kill during pytest startup, not a test failure. Prior comments indicate transient/non-reproducible failures. I'll run focused tests on the epic worktree (OOMPAH-459-fix branch tracks origin/epic-OOMPAH-459 at 11ea824f7) to identify any real regression. Plan: (1) run pytest -x on tests likely affected by recent OOMPAH-483 changes (integration gate, terminal mutation scanner, worker timeout), (2) if all pass, verify the previously-flaky intake_promotion test survives multiple runs, (3) commit a determinism fix if needed and force-push to origin/epic-OOMPAH-459.
---
author: oompah
created: 2026-07-30 03:50
---
Discovery: Reproduced a real (not just SIGTERM-timeout) test failure under 4-worker xdist parallel load: tests/test_orchestrator_handlers.py::TestMaintenanceLaneNonBlocking::test_tick_does_not_await_maintenance_heal fails with the 1.0s asyncio.wait_for tripping before _tick() has a chance to schedule its handlers under CPU contention. In isolation the test passes in <1s; under full-suite parallel load it exceeds the 1.0s guard even though _tick() is genuinely non-blocking. Root cause: wall-clock threshold too tight for CI parallel load — the same class of regression OOMPAH-483 fixed in test_task_cost_telemetry.py.
---
<!-- COMMENTS:END -->
