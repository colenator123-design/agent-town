from __future__ import annotations

import html
import math
from pathlib import Path

from PySide6.QtCore import QObject, QPoint, QRectF, QRunnable, Qt, QThreadPool, QTimer, Signal, Slot
from PySide6.QtGui import (
    QAction, QColor, QFont, QLinearGradient, QMouseEvent, QMovie, QPainter,
    QPainterPath, QPen, QPixmap, QRadialGradient,
)
from PySide6.QtWidgets import (
    QApplication, QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel,
    QLineEdit, QMenu, QPushButton, QSizePolicy, QTextBrowser, QVBoxLayout, QWidget,
)

from .core import AgentCore
from .image_tools import LocalImageTools
from .models import AgentStatus, Plan


STATUS_COPY = {
    AgentStatus.IDLE: ("READY", "皮卡！今天想完成什麼？"),
    AgentStatus.LISTENING: ("LISTENING", "我在聽，交給我吧。"),
    AgentStatus.PLANNING: ("THINKING", "正在拆解任務與檢查風險…"),
    AgentStatus.NEED_CONFIRMATION: ("REVIEW", "計畫準備好了，確認後才會執行。"),
    AgentStatus.EXECUTING: ("WORKING", "正在安全地執行任務…"),
    AgentStatus.SUCCESS: ("DONE", "任務完成！皮卡皮卡 ⚡"),
    AgentStatus.ERROR: ("ERROR", "遇到一點問題，看看下方說明。"),
}

STATUS_COLORS = {
    AgentStatus.IDLE: "#8ee3b2", AgentStatus.LISTENING: "#ffe16b",
    AgentStatus.PLANNING: "#7dc8ff", AgentStatus.NEED_CONFIRMATION: "#ffcc66",
    AgentStatus.EXECUTING: "#ffe16b", AgentStatus.SUCCESS: "#83e6a8",
    AgentStatus.ERROR: "#ff7d86",
}


