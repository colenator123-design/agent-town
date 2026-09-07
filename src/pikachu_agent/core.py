from __future__ import annotations

from collections.abc import Callable
import os
from pathlib import Path

from .executor import Executor
from .file_tools import FileTools
from .memory import MemoryStore
from .models import AgentStatus, ExecutionResult, Plan
from .models import Action, ActionKind
from .planner import RuleBasedPlanner
from .safety import WorkspacePolicy


class AgentCore:
    def __init__(self, project_root: Path, status_callback: Callable[[AgentStatus], None] | None = None):
        self.project_root = project_root.resolve()
        self.policy = WorkspacePolicy(self.project_root / "workspace")
        configured_roots = os.environ.get("PIKA_SCREENSHOT_DIRS")
        screenshot_roots = (
            [Path(item) for item in configured_roots.split(os.pathsep) if item]
            if configured_roots
            else [Path.home() / "Desktop", Path.home() / "Documents", Path.home() / "Downloads"]
        )
        self.tools = FileTools(self.policy, external_roots=screenshot_roots)
        retention_days = int(os.environ.get("PIKA_LOG_RETENTION_DAYS", "7"))
        self.memory = MemoryStore(
            self.project_root / "data" / "agent.sqlite3",
            retention_days=retention_days,
        )
        if os.environ.get("PIKA_ENABLE_AI") == "1":
            from .ai_planner import AIPlanner

            self.planner = AIPlanner(self.tools, model=os.environ.get("PIKA_MODEL", "gpt-5.2"))
        else:
            self.planner = RuleBasedPlanner(self.tools)
        self.executor = Executor(self.tools, self.memory)
        self.status_callback = status_callback or (lambda _status: None)

    def plan(self, request: str) -> Plan:
        self.status_callback(AgentStatus.PLANNING)
        plan = self.planner.create_plan(request)
        self.status_callback(AgentStatus.NEED_CONFIRMATION if plan.actions else AgentStatus.IDLE)
        return plan

    def plan_import(self, paths: list[Path]) -> Plan:
        self.status_callback(AgentStatus.PLANNING)
        plan = self.planner.create_import_plan(paths)
        self.status_callback(AgentStatus.NEED_CONFIRMATION if plan.actions else AgentStatus.IDLE)
        return plan

    def plan_note(self, name: str, content: str) -> Plan:
        self.status_callback(AgentStatus.PLANNING)
        safe_stem = "".join(character if character.isalnum() or character in "-_" else "_" for character in name)
        requested = Path("Notes") / f"{safe_stem or 'ocr-note'}.md"
        destination = self.planner.fallback._available_destination(requested, set()) if hasattr(self.planner, "fallback") else self.planner._available_destination(requested, set())
        actions = []
        if not self.policy.resolve("Notes").exists():
            actions.append(Action(ActionKind.CREATE_FOLDER, destination=Path("Notes")))
        actions.append(Action(ActionKind.WRITE_TEXT, destination=destination, content=content))
        plan = Plan(request=f"儲存 OCR 筆記 {destination.name}", actions=actions)
        self.status_callback(AgentStatus.NEED_CONFIRMATION)
        return plan

    def plan_named_import(self, source: Path, suggested_name: str) -> Plan:
        self.status_callback(AgentStatus.PLANNING)
        safe_stem = "".join(
            character if character.isalnum() or character in "-_" else "_"
            for character in suggested_name
        ).strip("_-")[:60]
        requested = Path("Images") / f"{safe_stem or 'image'}{source.suffix.lower()}"
        planner = self.planner.fallback if hasattr(self.planner, "fallback") else self.planner
        destination = planner._available_destination(requested, set())
        actions = []
        if not self.policy.resolve("Images").exists():
            actions.append(Action(ActionKind.CREATE_FOLDER, destination=Path("Images")))
        actions.append(Action(ActionKind.IMPORT_FILE, source=source.resolve(), destination=destination))
        plan = Plan(request=f"依 OCR 內容命名並匯入 {source.name}", actions=actions)
        self.status_callback(AgentStatus.NEED_CONFIRMATION)
        return plan

    def execute(self, plan: Plan) -> ExecutionResult:
        self.status_callback(AgentStatus.EXECUTING)
        result = self.executor.execute(plan, confirmed=True)
        self.status_callback(AgentStatus.SUCCESS if result.success else AgentStatus.ERROR)
        return result

    def undo(self) -> ExecutionResult:
        self.status_callback(AgentStatus.EXECUTING)
        result = self.executor.undo_last()
        self.status_callback(AgentStatus.SUCCESS if result.success else AgentStatus.ERROR)
        return result
