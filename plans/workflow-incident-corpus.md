# Workflow incident corpus

OOMPAH-774 establishes a permanent replay corpus for the stuck-task failures
that motivated the unified workflow engine. The executable source is
`tests/fixtures_workflow_incidents.py`; this document records its boundaries
and intended consumers.

| Source | Historical failure | Expected durable decision |
|---|---|---|
| OOMPAH-562 | A Ready child has a merged prerequisite absent from stale epic ancestry, so no row is claimable and no repair owner exists | Preserve the private head and enqueue one bounded epic-branch reconciliation job |
| OOMPAH-731 | A direct epic rebase publishes its own target and is then rejected as an ordinary child submission | Prove publication, reconcile only a safe checkout, bypass child integration, and request audited Done |
| OOMPAH-732 | A benign tracker timestamp changes the delivery generation while the exact pushed head is unchanged | Keep the authority generation and create one independent standalone delivery job |
| OOMPAH-739 | Normally deleted source refs are treated as proof that audited historical landing did not happen | Preserve verified Merged state from durable audit, merge, target, and ancestry evidence |
| OOMPAH-748 | Nested-child Merged requires parent root landing while parent review requires the child to be Merged | Accept audited landing on the immediate parent target and leave root landing as a separate fact |
| OOMPAH-749 | Unbounded historical audit replay runs before live Ready selection | Claim live work first, then replay one cursor-bounded history batch |
| OOMPAH-751 | An expected advisory peer denial enters the actionable handoff-failure channel | Return a non-disclosing policy result without changing task authority, auth health, or submission capability |

Each scenario contains:

- authoritative native task status, hierarchy, dependency, and metadata facts;
- branch/ref/ancestry facts when Git containment is relevant;
- unavailable forge observations as immutable audit/review evidence, never as
  mocked lifecycle decisions;
- the exact historical failure predicate;
- the expected reason, disposition, owner, status writes, durable jobs,
  alert severity, evidence, and invariants;
- authoritative after-facts for restart and idempotency assertions.

The fixture materializers write tasks through `OompahMarkdownTracker` and
construct real temporary Git commit DAGs. Future transition-service,
WorkDecision, durable-job, liveness, fault-injection, and scale tests should
import this corpus rather than reconstructing incident-specific test doubles.
Adding a new systemic incident requires an actionable oompah task first, then
a corpus scenario whose before-facts reproduce the failure and whose expected
decision is expressed without depending on an orchestrator private method.

