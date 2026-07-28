---
id: OOMPAH-465
type: feature
status: In Progress
priority: 1
title: Implement idempotent terminal-transition staging and audit chains
parent: OOMPAH-457
children: []
blocked_by:
- OOMPAH-461
- OOMPAH-462
- OOMPAH-463
labels:
- focus-complete:duplicate_detector
- focus-complete:docs
assignee: null
created_at: '2026-07-28T13:05:07.200491Z'
updated_at: '2026-07-28T19:24:34.787160Z'
work_branch: epic-OOMPAH-457
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 16c87247-9e70-44b6-b214-0b085ceea7fc
oompah.work_branch: epic-OOMPAH-457
oompah.task_costs:
  total_input_tokens: 293179
  total_output_tokens: 27433
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 293179
      output_tokens: 27433
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 154
    output_tokens: 4775
    cost_usd: 0.0
    recorded_at: '2026-07-28T19:18:20.345054+00:00'
  - profile: default
    model: haiku
    input_tokens: 292719
    output_tokens: 2719
    cost_usd: 0.0
    recorded_at: '2026-07-28T19:19:37.758578+00:00'
  - profile: default
    model: haiku
    input_tokens: 306
    output_tokens: 19939
    cost_usd: 0.0
    recorded_at: '2026-07-28T19:24:19.420709+00:00'
---
## Summary

Implementation scope

Implement a TerminalTransitionCoordinator owned by the orchestrator/server bootstrap. Its request_transition method accepts the current issue, requested terminal target, trigger identity, project/tracker context, and evidence fingerprint. It must atomically persist the request before moving the item to In Validation. Done creates one audit. Merged reuses a current passed Done audit or queues Done then Merged. Archived creates a safe-retirement audit after any pending earlier target. Repeated identical requests coalesce; a changed fingerprint supersedes pending work; stale requests cannot apply status. Use per-project locking and post a concise queued comment once.

Tests

Cover every target and chain, direct Merged with/without current Done evidence, duplicate events, changed fingerprints, simultaneous requests, superseded chains, tracker write failure ordering, restart-recovered requests, and comment deduplication. Run focused tests and make test.

Acceptance criteria

No terminal status is written by staging, every request has one durable chain, direct Merged cannot skip completion auditing, and retries/events cannot create duplicate auditor work.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 19:17
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 19:17
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 19:18
---
Duplicate screening complete: OOMPAH-465 is NOT a duplicate.

Investigation scope:
- All .oompah/tasks directories (200+ tasks) searched for keywords: terminal-transition, Coordinator, request_transition, staging, coalesce, supersede, fingerprint, audit-chain, pending-chain, idempotent-transition, In Validation
- Source code search: no TerminalTransitionCoordinator class exists yet
- Plans and docs: no prior design or implementation of transition staging/coordination
- Epic OOMPAH-457 and all sibling tasks reviewed: OOMPAH-461 (In Validation status), OOMPAH-462 (audit records/fingerprints), OOMPAH-463 (metadata persistence), OOMPAH-464 (grandfather recovery) all complete
- Git history searched for OOMPAH-465, OOMPAH-457, and related keywords

Key findings:
- OOMPAH-465 is a unique child of epic OOMPAH-457 covering transition staging and audit-chain coordination
- Prerequisites OOMPAH-461/462/463/464 are Done and provide: In Validation status, terminal audit records, metadata storage, grandfather baseline
- No existing TerminalTransitionCoordinator implementation, no request_transition method, no staging/coalescing logic
- Closest historical references (OOMPAH-179, OOMPAH-177, OOMPAH-178) cover release-addendum state machines — different domain and now archived

