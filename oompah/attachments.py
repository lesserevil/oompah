"""Attachment store backed by the project repo + git LFS.

Attachments live under ``.oompah/attachments/<issue-identifier>/`` inside a
project's repo. User uploads sit at the top level; agent-generated outputs
go in an ``outputs/`` subdirectory. File names are
``<sha256-prefix>-<original-name>`` so duplicates collapse and the original
name stays human-readable.

This module is the storage layer only — wiring into beads metadata, the
prompt renderer, and the dashboard happens in later phases. See
``plans/multimodal-attachments.md``.
"""

from __future__ import annotations

import hashlib
import logging
import mimetypes
import os
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable

logger = logging.getLogger(__name__)


# -- Limits and policy --------------------------------------------------------

# Per ``plans/multimodal-attachments.md§Validation and limits``.
MAX_ATTACHMENT_BYTES = 25 * 1024 * 1024  # 25 MB per file
MAX_PER_ISSUE_BYTES = 200 * 1024 * 1024  # 200 MB total per issue

# Conservative, explicit allow-list. Anything not on this list is rejected
# at ``add`` time. Extensions on disk are matched case-insensitively.
ALLOWED_MIME_TYPES: frozenset[str] = frozenset({
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/gif",
    "image/svg+xml",
    "application/pdf",
    "audio/wav",
    "audio/x-wav",
    "audio/mpeg",
    "audio/mp4",
    "audio/m4a",
    "video/mp4",
})

# LFS tracks these extensions inside the attachments directory. Kept narrow
# on purpose — only the formats listed above.
LFS_PATTERNS: tuple[str, ...] = (
    "*.png", "*.jpg", "*.jpeg", "*.gif", "*.webp", "*.svg",
    "*.pdf", "*.mp3", "*.wav", "*.m4a", "*.mp4",
)

ATTACHMENTS_SUBDIR = ".oompah/attachments"


# -- Records ------------------------------------------------------------------


@dataclass
class Attachment:
    """One attachment record.

    ``path`` is repo-relative (e.g.
    ``.oompah/attachments/oompah-9k1/abc-mock.png``). All bytes-on-disk
    operations resolve through the owning :class:`AttachmentStore` so the
    record itself stays portable.
    """

    path: str
    mime_type: str
    size: int
    created_at: str  # ISO-8601 UTC
    generated: bool = False
    turn: int | None = None
    added_by: str = "user"
    caption: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # Drop fields that match defaults to keep persisted JSON small.
        if d.get("turn") is None:
            d.pop("turn", None)
        if not d.get("caption"):
            d.pop("caption", None)
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Attachment:
        return cls(
            path=str(d["path"]),
            mime_type=str(d.get("mime_type", "application/octet-stream")),
            size=int(d.get("size", 0)),
            created_at=str(d.get("created_at", "")),
            generated=bool(d.get("generated", False)),
            turn=d.get("turn"),
            added_by=str(d.get("added_by", "user")),
            caption=d.get("caption"),
        )


# -- Helpers ------------------------------------------------------------------


_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_basename(original_name: str) -> str:
    """Strip directory components and unsafe characters from a name."""
    base = os.path.basename(original_name).strip()
    if not base:
        return "file"
    # Collapse runs of unsafe chars to a single underscore.
    cleaned = _SAFE_NAME_RE.sub("_", base)
    return cleaned or "file"


def _sha256_prefix(data: bytes, n: int = 12) -> str:
    return hashlib.sha256(data).hexdigest()[:n]


def _guess_mime(path: str) -> str:
    mt, _ = mimetypes.guess_type(path)
    return mt or "application/octet-stream"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# -- Errors -------------------------------------------------------------------


class AttachmentError(Exception):
    """Base error for attachment-store operations."""


class AttachmentTooLarge(AttachmentError):
    """File exceeds per-attachment or per-issue cap."""


class AttachmentMimeRejected(AttachmentError):
    """File's mime type is not on the allow-list."""


class AttachmentNotFound(AttachmentError):
    """The requested attachment does not exist in the store."""


# -- Store --------------------------------------------------------------------


