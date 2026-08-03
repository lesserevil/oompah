---
id: OOMPAH-717
type: task
status: In Progress
priority: null
title: Prevent generated hook collisions from hot-looping and starving epic integration
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-03T13:00:53.157839Z'
updated_at: '2026-08-03T13:03:04.228160Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: d8ace93bf4e88a08c6506eeec48f53bb3de7feb3979aff430a84719b449ac79f
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-03T13:01:42.096610+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: ** The task corpus contains no active task addressing\
    \ integration executor hot-looping, generated hook collisions, or queue starvation\
    \ issues. The closest completed tasks (OOMPAH-162, OOMPAH-163) address orthogonal\
    \ epic workflow problems. OOMPAH-717 is a distinct, previously untracked issue\
    \ specific to the integration queue and executor error handling.\nLooking at the\
    \ task corpus, I need to determine if OOMPAH-717 is a duplicate of any existing\
    \ active task.\n\n**Analysis:**\n\nOOMPAH-717 addresses a specific, compound problem:\n\
    1. Generated Oompah helpers (like `.oompah-no-hooks/prepare-commit-msg`) causing\
    \ untracked-file collisions during epic integration\n2. Error reporting masking\
    \ (successful checkout stderr hiding actual merge failures)\n3. Unbounded hot-looping\
    \ in the integration executor without backoff or attempt limits\n4. Starvation\
    \ of independent queue groups when one row repeatedly fails\n\nLet me examine\
    \ the task corpus for overlapping issues:\n\n**Reviewed Active/Terminal Tasks:**\n\
    - **OOMPAH-162** (Archived): Handles stacked epic children merged to default branch\u2014\
    orthogonal issue\n- **OOMPAH-163** (Archived): Validates epic target branches\
    \ through dispatch\u2014different validator problem\n- **OOMPAH-164-175** (All\
    \ Archived): Cover epic workflow standardization, release branches, documentation\u2014\
    not integration executor or queue health\n- **OOMPAH-10** (Archived): Native tracker\
    \ sync failures\u2014different component (markdown tracker, not integration)\n\
    - **OOMPAH-156-161** (All Archived): Error handling, task deduplication, API issues\u2014\
    not integration executor collision/retry logic\n\n**Conclusion:**\n\nNo active\
    \ (non-terminal) task covers the specific problem of:\n- Generated hook collisions\
    \ in shared epic worktrees causing executor failures\n- Error masking in integration\
    \ executor\n- Bounded retry/backoff for poisoned queue rows\n- Head-of-line protection\
    \ and queue health diagnostics\n\nAll related tasks are in terminal states (Archived/Merged).\
    \ OOMPAH-717 describes a genuinely new issue with no prior active task.\n\n---\n\
    \nFocus handoff: duplicate_detector\n\nDuplicate preflight verdict: no_duplicate\n\
    \nMatches: none\n\n**Evidence:** The task corpus contains no active task addressing\
    \ integration executor hot-looping, generated hook collisions, or queue starvation\
    \ issues. The closest completed tasks (OOMPAH-162, OOMPAH-163) address orthogonal\
    \ epic"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 91e65009-e787-45cd-857f-a01722ed7500
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 1538
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 1538
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1538
    cost_usd: 0.0
    recorded_at: '2026-08-03T13:01:42.095113+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-717__20260803T130115Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-717
    source_sha: b97187abdd50d76deda75be427f26049fd396cb6
    completed_at: '2026-08-03T13:01:42.112362+00:00'
---
## Summary

Live reproduction: NODEVIRT-8 remained Ready to Integrate for more than 3,400 automatic attempts. Its task head tracks .oompah-no-hooks/prepare-commit-msg while the shared epic worktree contains the same Oompah-generated helper as an untracked file. The executor fast-forward therefore fails because the untracked helper would be overwritten. Error selection reports the successful checkout stderr (Already on epic-NODEVIRT-2) instead of the failing merge stderr, classifies the result as an epic-head race, and retries immediately without backoff or an attempt bound. Dependent Ready rows remain at attempts=0.

Implementation scope:
- Treat every Oompah-generated worktree helper path as non-deliverable at submission and integration boundaries, including legacy task heads that already track a helper. Reject with an actionable repair status or sanitize through an explicit safe repair path before mutating the shared epic branch.
- In the integration executor, report stderr from the command that actually failed; successful checkout output must never mask reset or merge failures.
- Distinguish genuine remote epic-head compare-and-swap races from deterministic local preparation/merge failures. Do not classify untracked-file collisions as immediately retryable epic-head races.
- Add bounded retry/backoff and head-of-line protection so one repeatedly failing row cannot hot-loop thousands of times or prevent independent eligible queue groups from progressing.
- Surface an alert/health diagnostic for excessive Ready attempts with the exact task, failing step, real error, next retry, and repair action.

Relevant code: oompah/integration_executor.py, oompah/integration_queue.py, oompah/orchestrator.py integration routing and queue health, ProjectStore generated-helper handling, and dashboard integration diagnostics.

Required tests:
- Reproduce a shared epic worktree with an untracked .oompah-no-hooks/prepare-commit-msg and a submitted task head that tracks that path; prove the real collision is reported and no immediate retry loop occurs.
- Prove successful checkout stderr cannot mask a failing reset or merge.
- Prove a genuine epic compare-and-swap race remains retryable.
- Prove a poisoned row is bounded/backed off and another independent eligible epic/project row advances.
- Prove clean task heads still integrate normally and generated helpers never enter delivered trees.

Acceptance criteria:
- The NODEVIRT-8 reproduction cannot exceed the configured retry budget or monopolize integration processing.
- Operators see the real untracked-file collision and a safe repair path.
- Independent Ready work proceeds while the failed row waits.
- Focused integration executor/queue/orchestrator/ProjectStore tests and make test pass.
## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-03 13:01
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-03 13:01
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-03 13:01
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.5K out [1.5K total]
- Cost: $0.0000
- Exit: normal, Duration: 32s
- Log: OOMPAH-717__20260803T130115Z.jsonl
---
author: oompah
created: 2026-08-03 13:01
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-03 13:01
---
Focus: Frontend Developer
---
author: oompah
created: 2026-08-03 13:02
---
Understanding: the failure combines generated-helper paths entering submitted heads, masked subprocess errors, incorrect race classification, and an unbounded queue retry loop. I’ll trace ProjectStore, integration executor/queue, orchestrator health routing, and dashboard diagnostics; implement safe rejection/repair signaling, accurate errors, bounded backoff with fair scheduling, then add focused regression tests.
---
<!-- COMMENTS:END -->
