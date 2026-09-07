from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QLinearGradient, QMouseEvent, QMovie, QPainter, QPixmap
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QMainWindow, QPushButton, QVBoxLayout, QWidget,
)


@dataclass(frozen=True)
class AgentSpec:
    agent_id: str
    name: str
    role: str
    category: str
    abilities: tuple[str, ...]
    available: bool = False
    emoji: str = "?"


AGENTS = (
    AgentSpec("pikachu", "皮卡丘", "桌面與圖片助理", "日常小屋", ("檔案整理", "截圖清理", "圖片 OCR", "安全復原"), True, "⚡"),
    AgentSpec("bulbasaur", "妙蛙種子", "研究助理", "研究所", ("PDF 摘要", "論文分類", "引用整理"), False, "🌱"),
    AgentSpec("porygon", "多邊獸", "Project 專案管理員", "電腦中心", ("建立專案", "新增檔案", "重新命名", "安全刪除"), True, "⬡"),
    AgentSpec("rotom", "洛托姆", "系統自動化", "發電廠", ("macOS 操作", "排程任務", "App 控制"), False, "ϟ"),
    AgentSpec("dragonite", "快龍", "通訊助理", "郵局", ("今日 Gmail", "信件分類", "重要信件"), True, "✉"),
    AgentSpec("meloetta", "美洛耶塔", "YouTube Music 助理", "音樂館", ("播放控制", "找歌", "情境音樂", "系統音量"), True, "♫"),
    AgentSpec("snorlax", "卡比獸", "儲存助理", "倉庫", ("備份", "封存", "磁碟清理"), False, "◼"),
)


