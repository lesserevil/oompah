# Dashboard WebSocket state versioning

The dashboard WebSocket uses protocol version 1 with an additive envelope.
Existing clients can continue to read `type` and their existing payload
fields; clients that understand the envelope can detect transport loss and
authoritative snapshot generations.

## Envelope

Every server-to-client message has these top-level fields:

| Field | Meaning |
| --- | --- |
| `protocol_version` | Integer envelope version (`1`). |
| `epoch` | The service instance identifier (`service_instance_id`). A process restart creates a new epoch. |
| `delivery_seq` | A 1-based, contiguous sequence in wire-send order for this WebSocket connection. It is not shared across clients. |
| `state_revision` | The authoritative state revision represented by a `state` payload. On another message type, it is the current state revision observed when that message is sent. |
| `issue_revision` | The authoritative issue revision represented by an `issues` payload. On another message type, it is the current issue revision observed when that message is sent. |

For example, a state message has the following shape (the `data` object is
abbreviated):

```json
{
  "type": "state",
  "protocol_version": 1,
  "epoch": "4d0a…",
  "delivery_seq": 12,
  "state_revision": 18,
  "issue_revision": 11,
  "data": {"running": [], "service_instance_id": "4d0a…"}
}
```

An activity, pong, refresh response, or console/error control message also
has the same envelope fields. Its `state_revision` and `issue_revision` are
observations of the current counters; they do not version an absent state or
issues payload. Only apply a revision to payload data when the message type
contains that payload (`state` for `state_revision`, or `issues` for
`issue_revision`).

The envelope is additive: clients that do not understand these fields may
continue using the existing `type`, `data`, and message-specific fields.

## Authoritative revisions

State and issue revisions are independent authoritative generations and are
monotonic within an epoch.

- A state observer callback advances `state_revision` when its snapshot is
  accepted. A callback with an older `generated_at` value is ignored, and an
  identical callback does not create a new generation.
- Issue-cache invalidation advances `issue_revision`. A rebuild records the
  revision that belongs to the serialized board in the snapshot cache.
- A board sent during the refresh window retains its older
  `issue_revision`; it is never labelled with the newly invalidated revision.
- State delivery is trailing-edge coalesced. Every accepted snapshot replaces
  the cached state and marks delivery dirty. If the 500 ms delivery throttle
  is active, one timer sends the latest cached snapshot after the window. A
  connected client therefore eventually receives the final accepted state
  revision while the connection remains available.

A revision can advance without a message being sent to a particular client,
for example while no clients are connected or while several state callbacks
are coalesced. A revision jump is therefore an authoritative-generation gap,
not by itself a transport gap. State and issue revisions may advance
independently.

## Client recovery

Clients should track `(epoch, delivery_seq)` for transport ordering and the
two revisions independently:

1. On the first message for an epoch, record its epoch and sequence as the
   baseline.
2. Within one epoch, a non-contiguous `delivery_seq` indicates a transport or
   fan-out gap. Request a refresh or reconnect; do not infer a missing payload
   from a revision alone.
3. A contiguous message whose applicable payload revision skips a number
   indicates that one or more authoritative generations were coalesced or
   were not observed by this client. The payload is still labelled with the
   generation it contains, so it can be applied as the latest snapshot.
4. If `epoch` changes, discard all sequence and revision comparisons from the
   previous epoch and bootstrap again. Do not compare revisions across epochs.

## Restart and reconnect semantics

The epoch is the stream boundary. A process restart creates a new
`service_instance_id`; state and issue revisions begin at zero, and the first
accepted snapshots in that process become revision 1. WebSocket connections
are process-local and are expected to close during restart.

A reconnect starts `delivery_seq` at 1. Bootstrap sends state first and issues
second for that connection, each with its own sequence number. A later
refresh, activity, pong, console event, or error/control message continues the
same sequence. A new connection has an independent sequence even when another
client remains connected.

The server assigns `delivery_seq` immediately before each socket send while
holding the per-connection send ordering lock. Observer callbacks may run on
different threads, but revision counters and snapshot/cache pairs are
protected so a stale payload cannot be stamped with a newer revision.
