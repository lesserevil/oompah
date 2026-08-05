---
id: OOMPAH-817
type: bug
status: Open
priority: 1
title: Persist standalone-clone recovery objects before publishing refs
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-05T01:04:50.363142Z'
updated_at: '2026-08-05T01:09:25.293286Z'
work_branch: epic-OOMPAH-763--task-OOMPAH-817
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 8f17a9efe143d1c24e084b6d486c54c8213a0ca099304e8b6e7c26c6abed989e
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-05T01:09:16.440575+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: Reviewed all 10 active non-terminal peer tasks (OOMPAH-763,\
    \ OOMPAH-767\u2013771, OOMPAH-807\u2013816). None address the specific bug of\
    \ recovery checkpoint objects not being transferred/fetched into the authoritative\
    \ repository before publishing recovery refs in `preserve_worktree_changes`. OOMPAH-814\
    \ is a related incident that triggered discovery of this bug but tracks test fixture\
    \ determinism, not the persistence failure itself. The remaining tasks cover workflow\
    \ engine architecture, scheduling, dispatch fencing, integration queue management,\
    \ and resource leasing\u2014all distinct from recovery checkpoint durability.\
    \ OOMPAH-817 is a focused bug fix with no active duplicate.\nI'll analyze the\
    \ provided task corpus to determine whether OOMPAH-817 is a duplicate of any existing\
    \ active task.\n\n**Understanding OOMPAH-817**:\n- Core issue: `preserve_worktree_changes`\
    \ creates recovery checkpoints in standalone clone object databases, then attempts\
    \ to publish recovery refs in the authoritative repo, but the repo lacks the checkpoint\
    \ objects \u2192 `update-ref` fails with \"nonexistent object\"\n- Impact: Task\
    \ left In Progress with no running worker/recovery path\n- Solution scope: Transfer/fetch\
    \ objects into authoritative repo before publishing recovery refs, or store refs\
    \ in the object database owning the checkpoint\n- Specific to: recovery checkpoint\
    \ durability across linked worktrees and standalone clones\n\n**Reviewing active\
    \ (non-terminal) peer tasks**:\n\n1. **OOMPAH-763** (In Progress, epic): Workflow\
    \ engine migration\u2014broader scope, covers multiple domains\n2. **OOMPAH-767**\
    \ through **OOMPAH-771**: Workflow engine child epics\u2014each addresses specific\
    \ domain (facts, decisions, jobs, liveness, retirement)\n3. **OOMPAH-807** (Open,\
    \ task): Revisionless audits for metadata-only Archived\u2014audit lifecycle,\
    \ different scope\n4. **OOMPAH-808** (Open, task): Fence nested-epic dispatch\
    \ until prerequisite code reachable\u2014dispatch fencing, different issue\n5.\
    \ **OOMPAH-809** (Open, task): Reserve workflow-repair capacity\u2014scheduler\
    \ capacity starvation, unrelated to object persistence\n6. **OOMPAH-810** (Open,\
    \ task): Return completed auditor command results\u2014ACP session transport,\
    \ unrelated\n7. **OOMPAH-811** (Open, task): Atomically rearm integration ownership\
    \ on rebase\u2014integration queue saga, different problem\n8. **OOMPAH-814**\
    \ (Ready to Integrate, task): Make submit-queue fixtures deterministic\u2014test\
    \ fixture concurrency, unrelated\n9. **OOMPAH-815** (In Progress, task): Preserve\
    \ accepted child branch identity\u2014branch identity fencing, different issue\n\
    10. **OOMPAH-816** (In Progress, task): Serialize heavyweight auditor validation\u2014\
    resource lease for validation commands, unrelated"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: fdbe7db9-0302-4afc-be86-ad15708ff4ae
oompah.work_branch: epic-OOMPAH-763--task-OOMPAH-817
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-763--task-OOMPAH-817
  base_branch: epic-OOMPAH-763
  base_sha: 30dc2b2075a48c6c542da55a46ad0285f492d527
  updated_at: '2026-08-05T01:08:20.587903+00:00'
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 2022
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 2022
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 2022
    cost_usd: 0.0
    recorded_at: '2026-08-05T01:09:16.439250+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-817__20260805T010831Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: epic-OOMPAH-763--task-OOMPAH-817
    source_sha: 30dc2b2075a48c6c542da55a46ad0285f492d527
    completed_at: '2026-08-05T01:09:16.488925+00:00'
---
## Summary

Live reproduction during direct-owner takeover of OOMPAH-814 on 2026-08-05: ProjectStore.preserve_worktree_changes created recovery checkpoint 515cbc2c84ef6bf955468534a163b7fc77b33f2a inside the registered standalone task clone, then attempted git update-ref refs/oompah/recovery/... in project.repo_path. The authoritative repo did not contain that standalone clone's new object, so update-ref failed with "trying to write ref ... with nonexistent object 515cbc2..." after the checkpoint had already mutated the task branch. The transition left OOMPAH-814 In Progress with no running worker, retry, quality gate, or owner claim until an operator retried the claim and manually reconciled the checkpoint. Implementation scope: make recovery snapshots durable across both linked worktrees and registered standalone clones by transferring/fetching the exact commit/tree objects into the authoritative repository before publishing the recovery ref, or by storing the ref in the object database that actually owns the checkpoint and making every recovery reader use that same authority. Treat checkpoint creation plus durable ref publication as a fenced transaction: verify the exact object is readable from the chosen recovery authority before reporting success; on transfer/ref failure preserve the task branch and emit an actionable, automatically retryable recovery state without stranding the task. Do not reset, clean, delete, or rewrite the task checkout. Relevant code: oompah/projects.py _worktree_recovery_ref and preserve_worktree_changes/recovery readers; orchestrator owner-takeover/worker-exit recovery handling. Required tests: linked worktree control; separate standalone clone with distinct object database; missing-object update-ref reproduction; interrupted object transfer; retry/idempotence; restart; exact snapshot/ref resolution; dirty and active-operation checkpoints; and proof the task returns to a recoverable owner/scheduler state rather than ownerless In Progress. Acceptance: every reported recovery_ref resolves to snapshot_head in its authoritative repository, recovery is restart-safe and idempotent, and a persistence failure cannot strand a task or destroy its worktree.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-05 01:08
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-05 01:08
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-05 01:09
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 2.0K out [2.0K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 6s
- Log: OOMPAH-817__20260805T010831Z.jsonl
---
<!-- COMMENTS:END -->