class SpeechCard(QFrame):
    """Rounded translucent card with a speech-bubble tail."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(38)
        shadow.setOffset(0, 12)
        shadow.setColor(QColor(0, 0, 0, 125))
        self.setGraphicsEffect(shadow)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(4, 4, self.width() - 8, self.height() - 18)
        path = QPainterPath()
        path.addRoundedRect(rect, 22, 22)
        tail = QPainterPath()
        tail.moveTo(self.width() / 2 - 13, self.height() - 15)
        tail.lineTo(self.width() / 2 + 15, self.height() - 15)
        tail.lineTo(self.width() / 2 + 4, self.height() - 2)
        tail.closeSubpath()
        path.addPath(tail)
        gradient = QLinearGradient(0, 0, self.width(), self.height())
        gradient.setColorAt(0, QColor(31, 31, 35, 250))
        gradient.setColorAt(1, QColor(17, 18, 21, 250))
        painter.setBrush(gradient)
        painter.setPen(QPen(QColor(255, 221, 75, 185), 1.4))
        painter.drawPath(path)
        super().paintEvent(event)


class StatusPill(QLabel):
    def set_agent_status(self, status: AgentStatus) -> None:
        label, _ = STATUS_COPY[status]
        color = STATUS_COLORS[status]
        self.setText(f"●  {label}")
        self.setStyleSheet(
            f"color:{color};background:rgba(255,255,255,14);border:1px solid rgba(255,255,255,24);"
            "border-radius:10px;padding:4px 9px;font-size:10px;font-weight:700;letter-spacing:1px;"
        )


class AvatarWidget(QWidget):
    clicked = Signal()
    files_dropped = Signal(list)
    go_home = Signal()

    def __init__(self, animated_asset: Path, fallback_asset: Path, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedSize(230, 214)
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("點擊對話 · 拖曳移動 · 右鍵選單")
        self._pixmap = QPixmap(str(fallback_asset)) if fallback_asset.exists() else QPixmap()
        self._movie = QMovie(str(animated_asset)) if animated_asset.exists() else QMovie()
        if self._movie.isValid():
            self._movie.setCacheMode(QMovie.CacheMode.CacheAll)
            self._movie.frameChanged.connect(lambda _frame: self.update())
            self._movie.start()
        self._status = AgentStatus.IDLE
        self._phase = 0.0
        self._press_position: QPoint | None = None
        self._drop_hover = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._animate)
        self._timer.start(42)

    def set_status(self, status: AgentStatus) -> None:
        self._status = status
        if self._movie.isValid():
            speeds = {
                AgentStatus.IDLE: 115,
                AgentStatus.LISTENING: 140,
                AgentStatus.PLANNING: 175,
                AgentStatus.NEED_CONFIRMATION: 105,
                AgentStatus.EXECUTING: 240,
                AgentStatus.SUCCESS: 300,
                AgentStatus.ERROR: 65,
            }
            self._movie.setSpeed(speeds[status])
        self.update()

    def _animate(self) -> None:
        self._phase += 0.24 if self._status is AgentStatus.EXECUTING else 0.11
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.RightButton:
            self._show_menu(event.globalPosition().toPoint())
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_position = event.globalPosition().toPoint()
            self.window().setProperty("drag_origin", event.globalPosition().toPoint() - self.window().pos())

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton:
            origin = self.window().property("drag_origin")
            if isinstance(origin, QPoint):
                self.window().move(event.globalPosition().toPoint() - origin)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._press_position is not None:
            if (event.globalPosition().toPoint() - self._press_position).manhattanLength() < 7:
                self.clicked.emit()
        self._press_position = None

    def _show_menu(self, position: QPoint) -> None:
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu{background:#222328;color:white;border:1px solid #555;border-radius:8px;padding:6px;}"
            "QMenu::item{padding:7px 20px;border-radius:5px;}QMenu::item:selected{background:#f1ca36;color:#201b12;}"
        )
        toggle = QAction("開啟 / 收起對話", menu)
        toggle.triggered.connect(self.clicked.emit)
        home_action = QAction("回到 Agent Town", menu)
        home_action.triggered.connect(self.go_home.emit)
        quit_action = QAction("讓皮卡丘休息", menu)
        quit_action.triggered.connect(QApplication.instance().quit)
        menu.addAction(toggle)
        menu.addAction(home_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        menu.exec(position)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls() and any(url.isLocalFile() for url in event.mimeData().urls()):
            self._drop_hover = True
            self.update()
            event.acceptProposedAction()

    def dragLeaveEvent(self, event) -> None:
        self._drop_hover = False
        self.update()
        event.accept()

    def dropEvent(self, event) -> None:
        self._drop_hover = False
        paths = [Path(url.toLocalFile()) for url in event.mimeData().urls() if url.isLocalFile()]
        if paths:
            self.files_dropped.emit(paths)
            event.acceptProposedAction()
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        bob = math.sin(self._phase) * (5 if self._status is AgentStatus.IDLE else 2.5)
        pulse = (math.sin(self._phase * 1.6) + 1) / 2
        glow = QRadialGradient(115, 119 + bob, 105 if self._drop_hover else 92)
        center_alpha = 145 if self._drop_hover else int(62 + pulse * 38)
        glow.setColorAt(0, QColor(255, 216, 53, center_alpha))
        glow.setColorAt(0.55, QColor(255, 205, 40, 55 if self._drop_hover else 23))
        glow.setColorAt(1, QColor(255, 205, 40, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(glow)
        painter.drawEllipse(QRectF(23, 28 + bob, 184, 184))
        animated_frame = self._movie.currentPixmap() if self._movie.isValid() else QPixmap()
        if not animated_frame.isNull():
            # The source is pixel art: crisp nearest-neighbour scaling makes the
            # individual ear, paw and tail frames more expressive than smoothing.
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
            painter.drawPixmap(QRectF(30, 9 + bob, 170, 170).toRect(), animated_frame)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        elif not self._pixmap.isNull():
            painter.drawPixmap(QRectF(27, 14 + bob, 176, 176).toRect(), self._pixmap)
        painter.setPen(QPen(QColor(255, 223, 77, 145), 1))
        painter.setBrush(QColor(20, 21, 24, 205))
        painter.drawRoundedRect(QRectF(54, 185, 122, 23), 11, 11)
        painter.setPen(QColor("#ffe16b"))
        painter.setFont(QFont("Arial", 9, QFont.Weight.DemiBold))
        badge = "DROP FILES HERE" if self._drop_hover else "PIKA  •  ONLINE"
        painter.drawText(QRectF(54, 185, 122, 23), Qt.AlignmentFlag.AlignCenter, badge)
        if self._status in {AgentStatus.PLANNING, AgentStatus.EXECUTING, AgentStatus.SUCCESS}:
            painter.setFont(QFont("Arial", 20, QFont.Weight.Bold))
            painter.setPen(QColor(255, 225, 64, int(150 + pulse * 105)))
            painter.drawText(16, int(82 + bob), "ϟ")
            painter.drawText(194, int(58 + bob), "ϟ")


class WorkerSignals(QObject):
    result = Signal(object)
    error = Signal(str)
    finished = Signal()


class FunctionWorker(QRunnable):
    def __init__(self, function):
        super().__init__()
        self.function = function
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            result = self.function()
        except Exception as exc:
            try:
                self.signals.error.emit(str(exc))
            except RuntimeError:
                pass  # The app may have closed while background work was finishing.
        else:
            try:
                self.signals.result.emit(result)
            except RuntimeError:
                pass
        finally:
            try:
                self.signals.finished.emit()
            except RuntimeError:
                pass


class PikachuWindow(QWidget):
    status_changed = Signal(object)
    return_home = Signal()

    def __init__(self, project_root: Path):
        super().__init__()
        self.project_root = project_root
        self.current_plan: Plan | None = None
        self.status_changed.connect(self.set_status)
        self.core = AgentCore(project_root, self.status_changed.emit)
        self.image_tools = LocalImageTools(project_root)
        self._dropped_paths: list[Path] = []
        self._ocr_text = ""
        self._context_buttons: list[QPushButton] = []
        self.thread_pool = QThreadPool.globalInstance()
        self._workers: set[FunctionWorker] = set()
        self._status = AgentStatus.IDLE
        self.setWindowTitle("Pikachu Desktop Agent")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(440)
        self.panel = self._build_panel()
        self.avatar = AvatarWidget(
            project_root / "assets" / "pikachu-animated.gif",
            project_root / "assets" / "pikachu.png",
        )
        self.avatar.clicked.connect(self.toggle_panel)
        self.avatar.files_dropped.connect(self.prepare_import)
        self.avatar.go_home.connect(self._return_to_town)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 0)
        layout.setSpacing(0)
        layout.addWidget(self.panel)
        avatar_row = QHBoxLayout()
        avatar_row.addStretch()
        avatar_row.addWidget(self.avatar)
        avatar_row.addStretch()
        layout.addLayout(avatar_row)
        self.panel.hide()
        self.set_status(AgentStatus.IDLE)
        self.adjustSize()

    def _build_panel(self) -> SpeechCard:
        panel = SpeechCard()
        panel.setStyleSheet(
            """
            QLabel{color:#f7f7f8;background:transparent;border:none;}
            QLineEdit{background:rgba(255,255,255,245);color:#242427;border:2px solid transparent;
                border-radius:15px;padding:11px 14px;font-size:13px;selection-background-color:#e9c32e;}
            QLineEdit:focus{border:2px solid #f0cb39;}
            QTextBrowser{background:rgba(255,255,255,10);color:#e9e9eb;border:1px solid rgba(255,255,255,20);
                border-radius:13px;padding:10px;font-size:12px;}
            QPushButton{background:#f0ca35;color:#211c12;border:none;border-radius:11px;
                padding:9px 14px;font-size:12px;font-weight:700;}
            QPushButton:hover{background:#ffe36c;} QPushButton:pressed{background:#d9b522;}
            QPushButton#secondary{background:rgba(255,255,255,14);color:#dedee1;
                border:1px solid rgba(255,255,255,28);}
            QPushButton#secondary:hover{background:rgba(255,255,255,28);}
            QPushButton#quick{background:rgba(255,255,255,9);color:#bebec3;
                border:1px solid rgba(255,255,255,18);border-radius:10px;padding:7px 10px;font-weight:500;}
            QPushButton#quick:hover{color:#fff;border-color:#d5b735;background:rgba(240,202,53,18);}
            """
        )
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 18, 20, 29)
        layout.setSpacing(11)
        header = QHBoxLayout()
        brand = QLabel("⚡  PIKA AGENT")
        brand.setStyleSheet("font-size:12px;font-weight:800;letter-spacing:1.5px;color:#ffe16b;")
        self.status_pill = StatusPill()
        header.addWidget(brand)
        header.addStretch()
        header.addWidget(self.status_pill)
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.setStyleSheet("font-size:18px;font-weight:650;color:#fafafa;padding:3px 0;")
        input_row = QHBoxLayout()
        input_row.setSpacing(7)
        self.input = QLineEdit()
        self.input.setPlaceholderText("告訴皮卡丘要做什麼…")
        self.input.returnPressed.connect(self.submit)
        self.send_button = QPushButton("送出  ↗")
        self.send_button.setFixedWidth(82)
        self.send_button.clicked.connect(self.submit)
        input_row.addWidget(self.input)
        input_row.addWidget(self.send_button)
        quick_row = QHBoxLayout()
        quick_row.setSpacing(6)
        for label, command in (("整理檔案", "幫我整理這些檔案"), ("最近紀錄", "__history__"), ("復原上次", "__undo__")):
            button = QPushButton(label)
            button.setObjectName("quick")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda _checked=False, cmd=command: self.quick_action(cmd))
            quick_row.addWidget(button)
        quick_row.addStretch()
        self.context_row = QHBoxLayout()
        self.context_row.setSpacing(6)
        self.preview = QTextBrowser()
        self.preview.setMaximumHeight(175)
        self.preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.preview.hide()
        self.action_row = QHBoxLayout()
        self.action_summary = QLabel("YELLOW · 需要確認")
        self.action_summary.setStyleSheet("color:#e9c94f;font-size:11px;font-weight:700;")
        self.cancel_button = QPushButton("取消")
        self.cancel_button.setObjectName("secondary")
        self.cancel_button.clicked.connect(self.cancel_plan)
        self.confirm_button = QPushButton("確認執行  ⚡")
        self.confirm_button.clicked.connect(self.confirm_plan)
        self.action_row.addWidget(self.action_summary)
        self.action_row.addStretch()
        self.action_row.addWidget(self.cancel_button)
        self.action_row.addWidget(self.confirm_button)
        layout.addLayout(header)
        layout.addWidget(self.message)
        layout.addLayout(input_row)
        layout.addLayout(quick_row)
        layout.addLayout(self.context_row)
        layout.addWidget(self.preview)
        layout.addLayout(self.action_row)
        self._show_confirmation(False)
        return panel

    def toggle_panel(self) -> None:
        self.panel.setVisible(not self.panel.isVisible())
        self.adjustSize()
        if self.panel.isVisible():
            self.set_status(AgentStatus.LISTENING)
            self.input.setFocus()

    def _return_to_town(self) -> None:
        self.hide()
        self.return_home.emit()

    def set_status(self, status: AgentStatus) -> None:
        self._status = status
        if hasattr(self, "avatar"):
            self.avatar.set_status(status)
        if hasattr(self, "status_pill"):
            self.status_pill.set_agent_status(status)
        if hasattr(self, "message"):
            self.message.setText(STATUS_COPY[status][1])

    def quick_action(self, command: str) -> None:
        if command == "__history__":
            self.show_history()
        elif command == "__undo__":
            self.undo()
        else:
            self.input.setText(command)
            self.submit()

    def prepare_import(self, paths: list[Path]) -> None:
        if not self.panel.isVisible():
            self.panel.show()
        image_details = self.image_tools.inspect(paths)
        if image_details and len(image_details) == len(paths):
            self._dropped_paths = [detail.path for detail in image_details]
            self.current_plan = None
            rows = []
            for detail in image_details:
                size = detail.size_bytes / 1024
                rows.append(
                    f"<div style='margin:5px 0'><b>{html.escape(detail.path.name)}</b><br>"
                    f"<span style='color:#92949b'>{detail.width} × {detail.height} · {detail.format} · {size:.1f} KB</span></div>"
                )
            self._set_preview(
                f"<div style='color:#ffe16b;font-weight:700;margin-bottom:7px'>IMAGE ASSISTANT · {len(paths)} 張圖片</div>"
                + "".join(rows)
            )
            self._set_context_actions(
                [
                    ("辨識文字 OCR", self.run_ocr),
                    ("本機分析", self.run_image_analysis),
                    *(([("檢查重複", self.run_duplicate_check)]) if len(paths) > 1 else []),
                    ("匯入 Inbox", lambda: self._prepare_import_plan(paths)),
                ]
            )
            self._show_confirmation(False)
            self.set_status(AgentStatus.LISTENING)
            self.adjustSize()
            return
        self._prepare_import_plan(paths)

    def _prepare_import_plan(self, paths: list[Path]) -> None:
        self._set_context_actions([])
        self.input.setText(f"匯入 {len(paths)} 個檔案到 Inbox")
        try:
            self.current_plan = self.core.plan_import(paths)
        except Exception as exc:
            self.set_status(AgentStatus.ERROR)
            self._set_preview(f"<b>無法匯入</b><br>{html.escape(str(exc))}")
            return
        rows = [
            f"<div style='margin:4px 0'><span style='color:#777b84'>{number:02}</span>&nbsp;&nbsp;"
            f"{html.escape(action.describe())}</div>"
            for number, action in enumerate(self.current_plan.actions, 1)
        ]
        self._set_preview(
            f"<div style='color:#ffe16b;font-weight:700;margin-bottom:7px'>IMPORT PREVIEW · {len(paths)} 個項目</div>"
            + "".join(rows)
        )
        self._configure_plan_risk(self.current_plan)
        self._show_confirmation(bool(self.current_plan.actions))
        self.adjustSize()

    def run_ocr(self) -> None:
        if not self._dropped_paths:
            return
        self.set_status(AgentStatus.PLANNING)
        self._set_busy(True)
        self._set_preview("<span style='color:#7dc8ff'>正在使用 macOS Vision 辨識文字…</span>")
        self._run_background(lambda: self.image_tools.recognize_text(self._dropped_paths), self._ocr_ready)

    def _ocr_ready(self, recognized: str) -> None:
        self._set_busy(False)
        self._ocr_text = recognized
        formatted = html.escape(recognized).replace("\n", "<br>")
        self._set_preview(
            "<div style='color:#83e6a8;font-weight:700;margin-bottom:7px'>OCR COMPLETE</div>" + formatted
        )
        actions = [("複製文字", self.copy_ocr), ("存成 Markdown", self.prepare_ocr_note)]
        if len(self._dropped_paths) == 1 and "（沒有辨識到文字）" not in recognized:
            actions.append(("智慧命名匯入", self.prepare_smart_import))
        actions.append(("匯入圖片", lambda: self._prepare_import_plan(self._dropped_paths)))
        self._set_context_actions(actions)
        self.set_status(AgentStatus.SUCCESS)

    def run_image_analysis(self) -> None:
        if not self._dropped_paths:
            return
        self.set_status(AgentStatus.PLANNING)
        self._set_busy(True)
        self._set_preview("<span style='color:#7dc8ff'>正在使用 macOS Vision 分析畫面與 QR／條碼…</span>")
        self._run_background(lambda: self.image_tools.analyze(self._dropped_paths), self._analysis_ready)

    def _analysis_ready(self, result: str) -> None:
        self._set_busy(False)
        formatted = html.escape(result).replace("\n", "<br>")
        self._set_preview(
            "<div style='color:#83e6a8;font-weight:700;margin-bottom:7px'>LOCAL VISION COMPLETE</div>"
            + formatted
        )
        self._set_context_actions(
            [("辨識文字 OCR", self.run_ocr), ("匯入圖片", lambda: self._prepare_import_plan(self._dropped_paths))]
        )
        self.set_status(AgentStatus.SUCCESS)

    def run_duplicate_check(self) -> None:
        self._set_busy(True)
        self.set_status(AgentStatus.PLANNING)
        self._run_background(lambda: self.image_tools.find_duplicates(self._dropped_paths), self._duplicates_ready)

    def _duplicates_ready(self, groups: list[list[Path]]) -> None:
        self._set_busy(False)
        if not groups:
            self._set_preview("<span style='color:#83e6a8;font-weight:700'>✓ 沒有內容完全相同的圖片</span>")
        else:
            rows = [f"<div style='color:#ffcc66;font-weight:700'>找到 {len(groups)} 組重複圖片</div>"]
            for number, group in enumerate(groups, 1):
                names = " · ".join(html.escape(path.name) for path in group)
                rows.append(f"<div style='margin:6px 0'>{number:02}　{names}</div>")
            self._set_preview("".join(rows))
        self.set_status(AgentStatus.SUCCESS)

    def copy_ocr(self) -> None:
        QApplication.clipboard().setText(self._ocr_text)
        self.message.setText("文字已複製到剪貼簿 ⚡")

    def prepare_ocr_note(self) -> None:
        if not self._ocr_text:
            return
        name = f"{self._dropped_paths[0].stem}-ocr" if self._dropped_paths else "ocr-note"
        self.current_plan = self.core.plan_note(name, self._ocr_text)
        self._set_context_actions([])
        rows = "".join(
            f"<div style='margin:4px 0'>{html.escape(action.describe())}</div>"
            for action in self.current_plan.actions
        )
        self._set_preview("<div style='color:#ffe16b;font-weight:700'>SAVE NOTE PREVIEW</div>" + rows)
        self._configure_plan_risk(self.current_plan)
        self._show_confirmation(True)

    def prepare_smart_import(self) -> None:
        if len(self._dropped_paths) != 1:
            return
        candidates = [
            line.strip() for line in self._ocr_text.splitlines()
            if line.strip() and not line.startswith("##") and not line.startswith("（")
        ]
        suggestion = candidates[0] if candidates else self._dropped_paths[0].stem
        self.current_plan = self.core.plan_named_import(self._dropped_paths[0], suggestion)
        self._set_context_actions([])
        rows = "".join(
            f"<div style='margin:4px 0'>{html.escape(action.describe())}</div>"
            for action in self.current_plan.actions
        )
        self._set_preview("<div style='color:#ffe16b;font-weight:700'>SMART IMPORT PREVIEW</div>" + rows)
        self._configure_plan_risk(self.current_plan)
        self._show_confirmation(True)

    def submit(self) -> None:
        request = self.input.text().strip()
        if not request:
            return
        if request.lower() in {"undo", "復原", "復原上一個操作", "復原上次"}:
            self.undo()
            return
        self._set_busy(True)
        self._run_background(lambda: self.core.plan(request), self._plan_ready)

    def _plan_ready(self, plan: Plan) -> None:
        self.current_plan = plan
        self._set_busy(False)
        if not self.current_plan.actions:
            notes = "<br>".join(html.escape(note) for note in self.current_plan.notes)
            self._set_preview(f"<span style='color:#9fa0a6'>沒有需要執行的操作</span><br>{notes}")
            self._show_confirmation(False)
            return
        folders = sum(action.kind.value == "create_folder" for action in self.current_plan.actions)
        moves = sum(action.kind.value == "move_file" for action in self.current_plan.actions)
        imports = sum(action.kind.value == "import_file" for action in self.current_plan.actions)
        trash = sum(action.kind.value == "trash_file" for action in self.current_plan.actions)
        rows = []
        for number, action in enumerate(self.current_plan.actions, 1):
            rows.append(
                f"<div style='margin:4px 0'><span style='color:#777b84'>{number:02}</span>&nbsp;&nbsp;"
                f"{html.escape(action.describe())}</div>"
            )
        summary = (
            f"<div style='color:#ffe16b;font-weight:700;margin-bottom:7px'>TASK PREVIEW · "
            f"{folders} folders · {moves} moves · {imports} imports · {trash} trash</div>" + "".join(rows)
        )
        self._set_preview(summary)
        self._configure_plan_risk(self.current_plan)
        self._show_confirmation(True)

    def confirm_plan(self) -> None:
        if self.current_plan is None:
            return
        plan = self.current_plan
        self.current_plan = None
        self._set_busy(True)
        self._show_confirmation(False)
        self._run_background(lambda: self.core.execute(plan), self._execution_ready)

    def _execution_ready(self, result) -> None:
        self._set_busy(False)
        if result.success:
            self._set_preview(
                f"<span style='color:#83e6a8;font-weight:700'>✓ 任務完成</span><br>"
                f"安全執行了 {len(result.completed)} 個操作。你可以隨時按「復原上次」。"
            )
            self.input.clear()
        else:
            errors = "<br>".join(html.escape(error) for error in result.errors)
            self._set_preview(f"<span style='color:#ff7d86;font-weight:700'>執行未完成</span><br>{errors}")
        self._show_confirmation(False)

    def cancel_plan(self) -> None:
        self.current_plan = None
        self.preview.hide()
        self._show_confirmation(False)
        self.set_status(AgentStatus.IDLE)
        self.adjustSize()

    def undo(self) -> None:
        self._set_busy(True)
        self._show_confirmation(False)
        self._run_background(self.core.undo, self._undo_ready)

    def _undo_ready(self, result) -> None:
        self._set_busy(False)
        if result.success:
            self._set_preview(
                f"<span style='color:#83e6a8;font-weight:700'>↶ 已復原</span><br>"
                f"{len(result.completed)} 個檔案已回到原本位置。"
            )
        else:
            self._set_preview(
                f"<span style='color:#9fa0a6'>目前沒有可復原的操作。</span><br>"
                f"{html.escape(' '.join(result.errors))}"
            )
        self._show_confirmation(False)

    def _run_background(self, function, on_result) -> None:
        worker = FunctionWorker(function)
        self._workers.add(worker)
        worker.signals.result.connect(on_result)
        worker.signals.error.connect(self._background_error)
        worker.signals.finished.connect(lambda current=worker: self._workers.discard(current))
        self.thread_pool.start(worker)

    def _background_error(self, message: str) -> None:
        self._set_busy(False)
        self.set_status(AgentStatus.ERROR)
        self._set_preview(f"<b>任務發生錯誤</b><br>{html.escape(message)}")

    def _set_busy(self, busy: bool) -> None:
        self.input.setEnabled(not busy)
        self.send_button.setEnabled(not busy)
        self.confirm_button.setEnabled(not busy)
        for button in self._context_buttons:
            button.setEnabled(not busy)

    def _set_context_actions(self, actions: list[tuple[str, object]]) -> None:
        while self.context_row.count():
            item = self.context_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._context_buttons = []
        for label, callback in actions:
            button = QPushButton(label)
            button.setObjectName("quick")
            button.clicked.connect(lambda _checked=False, function=callback: function())
            self.context_row.addWidget(button)
            self._context_buttons.append(button)
        self.context_row.addStretch()

    def show_history(self) -> None:
        runs = self.core.memory.recent_runs()
        if not runs:
            self._set_preview("<span style='color:#9fa0a6'>目前還沒有執行紀錄。</span>")
            return
        rows = ["<div style='color:#ffe16b;font-weight:700;margin-bottom:6px'>RECENT ACTIVITY</div>"]
        for run in runs:
            icon = "↶" if run["undone"] else ("✓" if run["success"] else "!")
            color = "#9fa0a6" if run["undone"] else ("#83e6a8" if run["success"] else "#ff7d86")
            rows.append(
                f"<div style='margin:6px 0'><span style='color:{color};font-weight:700'>{icon}</span> "
                f"{html.escape(str(run['request']))} "
                f"<span style='color:#777b84'>· {run['action_count']} actions</span></div>"
            )
        self._set_preview("".join(rows))
        self._show_confirmation(False)
        self.set_status(AgentStatus.IDLE)

    def _set_preview(self, markup: str) -> None:
        self.preview.setHtml(
            "<style>body{font-family:-apple-system,BlinkMacSystemFont,'Helvetica Neue';font-size:12px;"
            "color:#e9e9eb;margin:2px;}</style>" + markup
        )
        self.preview.show()
        self.adjustSize()

    def _show_confirmation(self, visible: bool) -> None:
        self.action_summary.setVisible(visible)
        self.cancel_button.setVisible(visible)
        self.confirm_button.setVisible(visible)

    def _configure_plan_risk(self, plan: Plan) -> None:
        is_red = any(action.risk.value == "RED" for action in plan.actions)
        if is_red:
            self.action_summary.setText("RED · 高風險操作")
            self.action_summary.setStyleSheet("color:#ff7d86;font-size:11px;font-weight:800;")
            self.confirm_button.setText("確認移到垃圾桶")
            self.confirm_button.setStyleSheet("background:#ef6670;color:white;")
        else:
            self.action_summary.setText("YELLOW · 需要確認")
            self.action_summary.setStyleSheet("color:#e9c94f;font-size:11px;font-weight:700;")
            self.confirm_button.setText("確認執行  ⚡")
            self.confirm_button.setStyleSheet("")
