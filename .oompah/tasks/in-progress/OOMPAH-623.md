---
id: OOMPAH-623
type: bug
status: In Progress
priority: 1
title: Keep the canonical user CLI synchronized with the running server
parent: OOMPAH-619
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-621
labels: []
assignee: null
created_at: '2026-07-30T21:32:18.734139Z'
updated_at: '2026-07-31T08:56:53.099587Z'
work_branch: epic-OOMPAH-619--task-OOMPAH-623
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.start_blocked_by: *id001
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: c575bdc25a7ca3f085c125da3e650427c8a0bcb34cac3f817ac757f4f7ae0a16
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-30T21:38:24.821380+00:00'
  matched_identifiers: []
  evidence: 'Based on my comprehensive investigation, I have:


    1. **Searched all task directories** (.oompah/tasks/open, .oompah/tasks/merged,
    .oompah/tasks/archived)

    2. **Examined the single open task** (OOMPAH-281) - it''s about containerized
    GitHub Actions runners, completely unrelated

    3. **Searched for keywords** related to CLI, synchronization, version, build identity,
    lifecycle, Makefile targets

    4. **Checked documentation** in docs/ and plans/ for any related work

    5. **Reviewed the source code** for existing CLI version handling

    6. **Looked for coordination references** (OOMPAH-619, OOMPAH-620, OOMPAH-621)
    - they do not appear in the task tracking system


    **Findings:**


    The issue OOMPAH-623 is a Priority 1 bug about keeping the canonical CLI at `/home/shedwards/.local/bin/oompah`
    synchronized with the running server. The previous comments indicate:

    - A bootstrap fix was applied (CLI updated from commit 148184aa to 12f63352ba)

    - That was a temporary workaround to fix immediate authentication issues

    - The permanent lifecycle synchronization (Makefile targets, build identity, tests)
    remains to be implemented


    No existing active task covers CLI/server version synchronization, build identity
    tracking, or related lifecycle management. OOMPAH-281 (the only open task) concerns
    GitHub Actions runner containerization and is unrelated.


    **Focus handoff: duplicate_detector**


    **Duplicate preflight verdict: no_duplicate**


    **Matches: none**


    **Evidence:** Comprehensive search across all .oompah/tasks/ states (open, merged,
    archived), docs/, plans/, and source code found no active task matching OOMPAH-623''s
    scope. The only open task (OOMPAH-281) handles GitHub Actions runner containerization.
    Previous comments confirm OOMPAH-623 is a follow-up to a temporary bootstrap fix,
    requiring permanent implementation of Makefile lifecycle targets, machine-readable
    build identity (git revision), and comprehensive tests for CLI/server synchronization.'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 0c315515-69e5-42b5-978a-4c6f794da2f6
oompah.work_branch: epic-OOMPAH-619--task-OOMPAH-623
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-619--task-OOMPAH-623
  base_branch: epic-OOMPAH-619
  base_sha: 0dc7d0f7caeea06a6eceb55ea2e58cf16554f0a4
  updated_at: '2026-07-31T08:55:12.843626+00:00'
oompah.task_costs:
  total_input_tokens: 210
  total_output_tokens: 5047
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 210
      output_tokens: 5047
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 210
    output_tokens: 5047
    cost_usd: 0.0
    recorded_at: '2026-07-30T21:38:24.819020+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-623__20260730T213656Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: epic-OOMPAH-619--task-OOMPAH-623
    source_sha: c048ba706cbe9b1342b80a67576a49b82887e84a
    completed_at: '2026-07-30T21:38:24.834287+00:00'
---
## Summary

System contract: /home/shedwards/.local/bin/oompah is the canonical CLI used by operators, automation, and spawned processes on this host. It must not silently drift from the running Oompah server while a project-local virtualenv happens to contain newer code. Add a machine-readable build identity containing the source revision to both the standalone CLI and the server health or state surface, while retaining a human-readable oompah --version command. Add a Makefile lifecycle target that installs or upgrades the UV tool at the canonical user path from the exact clean pushed revision selected for the server, verifies command resolution and revision equality, and is invoked by normal source-managed start, restart, and graceful deployment flows at the safe point. Never replace the known-good CLI with a dirty, unpushed, failed, or non-review-ready source state; preserve the old executable on installation failure and report an actionable operator alert. Tests must isolate HOME and UV tool directories, simulate initial install, upgrade, already-current no-op, version mismatch, failed install rollback, dirty checkout refusal, wrong PATH resolution, and successful authenticated task/admin requests after synchronization. Document the canonical path and recovery command. Acceptance criteria: after merged main is deployed, command -v oompah resolves /home/shedwards/.local/bin/oompah; CLI and server report the same git revision; task and admin requests authenticate; every supported graceful lifecycle path either preserves that equality or fails clearly without disrupting the running known-good pair.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 21:32
---
Immediate bootstrap completed: the stale canonical CLI at commit 148184aa could not authenticate to the running server and returned HTTP 401. It was replaced through uv tool install with exact clean main revision 12f63352ba017c6ffe88b0ca730bf3f7f973304e, the revision active when the current server process started. ~/.local/bin/oompah now authenticates successfully. Permanent lifecycle synchronization remains the scope of this task.
---
author: oompah
created: 2026-07-30 21:36
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-30 21:36
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-30 21:38
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 64, Tool calls: 26
- Tokens: 210 in / 5.0K out [5.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 35s
- Log: OOMPAH-623__20260730T213656Z.jsonl
---
author: oompah
created: 2026-07-31 08:33
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-31 08:33
---
Focus: Maintenance Engineer
---
author: oompah
created: 2026-07-31 08:36
---
UNDERSTANDING: Task requires: (1) --version flag showing git revision, (2) build_id in server state/healthz endpoints, (3) Makefile target to install canonical CLI from exact pushed revision, (4) safeguards to prevent dirty/unpushed CLI replacement, (5) comprehensive tests, (6) documentation. Prior work (OOMPAH-621) added CLI credential precedence and revision compatibility testing infrastructure. Proceeding with implementation of version sync mechanisms and Makefile lifecycle target.
---
author: oompah
created: 2026-07-31 08:55
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-31 08:55
---
Focus: Maintenance Engineer
---
author: oompah
created: 2026-07-31 08:56
---
UNDERSTANDING: Task requires implementing CLI-server version sync to prevent silent drift. Key components: (1) Add --version flag to CLI showing git revision, (2) Add build_id to server /healthz and /api/v1/state endpoints, (3) Create Makefile target to install canonical CLI from exact revision, (4) Add safeguards to prevent dirty/unpushed installation, (5) Comprehensive tests for install/upgrade/rollback scenarios, (6) Documentation. Prior work (OOMPAH-621) established credential precedence. Proceeding with implementation.
---
author: oompah
created: 2026-07-31 08:56
---
DISCOVERY: Found test_cli_install_revision_compatibility.py which verifies exact-revision CLI can authenticate against matching server. Current version is 0.1.0 from pyproject.toml. No --version flag or build_id endpoints exist yet. Need to: (1) create version module to get git revision, (2) add --version to CLI, (3) add build_id to /healthz and /api/v1/state, (4) create Makefile install-cli target, (5) comprehensive tests, (6) documentation.
---
<!-- COMMENTS:END -->
