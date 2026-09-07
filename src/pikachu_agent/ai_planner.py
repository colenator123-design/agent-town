from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .file_tools import FileTools
from .models import Action, ActionKind, Plan
from .planner import DEFAULT_CATEGORIES, RuleBasedPlanner
from .safety import SafetyError


PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "moves": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "source": {"type": "string"},
                    "folder": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["source", "folder", "reason"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["moves"],
    "additionalProperties": False,
}


class AIPlanner:
    """Opt-in planner that may propose actions but can never execute tools."""

    def __init__(self, tools: FileTools, *, model: str = "gpt-5.2", client: Any = None):
        self.tools = tools
        self.model = model
        if client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise RuntimeError("AI 模式需要執行：uv sync --extra ai") from exc
            client = OpenAI()
        self.client = client
        self.fallback = RuleBasedPlanner(tools)

    def create_plan(self, request: str) -> Plan:
        if self.fallback._is_screenshot_cleanup(request):
            return self.fallback.create_screenshot_cleanup_plan(request)
        candidates = self._candidates()
        if not candidates:
            return Plan(request=request, notes=["找不到尚未整理的檔案。"])
        response = self.client.responses.create(
            model=self.model,
            store=False,
            instructions=(
                "You are a file organization planner. Return a conservative organization proposal. "
                "Use only source paths from the provided list. Folder paths must be relative, concise, "
                "must not start with a dot, and must not contain '..'. Never propose deletion or overwrite."
            ),
            input=json.dumps({"request": request, "files": candidates}, ensure_ascii=False),
            text={
                "format": {
                    "type": "json_schema",
                    "name": "file_organization_plan",
                    "strict": True,
                    "schema": PLAN_SCHEMA,
                }
            },
        )
        return self._validated_plan(request, candidates, json.loads(response.output_text))

    def create_import_plan(self, paths: list[Path]) -> Plan:
        return self.fallback.create_import_plan(paths)

    def _candidates(self) -> list[str]:
        managed = set(DEFAULT_CATEGORIES) | {"Other", "Inbox"}
        candidates = []
        for source in self.tools.list_files(".", recursive=True):
            relative = source.relative_to(self.tools.policy.root)
            if relative.parts[0] not in managed:
                candidates.append(str(relative))
        return candidates

    def _validated_plan(self, request: str, candidates: list[str], payload: dict[str, Any]) -> Plan:
        allowed = set(candidates)
        actions: list[Action] = []
        folders: set[Path] = set()
        reserved: set[Path] = set()
        for item in payload.get("moves", []):
            source_text = item.get("source", "")
            folder_text = item.get("folder", "")
            if source_text not in allowed:
                raise SafetyError(f"AI 提出了未知來源：{source_text}")
            folder = Path(folder_text)
            if not folder_text or any(part.startswith(".") for part in folder.parts):
                raise SafetyError(f"AI 提出了不安全的資料夾：{folder_text}")
            self.tools.policy.resolve(folder)
            if folder not in folders and not self.tools.policy.resolve(folder).exists():
                actions.append(Action(ActionKind.CREATE_FOLDER, destination=folder))
                folders.add(folder)
            source = Path(source_text)
            destination = self.fallback._available_destination(folder / source.name, reserved)
            actions.append(Action(ActionKind.MOVE_FILE, source=source, destination=destination))
            reserved.add(destination)
        notes = ["AI 只產生計畫；所有操作仍須確認並經過 workspace 安全檢查。"]
        if not actions:
            notes.append("AI 沒有提出需要執行的操作。")
        return Plan(request=request, actions=actions, notes=notes)
