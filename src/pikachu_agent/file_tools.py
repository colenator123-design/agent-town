from __future__ import annotations

import shutil
from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path

from .safety import SafetyError, WorkspacePolicy


class FileTools:
    def __init__(
        self,
        policy: WorkspacePolicy,
        *,
        external_roots: list[Path] | None = None,
        trash_callback: Callable[[str], None] | None = None,
    ):
        self.policy = policy
        self.external_roots = [path.expanduser().resolve() for path in (external_roots or [])]
        if trash_callback is None:
            from send2trash import send2trash

            trash_callback = send2trash
        self._trash_callback = trash_callback

    def list_files(self, path: str | Path = ".", *, recursive: bool = False) -> list[Path]:
        target = self.policy.resolve(path)
        if not target.exists() or not target.is_dir():
            raise SafetyError(f"資料夾不存在：{target}")
        candidates = target.rglob("*") if recursive else target.iterdir()
        return sorted(
            p for p in candidates
            if p.is_file()
            and not p.is_symlink()
            and not any(part.startswith(".") for part in p.relative_to(target).parts)
        )

    def create_folder(self, path: str | Path) -> Path:
        target = self.policy.resolve(path)
        target.mkdir(parents=True, exist_ok=True)
        return target

    def move_file(self, source: str | Path, destination: str | Path) -> Path:
        src = self.policy.resolve(source)
        dst = self.policy.resolve(destination)
        if not src.is_file():
            raise SafetyError(f"來源檔案不存在：{src}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            raise SafetyError(f"目的地已存在，不會覆寫：{dst}")
        return Path(shutil.move(str(src), str(dst)))

    def import_file(self, source: str | Path, destination: str | Path) -> Path:
        """Copy a user-selected file into the sandbox without modifying its source."""
        src = Path(source).expanduser().resolve()
        dst = self.policy.resolve(destination)
        if not src.is_file() or src.is_symlink():
            raise SafetyError(f"只能匯入一般檔案：{src}")
        if dst.exists():
            raise SafetyError(f"目的地已存在，不會覆寫：{dst}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        return Path(shutil.copy2(src, dst))

    def find_screenshots(self, target_date: date) -> list[Path]:
        matches: list[Path] = []
        prefixes = ("截圖", "螢幕截圖", "screen shot", "screenshot")
        extensions = {".png", ".jpg", ".jpeg", ".heic", ".webp"}
        for root in self.external_roots:
            if not root.is_dir():
                continue
            try:
                candidates = root.iterdir()
                for path in candidates:
                    if path.is_symlink() or not path.is_file():
                        continue
                    if path.suffix.lower() not in extensions or not path.name.lower().startswith(prefixes):
                        continue
                    metadata = path.stat()
                    timestamp = getattr(metadata, "st_birthtime", metadata.st_mtime)
                    if datetime.fromtimestamp(timestamp).astimezone().date() == target_date:
                        matches.append(path.resolve())
            except PermissionError:
                continue
        return sorted(matches, key=lambda item: item.name.lower())

    def trash_file(self, source: str | Path) -> None:
        src = Path(source).expanduser().resolve()
        if src.is_symlink() or not src.is_file():
            raise SafetyError(f"只能將一般檔案移到垃圾桶：{src}")
        allowed = src == self.policy.root or self.policy.root in src.parents
        allowed = allowed or any(src == root or root in src.parents for root in self.external_roots)
        if not allowed:
            raise SafetyError(f"拒絕清理未授權位置的檔案：{src}")
        self._trash_callback(str(src))

    def write_text(self, destination: str | Path, content: str) -> Path:
        dst = self.policy.resolve(destination)
        if dst.exists():
            raise SafetyError(f"目的地已存在，不會覆寫：{dst}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(content, encoding="utf-8")
        return dst
