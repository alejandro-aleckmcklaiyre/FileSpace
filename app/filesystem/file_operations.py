"""Confirmed file-only transfers using staged, content-verified copies.

Even same-drive moves copy and verify for a single conservative implementation.
No directory moves, link following, or silent destination replacement.
"""

import hashlib
import os
import shutil
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Callable
from uuid import uuid4

from app.filesystem.safety import SafetyPolicy, check_file_data
from app.filesystem.path_validator import validate_directory
from app.filesystem.streams import named_streams, stream_path

CHUNK_SIZE = 1024 * 1024


def fingerprint(path: Path) -> tuple[int, ...]:
    info = path.stat()
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


@dataclass(frozen=True)
class TransferItem:
    source: Path
    source_state: tuple[int, ...]
    target: Path
    target_state: tuple[int, ...] | None
    source_streams: tuple[tuple[str, int], ...] = ()
    target_streams: tuple[tuple[str, int], ...] = ()


@dataclass(frozen=True)
class TransferPlan:
    destination: Path
    directory_identity: tuple[int, int]
    items: tuple[TransferItem, ...]
    operation: str = "move"

    @property
    def total_size(self) -> int:
        return sum(item.source_state[2] + sum(size for _, size in item.source_streams) for item in self.items)


@dataclass
class TransferResult:
    source: str
    destination: str
    status: str
    message: str = ""


def build_plan(sources: list[str], destination: str, policy: SafetyPolicy, operation: str = "move") -> TransferPlan:
    if operation not in {"move", "copy"}:
        raise ValueError("Choose copy or move.")
    if not sources:
        raise ValueError("Select at least one file.")
    folder = policy.check(Path(destination))
    validate_directory(str(folder))
    info = folder.stat()
    items = []
    names = set()
    for value in sources:
        source = policy.check(Path(value))
        if not stat.S_ISREG(source.stat().st_mode):
            raise ValueError("Only files can be transferred. Folder transfers are not supported.")
        check_file_data(source)
        target = folder / source.name
        if source.parent == folder:
            raise ValueError(f"File is already in the destination: {source.name}")
        if source.name.casefold() in names:
            raise ValueError("Selected files contain duplicate destination names.")
        names.add(source.name.casefold())
        target_state = None
        target_streams = ()
        if target.exists() or target.is_symlink():
            policy.check(target)
            if not target.is_file() or os.path.samefile(source, target):
                raise ValueError(f"Unsafe destination conflict: {target}")
            check_file_data(target)
            target_state = fingerprint(target)
            target_streams = named_streams(target)
        items.append(TransferItem(source, fingerprint(source), target, target_state, named_streams(source), target_streams))
    return TransferPlan(folder, (info.st_dev, info.st_ino), tuple(items), operation)


def digest(path: Path) -> bytes:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(CHUNK_SIZE):
            result.update(chunk)
    return result.digest()


def publish_no_replace(source: Path, target: Path) -> None:
    """Windows rename rejects an existing target; POSIX needs a no-clobber link."""
    if os.name == "nt":
        os.rename(source, target)
    else:
        os.link(source, target)
        source.unlink()


def copy_streams(source: Path, stage: Path, streams: tuple[tuple[str, int], ...], progress) -> dict[str, bytes]:
    """Copy and flush named data, preserving download-zone information too."""
    hashes = {}
    for suffix, expected_size in streams:
        progress(f"Copying file metadata for {source.name}: {suffix}")
        copied_hash = hashlib.sha256()
        count = 0
        try:
            with stream_path(source, suffix).open("rb") as incoming, stream_path(stage, suffix).open("xb") as output:
                while chunk := incoming.read(CHUNK_SIZE):
                    output.write(chunk)
                    copied_hash.update(chunk)
                    count += len(chunk)
                output.flush()
                os.fsync(output.fileno())
        except OSError as error:
            raise OSError(
                f"Cannot preserve file metadata stream {suffix}. The destination may not support it; original kept. {error}"
            ) from error
        if count != expected_size:
            raise ValueError("File metadata changed during copying; original preserved.")
        hashes[suffix] = copied_hash.digest()
    return hashes


def verify_streams(source: Path, copy: Path, streams: tuple[tuple[str, int], ...], hashes: dict[str, bytes]) -> None:
    if named_streams(source) != streams or named_streams(copy) != streams:
        raise ValueError("File metadata streams changed or were not preserved; original kept.")
    for suffix, _ in streams:
        if digest(stream_path(source, suffix)) != hashes[suffix] or digest(stream_path(copy, suffix)) != hashes[suffix]:
            raise ValueError("File metadata verification failed; original kept.")


def _check_destination(plan: TransferPlan, policy: SafetyPolicy) -> None:
    folder = policy.check(plan.destination)
    info = folder.stat()
    if (info.st_dev, info.st_ino) != plan.directory_identity or not folder.is_dir():
        raise ValueError("Destination changed since confirmation.")