class AttachmentStore:
    """Filesystem-backed attachment store rooted at a project repo.

    The store owns ``<project_root>/.oompah/attachments/`` and a
    ``.gitattributes`` file in that directory that declares LFS for the
    binary extensions we accept. All paths returned by the store are
    repo-relative (forward slashes) so they round-trip cleanly through
    JSON.
    """

    def __init__(self, project_root: str):
        self.project_root = os.path.abspath(project_root)
        self.attachments_root = os.path.join(self.project_root, ATTACHMENTS_SUBDIR)

    # -- path helpers -------------------------------------------------------

    def absolute(self, rel_path: str) -> str:
        """Resolve a repo-relative attachment path to an absolute path.

        Refuses any path that escapes ``attachments_root`` (traversal
        protection).
        """
        if os.path.isabs(rel_path):
            raise AttachmentError(f"attachment path must be repo-relative: {rel_path!r}")
        full = os.path.normpath(os.path.join(self.project_root, rel_path))
        # Use realpath so symlinks can't escape the root.
        real_full = os.path.realpath(full)
        real_root = os.path.realpath(self.attachments_root)
        if real_full != real_root and not real_full.startswith(real_root + os.sep):
            raise AttachmentError(f"path escapes attachments root: {rel_path!r}")
        return full

    def _issue_dir(self, issue_identifier: str, *, generated: bool = False) -> str:
        if not issue_identifier or "/" in issue_identifier or "\\" in issue_identifier:
            raise AttachmentError(f"invalid issue identifier: {issue_identifier!r}")
        d = os.path.join(self.attachments_root, issue_identifier)
        if generated:
            d = os.path.join(d, "outputs")
        return d

    def _rel(self, abs_path: str) -> str:
        rel = os.path.relpath(abs_path, self.project_root)
        return rel.replace(os.sep, "/")

    # -- LFS bootstrap ------------------------------------------------------

    def ensure_lfs_configured(self) -> bool:
        """Write the ``.gitattributes`` declaring LFS for our extensions.

        Returns ``True`` when the file was written or updated, ``False``
        when it already had the right content. Idempotent. Does not run
        ``git lfs install`` itself — that's the project-registration step's
        responsibility (see ``oompah/projects.py``).
        """
        os.makedirs(self.attachments_root, exist_ok=True)
        ga_path = os.path.join(self.attachments_root, ".gitattributes")
        wanted_lines = [
            f"{pat} filter=lfs diff=lfs merge=lfs -text"
            for pat in LFS_PATTERNS
        ]
        wanted = "\n".join(wanted_lines) + "\n"
        try:
            with open(ga_path, "r", encoding="utf-8") as f:
                current = f.read()
        except FileNotFoundError:
            current = None
        if current == wanted:
            return False
        with open(ga_path, "w", encoding="utf-8") as f:
            f.write(wanted)
        return True

    # -- core operations ----------------------------------------------------

    def add(
        self,
        issue_identifier: str,
        src_path: str,
        *,
        generated: bool = False,
        turn: int | None = None,
        added_by: str = "user",
        caption: str | None = None,
        mime_type: str | None = None,
    ) -> Attachment:
        """Copy ``src_path`` into the store and return its :class:`Attachment`.

        Validates per-attachment size, the global mime allow-list, and the
        per-issue total cap. Refuses paths that don't exist or aren't
        regular files.
        """
        if not os.path.isfile(src_path):
            raise AttachmentError(f"source is not a regular file: {src_path!r}")

        size = os.path.getsize(src_path)
        if size > MAX_ATTACHMENT_BYTES:
            raise AttachmentTooLarge(
                f"{src_path!r} is {size} bytes; per-attachment cap is {MAX_ATTACHMENT_BYTES}"
            )

        mt = mime_type or _guess_mime(src_path)
        if mt not in ALLOWED_MIME_TYPES:
            raise AttachmentMimeRejected(
                f"mime {mt!r} is not on the allow-list (file: {src_path!r})"
            )

        # Per-issue cap counts everything currently under the issue dir
        # (inputs + outputs).
        existing_total = self.size_for_issue(issue_identifier)
        if existing_total + size > MAX_PER_ISSUE_BYTES:
            raise AttachmentTooLarge(
                f"adding {size} bytes to {issue_identifier!r} would exceed "
                f"per-issue cap {MAX_PER_ISSUE_BYTES} (current {existing_total})"
            )

        self.ensure_lfs_configured()

        with open(src_path, "rb") as f:
            data = f.read()
        prefix = _sha256_prefix(data)
        safe = _safe_basename(src_path)
        fname = f"{prefix}-{safe}"

        dest_dir = self._issue_dir(issue_identifier, generated=generated)
        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, fname)

        # If the exact same content already exists, reuse it (idempotent).
        if not os.path.exists(dest):
            shutil.copyfile(src_path, dest)

        rel = self._rel(dest)
        return Attachment(
            path=rel,
            mime_type=mt,
            size=size,
            created_at=_now_iso(),
            generated=generated,
            turn=turn,
            added_by=added_by,
            caption=caption,
        )

    def list(self, issue_identifier: str) -> list[Attachment]:
        """List attachments stored for an issue (inputs + outputs).

        Records are reconstructed from disk; the canonical record (with
        accurate ``created_at`` / ``added_by`` / ``caption``) lives in the
        beads metadata in later phases. This list is intended for the
        dashboard's sidecar use.
        """
        out: list[Attachment] = []
        for generated in (False, True):
            d = self._issue_dir(issue_identifier, generated=generated)
            if not os.path.isdir(d):
                continue
            for entry in sorted(os.listdir(d)):
                full = os.path.join(d, entry)
                if not os.path.isfile(full):
                    continue
                if entry == ".gitattributes":
                    continue
                size = os.path.getsize(full)
                mt = _guess_mime(full)
                created = datetime.fromtimestamp(
                    os.path.getmtime(full), tz=timezone.utc
                ).isoformat(timespec="seconds")
                out.append(Attachment(
                    path=self._rel(full),
                    mime_type=mt,
                    size=size,
                    created_at=created,
                    generated=generated,
                    added_by="agent" if generated else "user",
                ))
        return out

    def open(self, rel_path: str) -> bytes:
        """Read the bytes of an attachment by its repo-relative path."""
        full = self.absolute(rel_path)
        if not os.path.isfile(full):
            raise AttachmentNotFound(rel_path)
        with open(full, "rb") as f:
            return f.read()

    def remove(self, rel_path: str) -> None:
        """Delete an attachment from disk. Caller is responsible for
        committing the removal."""
        full = self.absolute(rel_path)
        if not os.path.isfile(full):
            raise AttachmentNotFound(rel_path)
        os.remove(full)

    def size_for_issue(self, issue_identifier: str) -> int:
        """Total bytes currently stored under an issue (inputs + outputs)."""
        total = 0
        for generated in (False, True):
            d = self._issue_dir(issue_identifier, generated=generated)
            if not os.path.isdir(d):
                continue
            for entry in os.listdir(d):
                full = os.path.join(d, entry)
                if os.path.isfile(full) and entry != ".gitattributes":
                    total += os.path.getsize(full)
        return total

    # -- git plumbing -------------------------------------------------------

    def commit(self, paths: Iterable[str], message: str) -> None:
        """Stage ``paths`` (repo-relative) and create a commit.

        Skipped when there are no changes to commit. Errors propagate so
        callers can wrap them in a useful warning. Used by the dashboard's
        upload + delete endpoints in Phase 4.
        """
        paths = list(paths)
        if not paths:
            return
        for rel in paths:
            # Validate before staging.
            self.absolute(rel) if os.path.exists(os.path.join(self.project_root, rel)) else rel
        subprocess.run(
            ["git", "add", "--", *paths],
            cwd=self.project_root, check=True,
        )
        # If nothing actually changed, skip the commit rather than failing.
        diff = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=self.project_root,
        )
        if diff.returncode == 0:
            return
        subprocess.run(
            ["git", "commit", "-m", message],
            cwd=self.project_root, check=True,
        )
