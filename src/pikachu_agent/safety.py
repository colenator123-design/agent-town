from __future__ import annotations

from pathlib import Path


class SafetyError(RuntimeError):
    pass


class WorkspacePolicy:
    """Resolves all tool paths and rejects traversal outside one workspace."""

    def __init__(self, root: Path):
        self.root = root.expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def resolve(self, path: str | Path) -> Path:
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = self.root / candidate
        candidate = candidate.expanduser().resolve()
        if candidate != self.root and self.root not in candidate.parents:
            raise SafetyError(f"拒絕存取 workspace 外的路徑：{candidate}")
        return candidate
