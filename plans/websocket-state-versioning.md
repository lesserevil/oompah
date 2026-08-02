# Dashboard WebSocket state versioning

The dashboard WebSocket uses a versioned, additive envelope. Existing clients
may continue to read `type` and their existing payload fields; clients that
understand version 1 can detect both transport loss and authoritative snapshot
loss.

Every server-to-client message has these top-level fields:

| Field | Meaning |
| --- | --- |
| `protocol_version` | Integer protocol version (`1`). |
| `epoch` | The process `service_instance_id`. It changes on service restart. |
| `delivery_seq` | 1-based, contiguous sequence for this WebSocket connection. It is not shared across clients. |
| `state_revision` | Latest revision represented by the state payload, or the current state revision for messages without a state payload. |
| `issue_revision` | Revision represented by the issue payload, or the current issue revision for messages without an issue payload. |

State and issue revisions are independent authoritative generations. A state
observer callback advances the state revision when its snapshot is accepted;
callbacks that arrive after a newer timestamped snapshot are ignored. Issue
cache invalidation advances the issue revision, and a rebuild records that
revision on the board that was serialized. A stale board sent during the
refresh window retains its older `issue_revision` rather than being labelled as
the newly invalidated generation.

State broadcasts are trailing-edge coalesced. Every accepted snapshot replaces
the cached state and marks delivery dirty. If the 500 ms delivery throttle is
active, one timer sends the latest cached snapshot after the window. Thus a
connected client eventually receives the final accepted revision, even when
several observer callbacks occur during one throttle interval.

## Restart and reconnect semantics

The epoch is the stream boundary. A process restart creates a new
`service_instance_id`; state and issue revisions begin at zero and the first
accepted snapshots become revision 1. WebSocket connections are process-local
and therefore are expected to close during restart. Clients must discard
sequence and revision comparisons from the previous epoch and bootstrap again
after reconnecting. A reconnect starts `delivery_seq` at 1, while a temporary
transport gap within one epoch is detected by a non-contiguous sequence.

`delivery_seq` is assigned immediately before each socket send, including
bootstrap state/issues, refresh responses, activity, pong, console events, and
errors. A sequence gap therefore indicates a transport/fan-out problem; a
revision jump with contiguous delivery indicates that authoritative snapshots
were coalesced or that the client missed a generation.
