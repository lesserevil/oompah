# Epic workflow facts

`oompah.epic_workflow` is the shared evidence boundary for shared and nested
epic rollups. `EpicFactCollector` walks the configured containment graph,
rejects repeated identifiers/cycles, resolves each child's immediate target
from its parent identity, and requests one `LandingFact` per child plus one
for the epic branch itself.

`evaluate_task` consumes the enriched containment fact for epic decisions. A
normal child must be `Done` and have positive landing evidence on its
immediate epic branch. A nested epic is checked by its positive landing fact
alone; its parent's derived tracker status is never an eligibility input.
This keeps the proof graph acyclic while allowing a nested branch to land on
an open parent branch.

Positive landing facts are append-only in the shared workflow job SQLite
ledger. A fresh process can therefore replay exact Git ancestry or
patch-equivalence evidence after the source ref is deleted. Maintenance actions
such as rebase/repair, terminal validation, cleanup, and restart recovery use
the same generation-fenced job store through `EpicWorkflowController`.

Legacy orchestrator gates use this path when `workflow_engine_mode` is
`enforce`; shadow scans use it for epics in `shadow` mode. Missing Git,
containment, or target evidence fails closed and schedules a bounded refresh
job rather than manufacturing an empty child set.
