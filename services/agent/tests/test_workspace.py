import json
import os
import stat
from pathlib import Path
from threading import Event, Thread
from uuid import UUID

import pytest

from medshift_agent.workspace import FileWorkspace
from medshift_agent.workspace import InMemoryWorkspace
from medshift_agent.workspace import RevisionConflictError
from medshift_agent.workspace import WorkspaceInvalidError
from medshift_agent.workspace import WorkspaceCorruptError
from medshift_agent.workspace import WorkspaceVersionUnsupportedError
from medshift_contracts import (
    ConsecutiveShiftLimit,
    Employee,
    Scenario,
    ShiftType,
    Workspace,
)


def minimum_scenario(
    display_name: str = "Avery",
    planning_weeks: int = 1,
) -> Scenario:
    return Scenario(
        planning_weeks=planning_weeks,
        employees=[
            Employee(
                employee_id=UUID("11111111-1111-1111-1111-111111111111"),
                display_name=display_name,
                overtime_hours=0,
                weekly_hours_ceiling=40,
            )
        ],
        departments=[],
        planning_entries=[],
    )


def test_first_save_initializes_workspace_at_revision_one() -> None:
    workspace = InMemoryWorkspace()

    assert workspace.load() is None

    saved = workspace.save_scenario(
        base_revision=None,
        scenario=minimum_scenario(),
    )

    assert saved.schema_version == 1
    assert saved.revision == 1
    assert saved.scenario == minimum_scenario()
    assert saved.policies == []
    assert saved.objectives == []
    assert workspace.load() == saved


def test_save_requires_the_current_revision_and_increments_once() -> None:
    workspace = InMemoryWorkspace()
    first = workspace.save_scenario(None, minimum_scenario())

    second = workspace.save_scenario(
        first.revision,
        minimum_scenario("Blair"),
    )

    assert second.revision == 2
    assert second.scenario.employees[0].display_name == "Blair"

    with pytest.raises(RevisionConflictError):
        workspace.save_scenario(
            first.revision,
            minimum_scenario("Casey"),
        )

    assert workspace.load() == second


def test_save_validates_the_complete_prospective_workspace() -> None:
    initial = Workspace(
        schema_version=1,
        revision=4,
        scenario=minimum_scenario(planning_weeks=2),
        policies=[
            ConsecutiveShiftLimit(
                id=UUID("22222222-2222-2222-2222-222222222222"),
                kind="consecutive_shift_limit",
                shift_type=ShiftType.NIGHT,
                minimum_run_length=None,
                maximum_run_length=14,
            )
        ],
        objectives=[],
    )
    workspace = InMemoryWorkspace(initial)

    with pytest.raises(WorkspaceInvalidError):
        workspace.save_scenario(
            base_revision=4,
            scenario=minimum_scenario(planning_weeks=1),
        )

    assert workspace.load() == initial


def test_file_workspace_stays_absent_until_save_and_reloads_after_restart(
    tmp_path: Path,
) -> None:
    workspace_path = tmp_path / "data" / "workspace.json"
    workspace = FileWorkspace(workspace_path)

    assert workspace.load() is None
    assert not workspace_path.exists()

    saved = workspace.save_scenario(None, minimum_scenario())

    assert saved.revision == 1
    assert workspace_path.exists()
    assert FileWorkspace(workspace_path).load() == saved


@pytest.mark.parametrize(
    ("contents", "expected_error"),
    [
        (b"{not-json", WorkspaceCorruptError),
        (
            json.dumps(
                {
                    "schema_version": 2,
                    "revision": 1,
                    "scenario": minimum_scenario().model_dump(mode="json"),
                    "policies": [],
                    "objectives": [],
                }
            ).encode(),
            WorkspaceVersionUnsupportedError,
        ),
    ],
)
def test_invalid_existing_file_is_preserved_after_failed_load_and_save(
    tmp_path: Path,
    contents: bytes,
    expected_error: type[Exception],
) -> None:
    workspace_path = tmp_path / "workspace.json"
    workspace_path.write_bytes(contents)
    workspace = FileWorkspace(workspace_path)

    with pytest.raises(expected_error):
        workspace.load()
    assert workspace_path.read_bytes() == contents

    with pytest.raises(expected_error):
        workspace.save_scenario(None, minimum_scenario())
    assert workspace_path.read_bytes() == contents


def test_file_save_replaces_from_same_directory_and_fsyncs_file_and_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_path = tmp_path / "workspace.json"
    replacements: list[tuple[Path, Path]] = []
    fsync_targets: list[str] = []
    real_replace = os.replace
    real_fsync = os.fsync

    def observed_replace(
        source: str | os.PathLike[str],
        destination: str | os.PathLike[str],
    ) -> None:
        source_path = Path(source)
        destination_path = Path(destination)
        replacements.append((source_path, destination_path))
        assert source_path.parent == destination_path.parent
        Workspace.model_validate_json(source_path.read_bytes())
        real_replace(source, destination)

    def observed_fsync(file_descriptor: int) -> None:
        mode = os.fstat(file_descriptor).st_mode
        fsync_targets.append("directory" if stat.S_ISDIR(mode) else "file")
        real_fsync(file_descriptor)

    monkeypatch.setattr("medshift_agent.workspace.os.replace", observed_replace)
    monkeypatch.setattr("medshift_agent.workspace.os.fsync", observed_fsync)

    FileWorkspace(workspace_path).save_scenario(None, minimum_scenario())

    assert replacements == [
        (replacements[0][0], workspace_path),
    ]
    assert fsync_targets == ["file", "directory"]


def test_atomic_replacement_never_exposes_a_torn_workspace(tmp_path: Path) -> None:
    workspace_path = tmp_path / "workspace.json"
    workspace = FileWorkspace(workspace_path)
    current = workspace.save_scenario(None, minimum_scenario("Employee 0"))
    finished = Event()
    failures: list[Exception] = []

    def write_revisions() -> None:
        nonlocal current
        try:
            for revision in range(1, 101):
                current = workspace.save_scenario(
                    current.revision,
                    minimum_scenario(f"Employee {revision}"),
                )
        except Exception as error:
            failures.append(error)
        finally:
            finished.set()

    writer = Thread(target=write_revisions)
    writer.start()
    reads = 0
    while not finished.is_set():
        Workspace.model_validate_json(workspace_path.read_bytes())
        reads += 1
    writer.join()

    assert failures == []
    assert reads > 0
