"""Coordinate persistent shortcuts and confirmed, journaled moves."""

from pathlib import Path
from threading import Event

from app.database.repository import Repository
from app.filesystem.file_operations import MovePlan, build_plan, execute_plan
from app.filesystem.path_validator import validate_directory
from app.filesystem.safety import SafetyPolicy


class QuickSortService:
    def __init__(self, repository: Repository, policy: SafetyPolicy) -> None:
        self.repository, self.policy = repository, policy

    def save(self, keyword: str, name: str, destination: str, shortcut_id: int | None = None) -> None:
        folder = self.policy.check(Path(destination))
        validate_directory(str(folder))
        self.repository.save_shortcut(keyword, name, str(folder), shortcut_id)

    def plan(self, sources: list[str], destination: str) -> MovePlan:
        return build_plan(sources, destination, self.policy)

    def move(self, plan: MovePlan, decisions: list[str], cancel: Event, progress) -> list:
        operation, ids = self.repository.start_operation(str(plan.destination), [str(item.source) for item in plan.items])

        def record(index, result):
            try:
                self.repository.record_item(ids[index], result.destination, result.status, result.message)
            except Exception as error:
                raise RuntimeError(
                    f"History could not be updated after {result.source}: {result.status}; "
                    f"destination {result.destination}. Inspect both paths before retrying. {error}"
                ) from error

        try:
            results = execute_plan(plan, decisions, self.policy, cancel, record, progress)
            statuses = {item.status for item in results}
            status = "completed" if statuses <= {"moved", "skipped"} else "cancelled" if statuses == {"cancelled"} else "partial"
            try:
                self.repository.finish_operation(operation, status)
            except Exception as error:
                raise RuntimeError(
                    "Transfers have finished, but the batch history status could not be saved. "
                    "Inspect the per-file history and both locations before retrying. " + str(error)
                ) from error
            return results
        except Exception as error:
            try:
                self.repository.finish_operation(operation, "needs_review")
            except Exception as journal_error:
                raise RuntimeError(f"{error}\nHistory status is also unavailable: {journal_error}") from error
            raise
