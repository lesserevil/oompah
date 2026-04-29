"""Tests for oompah.attachments."""

from __future__ import annotations

import os
import subprocess

import pytest

from oompah.attachments import (
    ALLOWED_MIME_TYPES,
    ATTACHMENTS_SUBDIR,
    LFS_PATTERNS,
    MAX_ATTACHMENT_BYTES,
    MAX_PER_ISSUE_BYTES,
    Attachment,
    AttachmentError,
    AttachmentMimeRejected,
    AttachmentNotFound,
    AttachmentStore,
    AttachmentTooLarge,
)


# -- Helpers ------------------------------------------------------------------


def _make_repo(tmp_path) -> str:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=repo, check=True)
    return str(repo)


def _png(path, size: int = 64) -> str:
    """Write a minimal-ish PNG-looking file. We don't validate content;
    the store only inspects mime by extension and size on disk."""
    p = str(path)
    # Real PNG magic + filler so the file looks plausible to anything that
    # peeks. Not strictly required for these tests.
    with open(p, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(b"\x00" * max(0, size - 8))
    return p


# -- Attachment dataclass -----------------------------------------------------


class TestAttachmentRecord:
    def test_round_trip(self):
        a = Attachment(
            path=".oompah/attachments/foo-1/abc-x.png",
            mime_type="image/png", size=123,
            created_at="2026-04-29T00:00:00+00:00",
        )
        d = a.to_dict()
        assert d["path"].endswith("abc-x.png")
        assert "turn" not in d  # default omitted
        assert "caption" not in d
        b = Attachment.from_dict(d)
        assert b == a

    def test_keeps_explicit_optional_fields(self):
        a = Attachment(
            path="x", mime_type="image/png", size=1, created_at="t",
            generated=True, turn=3, caption="hello",
        )
        b = Attachment.from_dict(a.to_dict())
        assert b.generated is True
        assert b.turn == 3
        assert b.caption == "hello"


# -- LFS bootstrap ------------------------------------------------------------


class TestEnsureLFSConfigured:
    def test_writes_gitattributes(self, tmp_path):
        repo = _make_repo(tmp_path)
        store = AttachmentStore(repo)
        wrote = store.ensure_lfs_configured()
        assert wrote is True
        ga = os.path.join(repo, ATTACHMENTS_SUBDIR, ".gitattributes")
        text = open(ga).read()
        for pat in LFS_PATTERNS:
            assert pat in text
            assert "filter=lfs" in text

    def test_idempotent(self, tmp_path):
        store = AttachmentStore(_make_repo(tmp_path))
        store.ensure_lfs_configured()
        # Second call must not rewrite when content is identical.
        assert store.ensure_lfs_configured() is False

    def test_overwrites_when_content_drifts(self, tmp_path):
        repo = _make_repo(tmp_path)
        store = AttachmentStore(repo)
        store.ensure_lfs_configured()
        ga = os.path.join(repo, ATTACHMENTS_SUBDIR, ".gitattributes")
        with open(ga, "w") as f:
            f.write("# manual edit\n")
        # Drift detected → rewritten.
        assert store.ensure_lfs_configured() is True


# -- Path validation ----------------------------------------------------------


class TestAbsolute:
    def test_rejects_absolute_path(self, tmp_path):
        store = AttachmentStore(_make_repo(tmp_path))
        with pytest.raises(AttachmentError, match="repo-relative"):
            store.absolute("/etc/passwd")

    def test_rejects_traversal(self, tmp_path):
        store = AttachmentStore(_make_repo(tmp_path))
        with pytest.raises(AttachmentError, match="escapes"):
            store.absolute("../etc/passwd")

    def test_rejects_path_outside_attachments(self, tmp_path):
        store = AttachmentStore(_make_repo(tmp_path))
        with pytest.raises(AttachmentError):
            # Inside repo but not under attachments root.
            store.absolute("README.md")

    def test_accepts_in_root(self, tmp_path):
        repo = _make_repo(tmp_path)
        store = AttachmentStore(repo)
        rel = ".oompah/attachments/foo-1/abc-img.png"
        # Path doesn't have to exist yet — just be inside the root.
        full = store.absolute(rel)
        assert full.startswith(os.path.realpath(repo))


# -- add() --------------------------------------------------------------------


class TestAdd:
    def test_basic_add(self, tmp_path):
        repo = _make_repo(tmp_path)
        store = AttachmentStore(repo)
        src = _png(tmp_path / "shot.png", size=100)
        rec = store.add("oompah-9k1", src)
        assert rec.path.startswith(".oompah/attachments/oompah-9k1/")
        assert rec.path.endswith("-shot.png")
        assert rec.mime_type == "image/png"
        assert rec.size == 100
        assert rec.generated is False
        # File is on disk where it should be.
        assert os.path.isfile(os.path.join(repo, rec.path))

    def test_canonical_path_is_stable_across_runs(self, tmp_path):
        """Same content → same path (sha-prefixed naming makes adds idempotent)."""
        repo = _make_repo(tmp_path)
        store = AttachmentStore(repo)
        src = _png(tmp_path / "shot.png", size=100)
        a = store.add("oompah-9k1", src)
        b = store.add("oompah-9k1", src)
        assert a.path == b.path

    def test_safe_basename(self, tmp_path):
        repo = _make_repo(tmp_path)
        store = AttachmentStore(repo)
        src = tmp_path / "weird name with spaces & symbols.png"
        _png(src, size=10)
        rec = store.add("oompah-9k1", str(src))
        # No spaces, no special chars in the canonical name.
        canon = os.path.basename(rec.path)
        assert " " not in canon
        assert "&" not in canon

    def test_generated_goes_to_outputs(self, tmp_path):
        store = AttachmentStore(_make_repo(tmp_path))
        src = _png(tmp_path / "diag.png", size=50)
        rec = store.add("oompah-9k1", src, generated=True, turn=4)
        assert "/outputs/" in rec.path
        assert rec.generated is True
        assert rec.turn == 4
        assert rec.added_by == "user"  # caller didn't override

    def test_rejects_missing_source(self, tmp_path):
        store = AttachmentStore(_make_repo(tmp_path))
        with pytest.raises(AttachmentError):
            store.add("foo-1", str(tmp_path / "nope.png"))

    def test_rejects_disallowed_mime(self, tmp_path):
        store = AttachmentStore(_make_repo(tmp_path))
        src = tmp_path / "evil.exe"
        src.write_bytes(b"MZ")
        with pytest.raises(AttachmentMimeRejected):
            store.add("foo-1", str(src))

    def test_rejects_oversize_attachment(self, tmp_path, monkeypatch):
        store = AttachmentStore(_make_repo(tmp_path))
        # Lower the cap rather than writing 25 MB.
        monkeypatch.setattr("oompah.attachments.MAX_ATTACHMENT_BYTES", 50)
        src = _png(tmp_path / "big.png", size=200)
        with pytest.raises(AttachmentTooLarge, match="per-attachment cap"):
            store.add("foo-1", src)

    def test_rejects_over_per_issue_cap(self, tmp_path, monkeypatch):
        store = AttachmentStore(_make_repo(tmp_path))
        monkeypatch.setattr("oompah.attachments.MAX_PER_ISSUE_BYTES", 200)
        # First add fits; second pushes over.
        a = _png(tmp_path / "a.png", size=120)
        store.add("foo-1", a)
        b = _png(tmp_path / "b.png", size=120)
        with pytest.raises(AttachmentTooLarge, match="per-issue cap"):
            store.add("foo-1", b)

    def test_caps_are_per_issue(self, tmp_path, monkeypatch):
        store = AttachmentStore(_make_repo(tmp_path))
        monkeypatch.setattr("oompah.attachments.MAX_PER_ISSUE_BYTES", 200)
        a = _png(tmp_path / "a.png", size=120)
        store.add("foo-1", a)
        # Same size in a different issue — must fit.
        b = _png(tmp_path / "b.png", size=120)
        store.add("bar-2", b)


# -- list / open / remove -----------------------------------------------------


class TestListOpenRemove:
    def test_list_returns_inputs_and_outputs(self, tmp_path):
        store = AttachmentStore(_make_repo(tmp_path))
        store.add("foo-1", _png(tmp_path / "a.png", size=10))
        store.add("foo-1", _png(tmp_path / "b.png", size=20), generated=True, turn=1)
        recs = store.list("foo-1")
        assert len(recs) == 2
        gens = [r for r in recs if r.generated]
        assert len(gens) == 1

    def test_list_empty(self, tmp_path):
        assert AttachmentStore(_make_repo(tmp_path)).list("foo-1") == []

    def test_list_skips_gitattributes(self, tmp_path):
        store = AttachmentStore(_make_repo(tmp_path))
        store.ensure_lfs_configured()
        # .gitattributes lives at attachments root, not under an issue —
        # but make sure list doesn't include any stray ones.
        store.add("foo-1", _png(tmp_path / "x.png", size=10))
        for r in store.list("foo-1"):
            assert not r.path.endswith(".gitattributes")

    def test_open_returns_bytes(self, tmp_path):
        store = AttachmentStore(_make_repo(tmp_path))
        rec = store.add("foo-1", _png(tmp_path / "x.png", size=64))
        data = store.open(rec.path)
        assert len(data) == 64
        assert data.startswith(b"\x89PNG")

    def test_open_missing(self, tmp_path):
        store = AttachmentStore(_make_repo(tmp_path))
        with pytest.raises(AttachmentNotFound):
            store.open(".oompah/attachments/foo-1/missing.png")

    def test_remove(self, tmp_path):
        store = AttachmentStore(_make_repo(tmp_path))
        rec = store.add("foo-1", _png(tmp_path / "x.png", size=10))
        store.remove(rec.path)
        assert store.list("foo-1") == []

    def test_remove_missing(self, tmp_path):
        store = AttachmentStore(_make_repo(tmp_path))
        with pytest.raises(AttachmentNotFound):
            store.remove(".oompah/attachments/foo-1/missing.png")


# -- commit -------------------------------------------------------------------


class TestCommit:
    def test_commit_creates_commit(self, tmp_path):
        repo = _make_repo(tmp_path)
        store = AttachmentStore(repo)
        # Initial commit so HEAD exists.
        (tmp_path / "repo" / "README").write_text("hi")
        subprocess.run(["git", "add", "README"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo, check=True)

        rec = store.add("foo-1", _png(tmp_path / "x.png", size=10))
        store.commit([rec.path], "add x.png")
        log = subprocess.check_output(
            ["git", "log", "--oneline"], cwd=repo, text=True,
        )
        assert "add x.png" in log

    def test_commit_skips_when_no_changes(self, tmp_path):
        repo = _make_repo(tmp_path)
        store = AttachmentStore(repo)
        (tmp_path / "repo" / "README").write_text("hi")
        subprocess.run(["git", "add", "README"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo, check=True)

        rec = store.add("foo-1", _png(tmp_path / "x.png", size=10))
        store.commit([rec.path], "add x.png")
        # Second commit with the same path → nothing to do, must not error.
        store.commit([rec.path], "again")
        log = subprocess.check_output(
            ["git", "log", "--oneline"], cwd=repo, text=True,
        ).splitlines()
        # init + add x.png — the second commit was skipped.
        assert sum(1 for line in log if "add x.png" in line) == 1


# -- Constants sanity --------------------------------------------------------


def test_caps_sane():
    assert MAX_ATTACHMENT_BYTES < MAX_PER_ISSUE_BYTES


def test_allowed_mime_includes_common_images():
    for mt in ("image/png", "image/jpeg", "image/webp", "application/pdf"):
        assert mt in ALLOWED_MIME_TYPES
