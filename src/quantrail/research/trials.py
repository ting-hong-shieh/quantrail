"""Append-only trial registry and code fingerprints.

Every trial is written as REGISTERED before it runs and receives exactly one terminal
event (COMPLETED, FAILED or BLOCKED). Lines are only appended, so failed or
unfavourable trials cannot be dropped by rewriting the file.
"""

from __future__ import annotations

import gzip
import io
import json
import os
import subprocess
import tarfile
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

TERMINAL = {"COMPLETED", "FAILED", "BLOCKED"}
DEFAULT_SOURCE_PATHS = ("src", "studies", "scripts", "pyproject.toml", "uv.lock")


def canonical_sha256(value) -> str:
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
                             default=str).encode()).hexdigest()


def _source_files(root: Path, paths) -> list[Path]:
    files = []
    for name in paths:
        path = root / name
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            files += [p for p in path.rglob("*") if p.is_file()
                      and "__pycache__" not in p.parts and ".ipynb_checkpoints" not in p.parts]
    return sorted(files)


def code_version(root, paths=DEFAULT_SOURCE_PATHS) -> dict:
    """Git commit and dirty flag when available, plus a hash of the source files that
    also covers uncommitted edits."""
    root = Path(root)
    digest = sha256()
    for path in _source_files(root, paths):
        digest.update(str(path.relative_to(root)).encode() + b"\0" + path.read_bytes() + b"\0")
    commit = dirty = None
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, check=True,
                                capture_output=True, text=True).stdout.strip()
        dirty = bool(subprocess.run(["git", "status", "--porcelain"], cwd=root, check=True,
                                    capture_output=True, text=True).stdout.strip())
    except (OSError, subprocess.CalledProcessError):
        pass
    return {"commit": commit, "dirty": dirty, "source_sha256": digest.hexdigest()}


def write_source_snapshot(dest, root, paths=DEFAULT_SOURCE_PATHS) -> Path:
    """Deterministic tar.gz of the files code_version hashes; use when commit is absent or dirty."""
    root = Path(root)
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.PAX_FORMAT) as archive:
        for path in _source_files(root, paths):
            info = archive.gettarinfo(path, arcname=str(path.relative_to(root)))
            # Strip everything that depends on when or by whom the file was written.
            info.mtime, info.uid, info.gid, info.uname, info.gname = 0, 0, 0, "", ""
            info.pax_headers = {}
            with path.open("rb") as handle:
                archive.addfile(info, handle)
    # gzip records a timestamp in its header; pin it so equal sources give equal bytes.
    Path(dest).write_bytes(gzip.compress(buffer.getvalue(), mtime=0))
    return Path(dest)


class TrialRegistry:
    def __init__(self, path):
        self.path = Path(path)

    def _append(self, event: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True, default=str) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def trials(self) -> list[dict]:
        """Latest state per trial, in registration order."""
        state: dict[str, dict] = {}
        if not self.path.exists():
            return []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            event = json.loads(line)
            if event["event"] == "register":
                state[event["trial_id"]] = {k: v for k, v in event.items() if k != "event"}
            else:
                state[event["trial_id"]].update(status=event["status"], result_path=event["result_path"],
                                                finished_at=event["finished_at"],
                                                status_reason=event["status_reason"])
        return list(state.values())

    def _state(self, trial_id: str) -> dict | None:
        return {t["trial_id"]: t for t in self.trials()}.get(trial_id)

    def register(self, *, study_id, strategy_id, config, data_manifest_sha256, hypothesis,
                 change_reason, code, parent_trial_id=None) -> str:
        if parent_trial_id is not None and self._state(parent_trial_id) is None:
            raise ValueError(f"Unknown parent trial {parent_trial_id}.")
        now = datetime.now(UTC)
        trial_id = f"{now:%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:8]}"
        self._append({
            "event": "register", "trial_id": trial_id, "registered_at": now.isoformat(),
            "study_id": study_id, "strategy_id": strategy_id,
            "config": config, "config_sha256": canonical_sha256(config),
            "data_manifest_sha256": data_manifest_sha256,
            "code_commit": code.get("commit"), "code_dirty": code.get("dirty"),
            "source_sha256": code.get("source_sha256"),
            "parent_trial_id": parent_trial_id, "change_reason": change_reason,
            "hypothesis": hypothesis, "status": "REGISTERED", "result_path": None,
        })
        return trial_id

    def finish(self, trial_id, status, *, result_path=None, reason=None) -> None:
        if status not in TERMINAL:
            raise ValueError(f"Terminal status must be one of {sorted(TERMINAL)}.")
        current = self._state(trial_id)
        if current is None:
            raise ValueError(f"Unknown trial {trial_id}.")
        if current["status"] != "REGISTERED":
            raise ValueError(f"Trial {trial_id} already ended as {current['status']}.")
        self._append({"event": "finish", "trial_id": trial_id, "status": status,
                      "result_path": None if result_path is None else str(result_path),
                      "finished_at": datetime.now(UTC).isoformat(), "status_reason": reason})

    @contextmanager
    def trial(self, **registration):
        """Register, run the block, record FAILED if it raises or ends without an outcome."""
        trial_id = self.register(**registration)
        try:
            yield trial_id
        except BaseException as error:
            if self._state(trial_id)["status"] == "REGISTERED":
                self.finish(trial_id, "FAILED", reason=f"{type(error).__name__}: {error}")
            raise
        if self._state(trial_id)["status"] == "REGISTERED":
            self.finish(trial_id, "FAILED", reason="block ended without a terminal status")
