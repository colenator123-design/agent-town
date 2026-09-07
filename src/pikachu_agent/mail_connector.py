from __future__ import annotations

import re
import subprocess
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MailItem:
    sender: str
    subject: str
    unread: bool
    flagged: bool
    category: str = "其他"


CATEGORY_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("安全警示", ("security", "login", "登入", "驗證", "verification", "password", "密碼", "alert", "警示")),
    ("帳單付款", ("invoice", "receipt", "付款", "帳單", "收據", "payment", "刷卡", "statement")),
    ("物流購物", ("shipped", "delivery", "物流", "配送", "出貨", "訂單", "order", "蝦皮", "momo")),
    ("行程會議", ("meeting", "calendar", "邀請", "會議", "appointment", "預約", "行程", "zoom", "meet")),
    ("社群通知", ("facebook", "instagram", "linkedin", "discord", "notification", "社群", "留言")),
    ("電子報廣告", ("newsletter", "unsubscribe", "電子報", "優惠", "sale", "promotion", "行銷", "digest")),
    ("工作學校", ("project", "report", "作業", "課程", "學校", "教授", "老師", "研究", "university", "deadline")),
)


class AppleMailConnector:
    def __init__(self, project_root: Path):
        self.script = project_root / "tools" / "mail_today.applescript"

    def fetch_today(self) -> list[MailItem]:
        if not self.script.exists():
            raise RuntimeError("找不到 Mail connector script")
        process = subprocess.run(
            ["/usr/bin/osascript", str(self.script)],
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )
        if process.returncode != 0:
            detail = process.stderr.strip() or "Mail 無法回應"
            raise RuntimeError(f"無法讀取 macOS Mail：{detail}")
        items = []
        for line in process.stdout.splitlines():
            fields = line.split("\t")
            if len(fields) != 4:
                continue
            sender, subject, unread, flagged = fields
            item = MailItem(sender, subject, unread.lower() == "true", flagged.lower() == "true")
            items.append(self.classify(item))
        return items

    @staticmethod
    def classify(item: MailItem) -> MailItem:
        searchable = f"{item.sender} {item.subject}".lower()
        category = "其他"
        for candidate, keywords in CATEGORY_RULES:
            if any(keyword in searchable for keyword in keywords):
                category = candidate
                break
        return MailItem(item.sender, item.subject, item.unread, item.flagged, category)

    @staticmethod
    def summary(items: list[MailItem]) -> dict[str, int]:
        return dict(Counter(item.category for item in items))

    @staticmethod
    def sender_name(sender: str) -> str:
        match = re.match(r'\s*"?([^"<]+)', sender)
        return match.group(1).strip() if match else sender