def transfer_file(plan: TransferPlan, item: TransferItem, action: str, policy: SafetyPolicy,
              progress: Callable[[str], None] = lambda message: None) -> TransferResult:
    """Finish one file without interruption; cancellation happens between files."""
    target = item.target
    stage: Path | None = None
    backup: Path | None = None
    published = False
    failed_result: TransferResult | None = None
    try:
        if plan.operation not in {"move", "copy"}:
            raise ValueError("Unknown transfer operation.")
        if action not in {plan.operation, "skip", "rename", "replace"}:
            raise ValueError("Unknown conflict decision.")
        if action == "skip":
            return TransferResult(str(item.source), str(target), "skipped", "Skipped by user.")
        _check_destination(plan, policy)
        policy.check(item.source)
        check_file_data(item.source)
        if fingerprint(item.source) != item.source_state:
            raise ValueError("Source changed since confirmation.")
        if named_streams(item.source) != item.source_streams:
            raise ValueError("File metadata streams changed since confirmation.")
        if action == "replace" and item.target_state is None:
            raise ValueError("Replacement was not part of the confirmed conflict.")
        if item.target_state is not None and action in {"move", "copy"}:
            raise FileExistsError("Conflict requires an explicit decision.")
        if action == "rename":
            number = 1
            while target.exists() or target.is_symlink():
                target = item.target.with_name(f"{item.target.stem} ({number}){item.target.suffix}")
                number += 1
        elif item.target_state is None:
            if target.exists() or target.is_symlink():
                raise FileExistsError("A new destination conflict appeared; confirm again.")
        elif not target.exists() or fingerprint(policy.check(target)) != item.target_state or named_streams(target) != item.target_streams:
            raise ValueError("Conflicting file changed since confirmation.")

        progress(f"Copying {item.source.name} ({item.source_state[2]:,} bytes)")
        descriptor, name = tempfile.mkstemp(prefix=".filespace-", suffix=".partial", dir=plan.destination)
        stage = Path(name)
        copied_hash = hashlib.sha256()
        with os.fdopen(descriptor, "wb") as output, item.source.open("rb") as incoming:
            if fingerprint(item.source) != item.source_state:
                raise ValueError("Source changed before copying.")
            copied = 0
            while chunk := incoming.read(CHUNK_SIZE):
                output.write(chunk)
                copied_hash.update(chunk)
                copied += len(chunk)
                if copied % (8 * CHUNK_SIZE) == 0:
                    progress(f"Copying {item.source.name}: {copied:,}/{item.source_state[2]:,} bytes")
            output.flush()
            os.fsync(output.fileno())
        stream_hashes = copy_streams(item.source, stage, item.source_streams, progress)
        progress(f"Verifying {item.source.name}")
        if fingerprint(item.source) != item.source_state or digest(stage) != copied_hash.digest() or digest(item.source) != copied_hash.digest():
            raise ValueError("Copy verification failed; original preserved.")
        verify_streams(item.source, stage, item.source_streams, stream_hashes)
        shutil.copystat(item.source, stage, follow_symlinks=False)
        _check_destination(plan, policy)
        if action == "replace":
            if fingerprint(policy.check(target)) != item.target_state or named_streams(target) != item.target_streams:
                raise ValueError("Conflicting file changed during copying.")
            check_file_data(target)
            backup = target.with_name(f".filespace-{uuid4().hex}.backup")
            publish_no_replace(target, backup)
        # A newly appearing file always causes failure, including rename races.
        publish_no_replace(stage, target)
        stage = None
        published = True
        published_state = fingerprint(target)
        policy.check(item.source)
        check_file_data(item.source)
        _check_destination(plan, policy)
        if fingerprint(item.source) != item.source_state or digest(target) != copied_hash.digest() or digest(item.source) != copied_hash.digest():
            raise ValueError("Final verification failed; original preserved.")
        verify_streams(item.source, target, item.source_streams, stream_hashes)
        if fingerprint(item.source) != item.source_state:
            raise ValueError("Source changed during final verification; original preserved.")
        if fingerprint(policy.check(target)) != published_state:
            raise ValueError("Destination changed during final verification; original preserved.")
        if plan.operation == "move":
            item.source.unlink()
            if item.source.exists():
                raise OSError("Source removal could not be verified.")
        if backup is not None:
            backup.unlink()
            backup = None
        return TransferResult(
            str(item.source), str(target), "moved" if plan.operation == "move" else "copied",
            "Copied, SHA-256 verified, then original removed." if plan.operation == "move"
            else "Copied and SHA-256 verified; original retained.",
        )
    except Exception as error:
        message = str(error)
        if published:
            message += f" Transfer may be incomplete; inspect the source and destination: {target}."
        if backup is not None and backup.exists():
            if not target.exists():
                try:
                    publish_no_replace(backup, target)
                    backup = None
                except OSError:
                    pass
            if backup is not None:
                message += f" Previous destination preserved at {backup}."
        failed_result = TransferResult(str(item.source), str(target), "needs_review" if published else "failed", message)
        return failed_result
    finally:
        if stage is not None:
            try:
                stage.unlink(missing_ok=True)
            except OSError as cleanup_error:
                if failed_result is not None:
                    failed_result.message += f" Staging file could not be removed: {stage} ({cleanup_error})."


def execute_plan(plan: TransferPlan, decisions: list[str], policy: SafetyPolicy, cancel: Event,
                 record: Callable[[int, TransferResult], None], progress: Callable[[str], None]) -> list[TransferResult]:
    if len(decisions) != len(plan.items):
        raise ValueError("Every selected file needs a decision.")
    results = []
    for index, (item, action) in enumerate(zip(plan.items, decisions)):
        if cancel.is_set():
            result = TransferResult(str(item.source), str(item.target), "cancelled", "Cancelled before starting this file.")
        else:
            progress(f"File {index + 1}/{len(plan.items)}: {item.source.name}")
            result = transfer_file(plan, item, action, policy, progress)
        record(index, result)  # A journal failure stops subsequent transfers.
        results.append(result)
    return results
