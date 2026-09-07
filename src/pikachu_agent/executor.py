from __future__ import annotations

from .file_tools import FileTools
from .memory import MemoryStore
from .models import Action, ActionKind, ExecutionResult, Plan


class Executor:
    def __init__(self, tools: FileTools, memory: MemoryStore):
        self.tools = tools
        self.memory = memory

    def execute(self, plan: Plan, *, confirmed: bool = False, record: bool = True) -> ExecutionResult:
        if plan.needs_confirmation and not confirmed:
            return ExecutionResult(False, errors=["這個計畫需要使用者確認。"])

        result = ExecutionResult(True)
        for action in plan.actions:
            try:
                self._execute_action(action)
                result.completed.append(action)
            except Exception as exc:
                result.success = False
                result.errors.append(str(exc))
                break
        if record:
            self.memory.record(plan.request, result)
        return result

    def undo_last(self) -> ExecutionResult:
        entry = self.memory.last_undoable()
        if entry is None:
            return ExecutionResult(False, errors=["沒有可復原的操作。"])
        run_id, actions = entry
        plan = Plan(request="undo", actions=actions)
        result = self.execute(plan, confirmed=True, record=False)
        if result.success:
            self.memory.mark_undone(run_id)
        return result

    def _execute_action(self, action: Action) -> None:
        if action.kind is ActionKind.CREATE_FOLDER:
            assert action.destination is not None
            self.tools.create_folder(action.destination)
        elif action.kind is ActionKind.MOVE_FILE:
            assert action.source is not None and action.destination is not None
            self.tools.move_file(action.source, action.destination)
        elif action.kind is ActionKind.IMPORT_FILE:
            assert action.source is not None and action.destination is not None
            self.tools.import_file(action.source, action.destination)
        elif action.kind is ActionKind.TRASH_FILE:
            assert action.source is not None
            self.tools.trash_file(action.source)
        elif action.kind is ActionKind.WRITE_TEXT:
            assert action.destination is not None and action.content is not None
            self.tools.write_text(action.destination, action.content)
        else:
            raise ValueError(f"不支援的操作：{action.kind}")
