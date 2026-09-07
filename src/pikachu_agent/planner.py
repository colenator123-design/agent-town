from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path

from .file_tools import FileTools
from .models import Action, ActionKind, Plan, RiskLevel


DEFAULT_CATEGORIES: dict[str, set[str]] = {
    "Documents": {".pdf", ".doc", ".docx", ".txt", ".md", ".rtf"},
    "Images": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".svg"},
    "Audio": {".mp3", ".wav", ".m4a", ".aac", ".flac"},
    "Video": {".mp4", ".mov", ".mkv", ".avi", ".webm"},
    "Archives": {".zip", ".tar", ".gz", ".rar", ".7z"},
    "Code": {".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java"},
}

ALIASES = {
    "圖片": "Images",
    "照片": "Images",
    "影像": "Images",
    "文件": "Documents",
    "文檔": "Documents",
    "音樂": "Audio",
    "音訊": "Audio",
    "影片": "Video",
    "壓縮檔": "Archives",
    "程式": "Code",
}


class RuleBasedPlanner:
    """A deterministic V0.2 planner; an LLM planner can replace this class later."""

    def __init__(self, tools: FileTools):
        self.tools = tools

    def create_plan(self, request: str) -> Plan:
        if self._is_screenshot_cleanup(request):
            return self.create_screenshot_cleanup_plan(request)
        files = self.tools.list_files(".", recursive=True)
        explicit = self._parse_explicit_mapping(request)
        actions: list[Action] = []
        folders: set[Path] = set()
        reserved: set[Path] = set()
        managed_folders = set(DEFAULT_CATEGORIES) | set(explicit.values()) | {"Other", "Inbox"}

        for source in files:
            relative_source = source.relative_to(self.tools.policy.root)
            if relative_source.parts[0] in managed_folders:
                continue
            category = explicit.get(source.suffix.lower()) or self._default_category(source)
            if category is None:
                continue
            folder = Path(category)
            destination = self._available_destination(folder / source.name, reserved)
            if not self.tools.policy.resolve(folder).exists() and folder not in folders:
                actions.append(Action(ActionKind.CREATE_FOLDER, destination=folder))
                folders.add(folder)
            actions.append(Action(ActionKind.MOVE_FILE, source=relative_source, destination=destination))
            reserved.add(destination)

        notes = [] if actions else ["找不到可整理的檔案，或目的地已經存在同名檔案。"]
        return Plan(request=request, actions=actions, notes=notes)

    def create_screenshot_cleanup_plan(self, request: str) -> Plan:
        target_date = date.today() - timedelta(days=1) if "昨天" in request else date.today()
        screenshots = self.tools.find_screenshots(target_date)
        actions = [
            Action(ActionKind.TRASH_FILE, source=path, risk=RiskLevel.RED)
            for path in screenshots
        ]
        day_label = "昨天" if target_date != date.today() else "今天"
        notes = [f"找到 {len(actions)} 個{day_label}的截圖；確認後只會移到 macOS 垃圾桶。"]
        if not actions:
            notes.append("已搜尋 Desktop、Documents 與 Downloads，沒有符合項目。")
        return Plan(request=request, actions=actions, notes=notes)

    def create_import_plan(self, paths: list[Path]) -> Plan:
        actions: list[Action] = []
        reserved: set[Path] = set()
        inbox = Path("Inbox")
        valid = [path.expanduser().resolve() for path in paths if path.expanduser().is_file()]
        if valid and not self.tools.policy.resolve(inbox).exists():
            actions.append(Action(ActionKind.CREATE_FOLDER, destination=inbox))
        for source in valid:
            destination = self._available_destination(inbox / source.name, reserved)
            actions.append(Action(ActionKind.IMPORT_FILE, source=source, destination=destination))
            reserved.add(destination)
        notes = [] if actions else ["拖入的項目中沒有可匯入的一般檔案。"]
        return Plan(request=f"匯入 {len(valid)} 個拖放檔案", actions=actions, notes=notes)

    def _available_destination(self, requested: Path, reserved: set[Path]) -> Path:
        candidate = requested
        counter = 2
        while self.tools.policy.resolve(candidate).exists() or candidate in reserved:
            candidate = requested.with_name(f"{requested.stem}_{counter}{requested.suffix}")
            counter += 1
        return candidate

    @staticmethod
    def _is_screenshot_cleanup(request: str) -> bool:
        screenshot_words = ("截圖", "螢幕截圖", "screenshot", "screen shot")
        deletion_words = ("刪除", "刪掉", "清掉", "清理", "垃圾桶", "delete", "remove", "trash")
        normalized = request.lower()
        return any(word in normalized for word in screenshot_words) and any(
            word in normalized for word in deletion_words
        )

    @staticmethod
    def _parse_explicit_mapping(request: str) -> dict[str, str]:
        mapping: dict[str, str] = {}
        normalized = request.replace("，", ",").replace("。", ".")
        # Examples: PDF 放 Documents / .jpg 移到 Images
        for extension, folder in re.findall(
            r"(?:^|[,\s])\.?([a-zA-Z0-9]{1,8})\s*(?:檔案)?\s*(?:放到?|移到|歸到|->|→)\s*([\w\-\u4e00-\u9fff]+)",
            normalized,
            flags=re.IGNORECASE,
        ):
            mapping[f".{extension.lower()}"] = ALIASES.get(folder, folder)
        for chinese, folder in ALIASES.items():
            match = re.search(rf"{chinese}\s*(?:放到?|移到|歸到|->|→)\s*([\w\-\u4e00-\u9fff]+)", normalized)
            if match:
                destination = ALIASES.get(match.group(1), match.group(1))
                for ext in DEFAULT_CATEGORIES[folder]:
                    mapping[ext] = destination
        return mapping

    @staticmethod
    def _default_category(path: Path) -> str | None:
        suffix = path.suffix.lower()
        for category, extensions in DEFAULT_CATEGORIES.items():
            if suffix in extensions:
                return category
        return "Other" if suffix else None
