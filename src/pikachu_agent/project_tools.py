from __future__ import annotations

import re
from pathlib import Path

from .safety import SafetyError, WorkspacePolicy


class ProjectTools:
    """Safe filesystem operations confined to the user's Project directory."""

    def __init__(self, root: Path, *, trash_callback=None):
        self.policy = WorkspacePolicy(root)
        if trash_callback is None:
            from send2trash import send2trash

            trash_callback = send2trash
        self._trash_callback = trash_callback

    @property
    def root(self) -> Path:
        return self.policy.root

    def resolve(self, path: str | Path = ".") -> Path:
        return self.policy.resolve(path)

    def children(self, path: str | Path = ".") -> list[Path]:
        target = self.resolve(path)
        if not target.is_dir():
            raise SafetyError(f"資料夾不存在：{target}")
        return sorted(
            (item for item in target.iterdir() if not item.name.startswith(".") and not item.is_symlink()),
            key=lambda item: (not item.is_dir(), item.name.casefold()),
        )

    def create_folder(self, parent: str | Path, name: str) -> Path:
        target = self.resolve(parent) / self._safe_name(name)
        if target.exists():
            raise SafetyError(f"已經有同名項目：{target.name}")
        target.mkdir()
        return target

    def create_text_file(self, parent: str | Path, name: str, content: str = "") -> Path:
        target = self.resolve(self.resolve(parent) / self._safe_name(name))
        if target.exists():
            raise SafetyError(f"已經有同名項目：{target.name}")
        target.write_text(content, encoding="utf-8")
        return target

    def rename(self, source: str | Path, new_name: str) -> Path:
        src = self.resolve(source)
        self._reject_root(src)
        if src.is_symlink():
            raise SafetyError("不會操作捷徑或符號連結")
        if not src.exists():
            raise SafetyError(f"項目不存在：{src}")
        destination = self.resolve(src.parent / self._safe_name(new_name))
        if destination.exists():
            raise SafetyError(f"已經有同名項目：{destination.name}")
        return src.rename(destination)

    def trash(self, source: str | Path) -> None:
        src = self.resolve(source)
        self._reject_root(src)
        if src.is_symlink():
            raise SafetyError("不會刪除捷徑或符號連結")
        if not src.exists():
            raise SafetyError(f"項目不存在：{src}")
        self._trash_callback(str(src))

    def relative(self, path: str | Path) -> Path:
        return self.resolve(path).relative_to(self.root)

    def _reject_root(self, path: Path) -> None:
        if path == self.root:
            raise SafetyError("Project 主資料夾不能重新命名或刪除")

    @staticmethod
    def _safe_name(name: str) -> str:
        cleaned = name.strip()
        if not cleaned or cleaned in {".", ".."}:
            raise SafetyError("名稱不能是空白")
        if "/" in cleaned or "\\" in cleaned or "\0" in cleaned:
            raise SafetyError("名稱不能包含路徑符號")
        if re.search(r"[\r\n]", cleaned):
            raise SafetyError("名稱不能包含換行")
        return cleaned
