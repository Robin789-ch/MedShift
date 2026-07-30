import json
import os
import tempfile
from pathlib import Path
from threading import Lock
from typing import Protocol

from pydantic import ValidationError

from medshift_contracts import Scenario, Workspace


class RevisionConflictError(Exception):
    pass


class WorkspaceInvalidError(Exception):
    pass


class WorkspaceCorruptError(Exception):
    pass


class WorkspaceVersionUnsupportedError(Exception):
    pass


class WorkspaceStore(Protocol):
    def load(self) -> Workspace | None: ...

    def save_scenario(
        self,
        base_revision: int | None,
        scenario: Scenario,
    ) -> Workspace: ...


class InMemoryWorkspace:
    def __init__(self, initial: Workspace | None = None) -> None:
        self._current = None if initial is None else initial.model_copy(deep=True)
        self._lock = Lock()

    def load(self) -> Workspace | None:
        with self._lock:
            if self._current is None:
                return None
            return self._current.model_copy(deep=True)

    def save_scenario(
        self,
        base_revision: int | None,
        scenario: Scenario,
    ) -> Workspace:
        with self._lock:
            workspace = _next_workspace(self._current, base_revision, scenario)
            self._current = workspace
            return workspace.model_copy(deep=True)


class FileWorkspace:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = Lock()

    def load(self) -> Workspace | None:
        with self._lock:
            return self._load_unlocked()

    def save_scenario(
        self,
        base_revision: int | None,
        scenario: Scenario,
    ) -> Workspace:
        with self._lock:
            workspace = _next_workspace(
                self._load_unlocked(),
                base_revision,
                scenario,
            )
            self._write_unlocked(workspace)
            return workspace

    def _load_unlocked(self) -> Workspace | None:
        if not self._path.exists():
            return None
        try:
            raw: object = json.loads(self._path.read_bytes())
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise WorkspaceCorruptError from error

        if (
            isinstance(raw, dict)
            and "schema_version" in raw
            and raw["schema_version"] != 1
        ):
            raise WorkspaceVersionUnsupportedError

        try:
            return Workspace.model_validate(raw)
        except ValidationError as error:
            raise WorkspaceCorruptError from error

    def _write_unlocked(self, workspace: Workspace) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=self._path.parent,
                prefix=f".{self._path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary:
                temporary_path = Path(temporary.name)
                temporary.write(
                    f"{workspace.model_dump_json(indent=2)}\n".encode(),
                )
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_path, self._path)
            directory_fd = os.open(
                self._path.parent,
                os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
            )
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)


def _next_workspace(
    current: Workspace | None,
    base_revision: int | None,
    scenario: Scenario,
) -> Workspace:
    current_revision = None if current is None else current.revision
    if base_revision != current_revision:
        raise RevisionConflictError

    try:
        return Workspace(
            schema_version=1,
            revision=1 if current is None else current.revision + 1,
            scenario=scenario,
            policies=[] if current is None else current.policies,
            objectives=[] if current is None else current.objectives,
        )
    except ValidationError as error:
        raise WorkspaceInvalidError from error
