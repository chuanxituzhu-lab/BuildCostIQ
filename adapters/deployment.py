"""Deployment and storage boundary for multi-terminal BuildCostIQ installs.

The Core and P01-P09 capabilities remain unchanged.  This adapter only
answers where a node runs, where its project data lives, and how one central
service serializes project writes.  Terminals should talk to one central
service; they must not open the project JSON files directly.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import os
from pathlib import Path
import re
from threading import RLock
from typing import Iterator, Mapping


DEPLOYMENT_VERSION = "1.0"
_SAFE_ID = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_id(value: object, fallback: str = "project") -> str:
    text = _SAFE_ID.sub("-", str(value or "").strip()).strip("-.")
    return text or fallback


def _path(value: object) -> Path:
    return Path(str(value)).expanduser()


@dataclass(frozen=True)
class StorageRoots:
    """Logical storage roots owned by one BuildCostIQ service node."""

    data_root: Path
    projects: Path
    sources: Path
    archive: Path
    basis: Path
    auth: Path
    backups: Path
    locks: Path

    @classmethod
    def from_environment(cls, environ: Mapping[str, str] | None = None) -> "StorageRoots":
        env = os.environ if environ is None else environ
        data_root = _path(env.get("BUILDCOSTIQ_DATA_ROOT", "runtime"))

        def child(name: str, default: Path) -> Path:
            return _path(env.get(name, str(default)))

        return cls(
            data_root=data_root,
            projects=child("BUILDCOSTIQ_WORKSPACE", data_root / "projects"),
            sources=child("BUILDCOSTIQ_SOURCE_STORE", data_root / "sources"),
            archive=child("BUILDCOSTIQ_ARCHIVE_STORE", data_root / "archive"),
            basis=child("BUILDCOSTIQ_BASIS_STORE", data_root / "basis"),
            auth=child("BUILDCOSTIQ_AUTH", data_root / "auth"),
            backups=child("BUILDCOSTIQ_BACKUP_ROOT", data_root / "backups"),
            locks=child("BUILDCOSTIQ_LOCK_ROOT", data_root / "locks"),
        )

    def ensure_layout(self) -> None:
        for root in (self.data_root, self.projects, self.sources, self.archive, self.basis, self.auth, self.backups, self.locks):
            root.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class DeploymentConfig:
    """Runtime deployment mode and storage roots.

    ``central`` is the multi-terminal authoritative service mode.  The
    ``single-node`` default keeps the existing local-first workflow.  ``edge``
    is descriptive only: an edge node may cache drafts later, but it is never
    the authoritative project database.
    """

    mode: str
    node_id: str
    host: str
    port: int
    roots: StorageRoots

    @classmethod
    def from_environment(cls, environ: Mapping[str, str] | None = None) -> "DeploymentConfig":
        env = os.environ if environ is None else environ
        mode = str(env.get("BUILDCOSTIQ_DEPLOYMENT_MODE", "single-node")).strip().lower() or "single-node"
        if mode not in {"single-node", "central", "edge"}:
            raise ValueError("BUILDCOSTIQ_DEPLOYMENT_MODE must be single-node, central, or edge")
        try:
            port = int(env.get("BUILDCOSTIQ_PORT", "8787"))
        except ValueError as exc:
            raise ValueError("BUILDCOSTIQ_PORT must be an integer") from exc
        if not 1 <= port <= 65535:
            raise ValueError("BUILDCOSTIQ_PORT must be between 1 and 65535")
        return cls(
            mode=mode,
            node_id=str(env.get("BUILDCOSTIQ_NODE_ID", "local-node")).strip() or "local-node",
            host=str(env.get("BUILDCOSTIQ_HOST", "127.0.0.1")).strip() or "127.0.0.1",
            port=port,
            roots=StorageRoots.from_environment(env),
        )

    @property
    def authoritative(self) -> bool:
        return self.mode in {"single-node", "central"}

    def ensure_layout(self) -> None:
        self.roots.ensure_layout()

    def public(self, *, include_paths: bool = False) -> dict[str, object]:
        storage: dict[str, object] = {
            "authority": "central_service" if self.mode == "central" else "single_node",
            "project_state": "projects",
            "immutable_sources": "sources",
            "categorized_archive": "archive",
            "external_basis": "basis",
            "identity_and_roles": "auth",
            "backup": "backups",
        }
        if include_paths:
            storage["paths"] = {
                "data_root": str(self.roots.data_root.resolve()),
                "projects": str(self.roots.projects.resolve()),
                "sources": str(self.roots.sources.resolve()),
                "archive": str(self.roots.archive.resolve()),
                "basis": str(self.roots.basis.resolve()),
                "auth": str(self.roots.auth.resolve()),
                "backups": str(self.roots.backups.resolve()),
            }
        return {
            "version": DEPLOYMENT_VERSION,
            "mode": self.mode,
            "node_id": self.node_id,
            "authoritative": self.authoritative,
            "host": self.host,
            "port": self.port,
            "storage": storage,
            "consistency": {
                "project_write_lock": True,
                "project_revision": True,
                "direct_shared_folder_writes": False,
                "offline_edge_is_authoritative": False,
            },
        }


class DeploymentStorageAdapter:
    """Central storage coordinator with thread and process write locks."""

    def __init__(self, config: DeploymentConfig) -> None:
        self.config = config
        self.config.ensure_layout()
        self._registry_lock = RLock()
        self._project_locks: dict[str, RLock] = {}

    def _thread_lock(self, project_id: str) -> RLock:
        key = _safe_id(project_id)
        with self._registry_lock:
            return self._project_locks.setdefault(key, RLock())

    @staticmethod
    def _lock_file(handle: object) -> None:
        if os.name == "nt":
            import msvcrt

            file_handle = handle  # type: ignore[assignment]
            file_handle.seek(0, os.SEEK_END)
            if file_handle.tell() == 0:
                file_handle.write(b"0")
                file_handle.flush()
            file_handle.seek(0)
            msvcrt.locking(file_handle.fileno(), msvcrt.LK_LOCK, 1)
            return
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)  # type: ignore[attr-defined]

    @staticmethod
    def _unlock_file(handle: object) -> None:
        if os.name == "nt":
            import msvcrt

            file_handle = handle  # type: ignore[assignment]
            file_handle.seek(0)
            msvcrt.locking(file_handle.fileno(), msvcrt.LK_UNLCK, 1)
            return
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)  # type: ignore[attr-defined]

    @contextmanager
    def project_lock(self, project_id: str) -> Iterator[None]:
        """Serialize one project's read-modify-write transaction.

        The lock is process-safe on the central node and remains a no-op for
        other projects, so unrelated projects can continue in parallel.
        """

        thread_lock = self._thread_lock(project_id)
        lock_path = self.config.roots.locks / f"{_safe_id(project_id)}.lock"
        with thread_lock:
            with lock_path.open("a+b") as handle:
                self._lock_file(handle)
                try:
                    yield
                finally:
                    self._unlock_file(handle)

    def status(self) -> dict[str, object]:
        return self.config.public()
