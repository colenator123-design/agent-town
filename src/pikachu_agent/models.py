from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class AgentStatus(str, Enum):
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    PLANNING = "PLANNING"
    NEED_CONFIRMATION = "NEED_CONFIRMATION"
    EXECUTING = "EXECUTING"
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"


class RiskLevel(str, Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"


class ActionKind(str, Enum):
    CREATE_FOLDER = "create_folder"
    MOVE_FILE = "move_file"
    IMPORT_FILE = "import_file"
    TRASH_FILE = "trash_file"
    WRITE_TEXT = "write_text"


@dataclass(frozen=True)
class Action:
    kind: ActionKind
    source: Path | None = None
    destination: Path | None = None
    content: str | None = None
    risk: RiskLevel = RiskLevel.YELLOW

    def describe(self) -> str:
        if self.kind is ActionKind.CREATE_FOLDER:
            return f"建立資料夾  {self.destination}"
        if self.kind is ActionKind.IMPORT_FILE:
            return f"匯入  {self.source}  →  {self.destination}"
        if self.kind is ActionKind.TRASH_FILE:
            return f"移到垃圾桶  {self.source}"
        if self.kind is ActionKind.WRITE_TEXT:
            return f"儲存文字筆記  {self.destination}"
        return f"移動  {self.source}  →  {self.destination}"


@dataclass
class Plan:
    request: str
    actions: list[Action] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def needs_confirmation(self) -> bool:
        return any(action.risk is not RiskLevel.GREEN for action in self.actions)


@dataclass
class ExecutionResult:
    success: bool
    completed: list[Action] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
