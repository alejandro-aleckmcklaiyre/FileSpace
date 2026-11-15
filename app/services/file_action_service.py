"""Validated, journaled rename and Recycle Bin actions for regular files."""

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QFile

from app.filesystem.file_operations import TransferResult, fingerprint, publish_no_replace
from app.filesystem.safety import check_file_data
from app.filesystem.streams import named_streams


@dataclass(frozen=True)
class ActionItem:
    source: Path
    state: tuple[int, ...]
    streams: tuple[tuple[str, int], ...]
    destination: str


@dataclass(frozen=True)
class ActionPlan:
    operation: str
    items: tuple[ActionItem, ...]

    @property
    def total_size(self):
        return sum(item.state[2] + sum(size for name, size in item.streams) for item in self.items)


class FileActionService:
    def __init__(self, repository, policy):
        self.repository, self.policy = repository, policy

    def _snapshot(self, value: str, destination: str) -> ActionItem:
        source = self.policy.check(Path(value))
        check_file_data(source)
        return ActionItem(source, fingerprint(source), named_streams(source), destination)

    def plan_rename(self, value: str, stem: str) -> ActionPlan:
        source = Path(value)
        if not stem or stem != stem.strip() or stem.endswith((".", " ")) or any(ord(char) < 32 or char in '<>:"/\\|?*' for char in stem):
            raise ValueError("Enter a valid file name without path separators or trailing spaces/dots.")
        if re.match(r"^(CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³])(?:\.|$)", stem, re.IGNORECASE):
            raise ValueError("That name is reserved by Windows.")
        target = source.with_name(stem + source.suffix)
        item = self._snapshot(value, str(target))
        if item.source == target:
            raise ValueError("Choose a different name; case-only renames are not supported yet.")
        if target.exists() or target.is_symlink():
            raise FileExistsError("The new name already exists. No file will be replaced.")
        return ActionPlan("rename", (item,))

    def plan_recycle(self, sources: list[str]) -> ActionPlan:
        if not sources:
            raise ValueError("Select files to send to the Recycle Bin.")
        if not QFile.supportsMoveToTrash():
            raise OSError("The Recycle Bin is unavailable. Permanent deletion is not offered.")
        return ActionPlan("recycle", tuple(self._snapshot(value, "Recycle Bin") for value in dict.fromkeys(sources)))

    def properties(self, paths: list[str]) -> str:
        parts = []
        for value in paths:
            path = Path(value)
            info = path.stat()
            parts.append(
                f"Name: {path.name}\nType: {'Folder' if path.is_dir() else path.suffix or 'File'}\n"
                f"Size: {'Not calculated for folders' if path.is_dir() else format(info.st_size, ',') + ' bytes'}\n"
                f"Modified: {datetime.fromtimestamp(info.st_mtime):%Y-%m-%d %H:%M:%S}\nLocation: {path}"
            )
        return "\n\n".join(parts)

    def execute(self, plan: ActionPlan, cancel, progress):
        if plan.operation not in {"rename", "recycle"} or not plan.items:
            raise ValueError("Expected a nonempty rename or Recycle Bin plan.")
        operation, ids = self.repository.start_operation(
            plan.items[0].destination, [str(item.source) for item in plan.items], plan.operation,
            [item.destination for item in plan.items],
        )
        results = []
        try:
            for index, item in enumerate(plan.items):
                destination = item.destination
                status, message = "cancelled", "Cancelled before this file started."
                if not cancel.is_set():
                    changed = False
                    progress(f"{plan.operation.title()} {index + 1}/{len(plan.items)}: {item.source.name}")
                    try:
                        self.policy.check(item.source)
                        check_file_data(item.source)
                        if fingerprint(item.source) != item.state or named_streams(item.source) != item.streams:
                            raise ValueError("File changed after confirmation; no action performed.")
                        if plan.operation == "rename":
                            target = Path(destination)
                            self.policy.check(target.parent)
                            publish_no_replace(item.source, target)
                            changed = True
                            if item.source.exists() or fingerprint(target)[:3] != item.state[:3] or named_streams(target) != item.streams:
                                raise OSError("Rename requires review; inspect both names.")
                            status, message = "renamed", "Renamed without replacing an existing file; extension preserved."
                        elif plan.operation == "recycle":
                            file = QFile(str(item.source))
                            if not file.moveToTrash():
                                raise OSError(file.errorString() or "Could not move this file to the Recycle Bin.")
                            changed = True
                            destination = file.fileName() or "Recycle Bin"
                            if item.source.exists():
                                raise OSError("Recycle operation requires review; the original path still exists.")
                            status, message = "recycled", "Sent to the Recycle Bin. Restore using Windows if needed."
                        else:
                            raise ValueError("Unsupported file action.")
                    except Exception as error:
                        status, message = "needs_review" if changed else "failed", str(error)
                        logging.getLogger(__name__).warning(
                            "%s failed: source=%s destination=%s errno=%s winerror=%s: %s",
                            plan.operation, item.source, destination, getattr(error, "errno", None),
                            getattr(error, "winerror", None), error,
                        )
                result = TransferResult(str(item.source), destination, status, message)
                results.append(result)
                try:
                    self.repository.record_item(ids[index], destination, status, message)
                except Exception as error:
                    raise OSError(f"Action on {item.source}: {status}. History update failed; inspect both locations before retrying. {error}") from error
            status = "completed" if all(item.status in {"renamed", "recycled"} for item in results) else "partial"
            self.repository.finish_operation(operation, status)
            return results
        except Exception as error:
            try:
                self.repository.finish_operation(operation, "needs_review")
            except Exception:
                logging.getLogger(__name__).exception("Could not mark failed file action in history")
            raise OSError(f"File action may have completed. Inspect per-file history before retrying. {error}") from error