Conclusion: OOMPAH-465 is a unique, original feature implementation task. No prior implementation or duplicate found.
---
author: oompah
created: 2026-07-28 19:18
---
Agent completed successfully in 76s (4929 tokens)
---
author: oompah
created: 2026-07-28 19:18
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 53, Tool calls: 18
- Tokens: 154 in / 4.8K out [4.9K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 16s
- Log: OOMPAH-465__20260728T191707Z.jsonl
---
author: oompah
created: 2026-07-28 19:18
---
Focus handoff required before leaving `duplicate_detector`. Add a comment headed `Focus handoff: duplicate_detector` with outcome, evidence, remaining work, and next focus.
---
author: oompah
created: 2026-07-28 19:18
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 19:18
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 19:19
---
Agent completed successfully in 64s (295438 tokens)
---
author: oompah
created: 2026-07-28 19:19
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 4
- Tokens: 292.7K in / 2.7K out [295.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 4s
- Log: OOMPAH-465__20260728T191835Z.jsonl
---
author: oompah
created: 2026-07-28 19:19
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-28 19:19
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 19:19
---
Focus: Technical Writer
---
author: oompah
created: 2026-07-28 19:20
---
Understanding: Technical Writer phase for OOMPAH-465 (Terminal-Transition Staging & Audit Chains).

Scope:
- Create comprehensive design/architecture documentation for TerminalTransitionCoordinator
- Document idempotent staging, coalescing, and audit-chain coordination
- Explain integration with existing In Validation status, terminal audit records, and metadata persistence

Prerequisites satisfied:
- OOMPAH-461: In Validation status (statuses.py)
- OOMPAH-462: Terminal audit records (terminal_audit.py)
- OOMPAH-463: Metadata persistence (evidenced by tracker/metadata storage)
- OOMPAH-464: Grandfather recovery baseline

Key components to document:
1. TerminalTransitionCoordinator architecture and interface
2. Request staging and persistence model
3. Coalescing and superseding logic
4. Terminal state chains (Done → Merged, Archived rules)
5. Per-project locking strategy
6. Comment deduplication
7. Recovery and restart semantics
8. Testing requirements

Approach: Create design doc in plans/ that serves as implementation spec, then hand off to feature agent for implementation.
---
author: oompah
created: 2026-07-28 19:21
---
Discovery: Created comprehensive design document at plans/terminal-transition-coordinator.md

Content:
- Full architecture and design principles
- API specification for request_transition method  
- Detailed state chains (Done, Merged, Archived)
- Coalescing and superseding logic
- Per-project locking strategy
- Comment deduplication mechanism
- Recovery and restart semantics
- Integration points (bootstrap, orchestrator, auditor)
- Testing strategy with 13+ test cases
- Data schema and JSON storage format

Key design highlights:
1. Atomicity: Persistence before status move ensures crash recovery
2. Coalescing: Identical requests deduplicated by fingerprint
3. Chains: Done (1 audit) → Merged (1-2 audits) → Archived (deferred)
4. Per-project locking: Concurrent requests serialize safely
5. Comment dedup: Persisted set prevents duplicate notifications

The design is ready for implementation. Next focus: Feature agent for implementation.
---
author: oompah
created: 2026-07-28 19:22
---
Implementation: Documentation complete.

Created two comprehensive reference documents:

1. **plans/terminal-transition-coordinator.md** (14KB)
   - Full architecture and design principles
   - Detailed API specification with 7-step algorithm
   - State chain logic (Done, Merged, Archived)
   - Coalescing and superseding mechanics
   - Per-project locking strategy
   - Comment deduplication with persistence
   - Recovery and restart semantics
   - Integration points (bootstrap, orchestrator, auditor)
   - 13 test case specifications
   - Data schema and JSON storage format

2. **plans/terminal-transition-coordinator-api.md** (18KB)
   - Quick-reference Python class template
   - Method signatures with docstrings
   - Implementation stubs for each operation
   - Bootstrap and orchestrator integration code
   - Storage schema and JSON examples
   - Testing checklist
   - Error handling table
   - Performance considerations

These documents provide a complete specification for implementation. All requirements from OOMPAH-465 are covered:
✓ request_transition API design
✓ Atomic persistence before status move
✓ Done/Merged/Archived chains with correct sequencing
✓ Coalescing identical requests
✓ Fingerprint-based superseding
✓ Per-project locking
✓ Concise queued comment (once per task)
✓ Recovery semantics
✓ Comment deduplication
✓ Complete test strategy

Ready for feature implementation agent.
---
author: oompah
created: 2026-07-28 19:22
---
Focus handoff: docs

OUTCOME:
Comprehensive design and API documentation created for TerminalTransitionCoordinator. All requirements from OOMPAH-465 are fully specified and ready for implementation.

EVIDENCE & FILES:
- plans/terminal-transition-coordinator.md (14KB) — Complete architecture, API spec, state chains, concurrency, testing
- plans/terminal-transition-coordinator-api.md (18KB) — Python class template, method stubs, bootstrap/orchestrator integration, storage schema, test checklist
- Reviewed existing infrastructure: terminal_audit.py (audit records), statuses.py (IN_VALIDATION), bootstrap.py (service initialization)
- Examined test patterns in tests/test_terminal_audit.py

REQUIREMENTS COVERED:
✓ request_transition API (7-step algorithm: lock → load → coalesce/supersede → chain → persist → status → comment)
✓ Atomic persistence before status move (ensures crash recovery)
✓ Terminal state chains: Done (1 audit), Merged (1-2 audits with Done reuse), Archived (defers to pending)
✓ Idempotent coalescing by fingerprint
✓ Fingerprint-based superseding with old audit marked SUPERSEDED
✓ Per-project async locks (prevent concurrent requests for same task)
✓ Concise queued comment posted once per task (persisted set)
✓ Recovery semantics (restart-recovered requests load from storage, no duplicates)
✓ No terminal status written by coordinator (auditor applies statuses)
✓ Complete test strategy with 13+ test cases

REMAINING WORK:
1. Implement TerminalTransitionCoordinator class (oompah/terminal_transition_coordinator.py)
   - Use template in plans/terminal-transition-coordinator-api.md as starting point
   - Implement all methods with full chain logic
   - Store audit chains in project metadata (JSON serialization)
   - Persist queued_comments_posted set

2. Integrate into server bootstrap (oompah/bootstrap.py)
   - Create coordinator in setup_services
   - Attach to orchestrator

3. Add orchestrator method for request_terminal_transition

4. Implement tests (tests/test_terminal_transition_coordinator.py)
   - 13+ test cases from design doc
   - Coverage: chains, coalescing, superseding, locking, restart recovery, comment dedup

5. Run focused tests: make test -- tests/test_terminal_transition_coordinator.py -v

RISKS & NOTES:
- Audit chain persistence must occur before tracker status write (atomicity guarantee)
- Fingerprint computation must be deterministic (already ensured by terminal_audit.py)
- Per-project locks are async; coordinate with orchestrator's existing locking
- Comment deduplication set must survive restarts (persist to metadata)
- Direct Merged (without current Done) must queue Done first; cannot skip completion auditing

NEXT FOCUS: Feature agent for implementation.
Recommended: Start with method stubs in API reference, implement chain logic, then add tests.
---
author: oompah
created: 2026-07-28 19:23
---
Completion: Technical Writer phase finished. Documentation ready for implementation.

DELIVERABLES:
1. plans/terminal-transition-coordinator.md (14KB)
   - Complete architecture, design principles, requirements
   - Detailed 7-step request_transition algorithm
   - State chains (Done, Merged, Archived) with pseudocode
   - Coalescing, superseding, and restart recovery
   - Testing strategy with 13+ test cases

2. plans/terminal-transition-coordinator-api.md (18KB)
   - Python class template with method stubs
   - Integration with TerminalAuditMetadataStore (existing persistence layer)
   - Bootstrap and orchestrator integration code
   - Storage schema and JSON examples
   - Test checklist and error handling table

DESIGN HIGHLIGHTS:
✓ Atomic persistence (via TerminalAuditMetadataStore) before status move
✓ Per-project async locks for concurrent request safety
✓ Coalescing by (target, fingerprint) deduplication
✓ Fingerprint-based superseding with SUPERSEDED marking
✓ Chain semantics: Done(1), Merged(1-2 with Done reuse), Archived(deferred)
✓ Direct Merged cannot skip completion auditing
✓ Queued comment posted once per task (persisted set)
✓ Restart recovery from stored metadata
✓ No terminal statuses written by coordinator (auditor applies)

INTEGRATION READY:
- Aligns with existing TerminalAuditMetadata and TerminalAuditMetadataStore patterns
- Bootstrap integration point clear (setup_services in oompah/bootstrap.py)
- Orchestrator usage pattern documented
- Per-project write locks leverage existing ProjectStore locking

STATUS: Handed off to feature implementation agent with focus:feature label.
---
author: oompah
created: 2026-07-28 19:24
---
Agent completed successfully in 266s (20245 tokens)
---
author: oompah
created: 2026-07-28 19:24
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 84, Tool calls: 37
- Tokens: 306 in / 19.9K out [20.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 4m 26s
- Log: OOMPAH-465__20260728T191959Z.jsonl
---
author: oompah
created: 2026-07-28 19:24
---
Focus handoff from `docs` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-28 19:24
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-28 19:24
---
Focus: Software Engineer
---
<!-- COMMENTS:END -->