class TownBackdrop(QWidget):
    def __init__(self, background: Path):
        super().__init__()
        self.background = QPixmap(str(background))

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        if not self.background.isNull():
            scaled = self.background.scaled(
                self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            source_x = max(0, (scaled.width() - self.width()) // 2)
            source_y = max(0, (scaled.height() - self.height()) // 2)
            painter.drawPixmap(0, 0, scaled, source_x, source_y, self.width(), self.height())
        shade = QLinearGradient(0, 0, self.width(), self.height())
        shade.setColorAt(0, QColor(10, 24, 20, 110))
        shade.setColorAt(0.52, QColor(12, 26, 21, 38))
        shade.setColorAt(1, QColor(9, 20, 18, 80))
        painter.fillRect(self.rect(), shade)


class AgentCard(QFrame):
    selected = Signal(object)
    launched = Signal(object)

    def __init__(self, spec: AgentSpec, assets: Path):
        super().__init__()
        self.spec = spec
        self.setObjectName("agentCard")
        self.setProperty("selected", False)
        self.setProperty("available", spec.available)
        self.setFixedSize(164, 180)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 11)
        layout.setSpacing(4)

        self.art = QLabel()
        self.art.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.art.setFixedHeight(104)
        animated_asset = assets / f"{spec.agent_id}-animated.gif"
        if animated_asset.exists():
            movie = QMovie(str(animated_asset))
            movie.setCacheMode(QMovie.CacheMode.CacheAll)
            movie.setScaledSize(QSize(96, 96))
            self.art.setMovie(movie)
            self.movie = movie
            movie.start()
        else:
            self.art.setText(spec.emoji)
            self.art.setStyleSheet("font-size:46px;color:rgba(255,255,255,145);background:transparent;")

        name = QLabel(spec.name)
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name.setStyleSheet("font-size:15px;font-weight:800;color:white;background:transparent;")
        role = QLabel(spec.role if spec.available else f"{spec.role}  ·  尚未入住")
        role.setAlignment(Qt.AlignmentFlag.AlignCenter)
        role.setStyleSheet("font-size:10px;color:rgba(255,255,255,190);background:transparent;")
        layout.addWidget(self.art)
        layout.addWidget(name)
        layout.addWidget(role)

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.selected.emit(self.spec)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.launched.emit(self.spec)
        super().mouseDoubleClickEvent(event)


class AgentTownWindow(QMainWindow):
    summon_requested = Signal(str)

    def __init__(self, project_root: Path):
        super().__init__()
        self.project_root = project_root
        self.cards: list[AgentCard] = []
        self.current_category = "全部助理"
        self.setWindowTitle("Agent Town")
        self.setMinimumSize(900, 620)
        self.resize(1080, 720)
        self.setCentralWidget(self._build())

    def _build(self) -> QWidget:
        root = TownBackdrop(self.project_root / "assets" / "agent-town-v2.png")
        root.setStyleSheet(
            """
            QFrame#glass{background:rgba(12,22,20,205);border:1px solid rgba(255,255,255,58);border-radius:18px;}
            QFrame#agentCard{background:rgba(14,25,22,202);border:1px solid rgba(255,255,255,70);border-radius:17px;}
            QFrame#agentCard:hover{background:rgba(24,43,35,225);border:2px solid rgba(255,226,91,210);}
            QFrame#agentCard[selected="true"]{background:rgba(28,48,39,235);border:3px solid #ffe15b;}
            QFrame#agentCard[available="false"]{background:rgba(20,28,26,170);border:1px solid rgba(255,255,255,38);}
            QLineEdit{background:rgba(255,255,255,238);color:#1c2822;border:none;border-radius:15px;padding:10px 15px;font-size:13px;}
            QListWidget{background:transparent;color:white;border:none;font-size:13px;outline:none;}
            QListWidget::item{padding:10px 12px;border-radius:10px;margin:2px;}
            QListWidget::item:selected{background:rgba(255,225,91,215);color:#1b281f;font-weight:800;}
            QPushButton{background:#ffe15b;color:#172119;border:none;border-radius:12px;padding:10px 18px;font-weight:800;}
            QPushButton:disabled{background:rgba(255,255,255,25);color:rgba(255,255,255,100);}
            """
        )
        outer = QHBoxLayout(root)
        outer.setContentsMargins(22, 22, 22, 22)
        outer.setSpacing(16)

        sidebar = QFrame()
        sidebar.setObjectName("glass")
        sidebar.setFixedWidth(196)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(15, 20, 15, 16)
        title = QLabel("AGENT TOWN")
        title.setStyleSheet("color:#ffe15b;font-size:16px;font-weight:900;letter-spacing:2px;")
        subtitle = QLabel("你的智慧夥伴城鎮")
        subtitle.setStyleSheet("color:rgba(255,255,255,175);font-size:11px;")
        self.categories = QListWidget()
        for category in ("全部助理", "日常小屋", "研究所", "電腦中心", "發電廠", "郵局", "音樂館", "倉庫"):
            self.categories.addItem(category)
        self.categories.setCurrentRow(0)
        self.categories.currentTextChanged.connect(self.filter_category)
        hint = QLabel("雙擊助理即可召喚\n右鍵皮卡丘可以回城")
        hint.setWordWrap(True)
        hint.setStyleSheet("color:rgba(255,255,255,145);font-size:10px;line-height:1.5;")
        side.addWidget(title)
        side.addWidget(subtitle)
        side.addSpacing(14)
        side.addWidget(self.categories)
        side.addWidget(hint)

        content = QFrame()
        content.setObjectName("glass")
        body = QVBoxLayout(content)
        body.setContentsMargins(20, 18, 20, 17)
        body.setSpacing(13)
        top = QHBoxLayout()
        heading = QLabel("所有智慧助理")
        heading.setStyleSheet("color:white;font-size:21px;font-weight:850;")
        self.search = QLineEdit()
        self.search.setPlaceholderText("搜尋助理或能力…")
        self.search.setFixedWidth(250)
        self.search.textChanged.connect(self.apply_filters)
        top.addWidget(heading)
        top.addStretch()
        top.addWidget(self.search)
        body.addLayout(top)

        self.grid = QGridLayout()
        self.grid.setHorizontalSpacing(13)
        self.grid.setVerticalSpacing(13)
        self.grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        for index, spec in enumerate(AGENTS):
            card = AgentCard(spec, self.project_root / "assets")
            card.selected.connect(self.select_agent)
            card.launched.connect(self.launch_agent)
            self.cards.append(card)
            self.grid.addWidget(card, index // 3, index % 3)
        body.addLayout(self.grid, 1)

        details = QFrame()
        details.setObjectName("glass")
        detail_layout = QHBoxLayout(details)
        detail_layout.setContentsMargins(15, 11, 13, 11)
        self.detail_text = QLabel("選擇一位助理查看能力")
        self.detail_text.setStyleSheet("color:white;font-size:12px;")
        self.detail_text.setWordWrap(True)
        self.launch_button = QPushButton("召喚")
        self.launch_button.setEnabled(False)
        self.launch_button.clicked.connect(self.launch_selected)
        detail_layout.addWidget(self.detail_text, 1)
        detail_layout.addWidget(self.launch_button)
        body.addWidget(details)
        outer.addWidget(sidebar)
        outer.addWidget(content, 1)
        return root

    def filter_category(self, category: str) -> None:
        self.current_category = category
        self.apply_filters()

    def apply_filters(self) -> None:
        query = self.search.text().strip().lower()
        for card in self.cards:
            spec = card.spec
            searchable = " ".join((spec.name, spec.role, spec.category, *spec.abilities)).lower()
            category_match = self.current_category == "全部助理" or spec.category == self.current_category
            card.setVisible(category_match and (not query or query in searchable))

    def select_agent(self, spec: AgentSpec) -> None:
        for card in self.cards:
            card.set_selected(card.spec.agent_id == spec.agent_id)
        abilities = " · ".join(spec.abilities)
        state = "已入住" if spec.available else "建造中"
        self.detail_text.setText(f"{spec.name}｜{spec.role}\n{abilities}　·　{state}")
        self.launch_button.setEnabled(spec.available)
        self.launch_button.setProperty("agent_id", spec.agent_id)
        self.launch_button.setText("召喚" if spec.available else "尚未入住")

    def launch_agent(self, spec: AgentSpec) -> None:
        if spec.available:
            self.summon_requested.emit(spec.agent_id)
        else:
            self.select_agent(spec)

    def launch_selected(self) -> None:
        agent_id = self.launch_button.property("agent_id")
        if agent_id:
            self.summon_requested.emit(str(agent_id))

    def closeEvent(self, event) -> None:
        event.ignore()
        self.hide()
