from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from oompah.coordination import (
    COORDINATION_SCHEMA_VERSION,
    MAX_MESSAGE_BYTES,
    CoordinationStore,
    derive_peer_suggestions,
)
from oompah.models import BlockerRef, Issue
from oompah.orchestrator import Orchestrator


def _issue(identifier: str, **kwargs) -> Issue:
    return Issue(
        id=identifier,
        identifier=identifier,
        title=identifier,
        state=kwargs.pop("state", "Open"),
        project_id=kwargs.pop("project_id", "project-1"),
        **kwargs,
    )


def test_store_survives_restart_and_preserves_fifo(tmp_path):
    path = tmp_path / "coordination.sqlite3"
    store = CoordinationStore(str(path))
    first = store.append(
        project_id="p1",
        sender_task="T-1",
        recipient_task="T-2",
        text="first",
        idempotency_key="one",
        sender_run_id="run-1",
        recipient_run_id="run-2",
    )
    second = store.append(
        project_id="p1",
        sender_task="T-1",
        recipient_task="T-2",
        text="second",
        changed_paths=["b.py", "a.py", "a.py"],
    )
    assert store.schema_version == COORDINATION_SCHEMA_VERSION
    store.close()

    reopened = CoordinationStore(str(path))
    inbox = reopened.inbox("p1", "T-2")
    assert [message.id for message in inbox] == [first.id, second.id]
    assert inbox[1].changed_paths == ("a.py", "b.py")
    assert inbox[0].sender_run_id == "run-1"
    assert inbox[0].recipient_run_id == "run-2"


def test_idempotency_is_scoped_to_project_and_sender(tmp_path):
    store = CoordinationStore(str(tmp_path / "coordination.sqlite3"))
    first = store.append(
        project_id="p1",
        sender_task="T-1",
        recipient_task="T-2",
        text="first",
        idempotency_key="stable",
    )
    repeated = store.append(
        project_id="p1",
        sender_task="T-1",
        recipient_task="T-3",
        text="ignored retry payload",
        idempotency_key="stable",
    )
    other = store.append(
        project_id="p1",
        sender_task="T-9",
        recipient_task="T-2",
        text="other sender",
        idempotency_key="stable",
    )
    assert repeated == first
    assert other.id != first.id


def test_concurrent_writers_do_not_lose_messages(tmp_path):
    store = CoordinationStore(str(tmp_path / "coordination.sqlite3"))

    def _append(index: int):
        return store.append(
            project_id="p1",
            sender_task=f"T-{index}",
            recipient_task="T-target",
            text=f"message {index}",
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        messages = list(pool.map(_append, range(40)))
    assert len({message.id for message in messages}) == 40
    assert len(store.inbox("p1", "T-target", limit=100)) == 40


def test_read_delivery_and_bounded_retention(tmp_path):
    store = CoordinationStore(str(tmp_path / "coordination.sqlite3"))
    message = store.append(
        project_id="p1",
        sender_task="T-1",
        recipient_task="T-2",
        text="hello",
    )
    assert store.unread_count("p1", "T-2") == 1
    assert store.mark_delivered(message.id)
    assert store.mark_read(message.id)
    assert store.unread_count("p1", "T-2") == 0
    assert store.prune_before("9999-01-01T00:00:00+00:00", limit=1) == 1
    assert store.get(message.id) is None


def test_orchestrator_inbox_marks_returned_messages_read(tmp_path):
    store = CoordinationStore(str(tmp_path / "coordination.sqlite3"))
    message = store.append(
        project_id="p1",
        sender_task="T-1",
        recipient_task="T-2",
        text="hello",
    )

    class _CoordinationOnly:
        coordination_store = store

    result = Orchestrator.coordination_inbox(
        _CoordinationOnly(),
        "p1",
        "T-2",
        unread_only=True,
    )

    assert [item["id"] for item in result] == [message.id]
    refreshed = store.get(message.id)
    assert refreshed is not None
    assert refreshed.delivered_at is not None
    assert refreshed.read_at is not None
    assert store.unread_count("p1", "T-2") == 0


def test_checkpoint_survives_restart_and_replaces_prior_paths(tmp_path):
    path = tmp_path / "coordination.sqlite3"
    store = CoordinationStore(str(path))
    store.checkpoint(
        project_id="p1",
        task_identifier="T-1",
        changed_paths=["old.py"],
    )
    store.checkpoint(
        project_id="p1",
        task_identifier="T-1",
        changed_paths=["new.py", "new.py"],
        commit_sha="abc1234",
        summary="Current interface is stable.",
    )
    store.close()

    reopened = CoordinationStore(str(path))
    checkpoint = reopened.checkpoints("p1")["T-1"]
    assert checkpoint["changed_paths"] == ["new.py"]
    assert checkpoint["commit_sha"] == "abc1234"


def test_message_validation(tmp_path):
    store = CoordinationStore(str(tmp_path / "coordination.sqlite3"))
    with pytest.raises(ValueError, match="text is required"):
        store.append(
            project_id="p1",
            sender_task="T-1",
            recipient_task="T-2",
            text="",
        )
    with pytest.raises(ValueError, match="UTF-8 bytes"):
        store.append(
            project_id="p1",
            sender_task="T-1",
            recipient_task="T-2",
            text="x" * (MAX_MESSAGE_BYTES + 1),
        )


def test_peer_suggestions_cover_dependencies_siblings_and_overlap():
    task = _issue(
        "T-1",
        parent_id="E-1",
        blocked_by=[BlockerRef(id="T-2", identifier="T-2")],
    )
    suggestions = derive_peer_suggestions(
        task,
        [
            task,
            _issue("T-2", parent_id="E-1"),
            _issue("T-3", parent_id="E-1"),
            _issue("T-4"),
            _issue("T-terminal", parent_id="E-1", state="Done"),
            _issue("OTHER-1", project_id="project-2", parent_id="E-1"),
        ],
        changed_paths={
            "T-1": ["src/shared.py"],
            "T-4": ["src/shared.py"],
        },
    )
    by_id = {peer.identifier: set(peer.reasons) for peer in suggestions}
    assert by_id["T-2"] == {"dependency", "epic-sibling"}
    assert by_id["T-3"] == {"epic-sibling"}
    assert by_id["T-4"] == {"changed-path-overlap"}
    assert "T-terminal" not in by_id
    assert "OTHER-1" not in by_id


def test_peer_suggestions_include_dependencies_inherited_from_parent_epic():
    parent = _issue(
        "E-1",
        blocked_by=[BlockerRef(id="T-2", identifier="T-2")],
    )
    child = _issue("T-1", parent_id="E-1")
    suggestions = derive_peer_suggestions(
        child,
        [parent, child, _issue("T-2")],
    )

    by_id = {peer.identifier: set(peer.reasons) for peer in suggestions}
    assert by_id["T-2"] == {"dependency"}
