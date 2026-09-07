from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, QThreadPool, Signal
from PySide6.QtGui import QColor, QMovie
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget, QMainWindow,
    QPushButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from .mail_connector import AppleMailConnector, MailItem
from .ui import FunctionWorker


CATEGORIES = ("全部", "工作學校", "行程會議", "安全警示", "帳單付款", "物流購物", "社群通知", "電子報廣告", "其他")


class DragoniteMailWindow(QMainWindow):
    return_home = Signal()

    def __init__(self, project_root: Path):
        super().__init__()
        self.project_root = project_root
        self.connector = AppleMailConnector(project_root)
        self.thread_pool = QThreadPool.globalInstance()
        self._workers: set[FunctionWorker] = set()
        self.items: list[MailItem] = []
        self.current_category = "全部"
        self.setWindowTitle("快龍通訊助理")
        self.setMinimumSize(880, 590)
        self.resize(1020, 660)
        self.setCentralWidget(self._build())

    def _build(self) -> QWidget:
        root = QWidget()
        root.setStyleSheet(
            """
            QWidget{background:#10191c;color:#f6f8f8;font-family:-apple-system;}
            QLabel{background:transparent;}
            QFrame#sidebar,QFrame#summary,QFrame#detail{background:#172429;border:1px solid #2c4247;border-radius:16px;}
            QLineEdit{background:#f5f7f6;color:#172226;border:none;border-radius:13px;padding:10px 14px;font-size:13px;}
            QListWidget{background:transparent;border:none;outline:none;font-size:12px;}
            QListWidget::item{padding:9px;border-radius:9px;margin:1px;}
            QListWidget::item:selected{background:#e99047;color:#171f20;font-weight:800;}
            QTreeWidget{background:#132024;border:1px solid #2b4045;border-radius:14px;outline:none;font-size:12px;}
            QTreeWidget::item{padding:8px;border-bottom:1px solid #22353a;}
            QTreeWidget::item:selected{background:#29464b;color:white;}
            QHeaderView::section{background:#1b2d31;color:#91a9ae;border:none;padding:8px;font-weight:700;}
            QPushButton{background:#e99047;color:#182023;border:none;border-radius:11px;padding:10px 16px;font-weight:800;}
            QPushButton:hover{background:#f5aa69;} QPushButton:disabled{background:#34464a;color:#71858a;}
            """
        )
        outer = QHBoxLayout(root)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(14)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(205)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(15, 16, 15, 15)
        avatar = QLabel()
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        movie = QMovie(str(self.project_root / "assets" / "dragonite-animated.gif"))
        if movie.isValid():
            movie.setCacheMode(QMovie.CacheMode.CacheAll)
            movie.setScaledSize(QSize(112, 112))
            avatar.setMovie(movie)
            self.movie = movie
            movie.start()
        else:
            avatar.setText("✉")
            avatar.setStyleSheet("font-size:72px;color:#f4a35f;background:transparent;")
        name = QLabel("快龍")
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name.setStyleSheet("font-size:22px;font-weight:900;color:#f4a35f;")
        role = QLabel("今日 Gmail 分揀員")
        role.setAlignment(Qt.AlignmentFlag.AlignCenter)
        role.setStyleSheet("font-size:11px;color:#91a9ae;")
        self.categories = QListWidget()
        self.categories.addItems(CATEGORIES)
        self.categories.setCurrentRow(0)
        self.categories.currentTextChanged.connect(self.set_category)
        home = QPushButton("← 回 Agent Town")
        home.setStyleSheet("background:#26383d;color:#dce5e6;")
        home.clicked.connect(self.go_home)
        side.addWidget(avatar)
        side.addWidget(name)
        side.addWidget(role)
        side.addSpacing(12)
        side.addWidget(self.categories, 1)
        side.addWidget(home)

        main = QVBoxLayout()
        header = QHBoxLayout()
        heading_box = QVBoxLayout()
        heading = QLabel("今日信件")
        heading.setStyleSheet("font-size:25px;font-weight:900;")
        self.subtitle = QLabel("尚未同步 · 唯讀模式")
        self.subtitle.setStyleSheet("font-size:11px;color:#83c5b6;")
        heading_box.addWidget(heading)
        heading_box.addWidget(self.subtitle)
        self.search = QLineEdit()
        self.search.setPlaceholderText("搜尋寄件人或主旨…")
        self.search.setFixedWidth(250)
        self.search.textChanged.connect(self.apply_filters)
        self.sync_button = QPushButton("同步今天")
        self.sync_button.clicked.connect(self.sync_today)
        header.addLayout(heading_box)
        header.addStretch()
        header.addWidget(self.search)
        header.addWidget(self.sync_button)
        main.addLayout(header)

        self.summary = QFrame()
        self.summary.setObjectName("summary")
        self.summary_layout = QHBoxLayout(self.summary)
        self.summary_layout.setContentsMargins(13, 10, 13, 10)
        self._render_summary({})
        main.addWidget(self.summary)

        self.mail_list = QTreeWidget()
        self.mail_list.setColumnCount(4)
        self.mail_list.setHeaderLabels(("狀態", "分類", "寄件人", "主旨"))
        self.mail_list.setColumnWidth(0, 58)
        self.mail_list.setColumnWidth(1, 90)
        self.mail_list.setColumnWidth(2, 180)
        self.mail_list.itemSelectionChanged.connect(self.show_selected)
        main.addWidget(self.mail_list, 1)

        detail = QFrame()
        detail.setObjectName("detail")
        detail_layout = QVBoxLayout(detail)
        detail_layout.setContentsMargins(14, 10, 14, 10)
        self.detail = QLabel("同步後選擇一封信查看摘要資訊。")
        self.detail.setWordWrap(True)
        self.detail.setStyleSheet("font-size:12px;color:#c9d5d7;")
        privacy = QLabel("🔒 目前只讀取今天的寄件人、主旨與狀態；不讀附件、不寄信、不刪信。")
        privacy.setStyleSheet("font-size:10px;color:#7fa199;")
        detail_layout.addWidget(self.detail)
        detail_layout.addWidget(privacy)
        main.addWidget(detail)
        outer.addWidget(sidebar)
        outer.addLayout(main, 1)
        return root

    def sync_today(self) -> None:
        self.sync_button.setEnabled(False)
        self.sync_button.setText("同步中…")
        self.subtitle.setText("正在透過 macOS Mail 讀取今天的信件…")
        self.movie.setSpeed(210)
        worker = FunctionWorker(self.connector.fetch_today)
        self._workers.add(worker)
        worker.signals.result.connect(self._sync_ready)
        worker.signals.error.connect(self._sync_error)
        worker.signals.finished.connect(lambda current=worker: self._workers.discard(current))
        self.thread_pool.start(worker)

    def _sync_ready(self, items: list[MailItem]) -> None:
        self.items = items
        self.sync_button.setEnabled(True)
        self.sync_button.setText("重新同步")
        unread = sum(item.unread for item in items)
        self.subtitle.setText(f"今天共 {len(items)} 封 · {unread} 封未讀 · 唯讀模式")
        self.movie.setSpeed(115)
        self._render_summary(self.connector.summary(items))
        self.apply_filters()

    def _sync_error(self, message: str) -> None:
        self.sync_button.setEnabled(True)
        self.sync_button.setText("重試同步")
        self.subtitle.setText("同步失敗")
        self.detail.setText(message)
        self.movie.setSpeed(65)

    def _render_summary(self, summary: dict[str, int]) -> None:
        while self.summary_layout.count():
            item = self.summary_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        total = sum(summary.values())
        entries = [("全部", total), *sorted(summary.items(), key=lambda item: item[1], reverse=True)[:4]]
        if not total:
            entries = [("尚未同步", 0)]
        for category, count in entries:
            label = QLabel(f"<b style='font-size:18px;color:#f4a35f'>{count}</b><br><span style='color:#91a9ae'>{category}</span>")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.summary_layout.addWidget(label)
        self.summary_layout.addStretch()

    def set_category(self, category: str) -> None:
        self.current_category = category
        self.apply_filters()

    def apply_filters(self) -> None:
        query = self.search.text().strip().lower()
        self.mail_list.clear()
        for item in self.items:
            if self.current_category != "全部" and item.category != self.current_category:
                continue
            if query and query not in f"{item.sender} {item.subject}".lower():
                continue
            status = "★" if item.flagged else ("●" if item.unread else "")
            row = QTreeWidgetItem((status, item.category, self.connector.sender_name(item.sender), item.subject))
            row.setData(0, Qt.ItemDataRole.UserRole, item)
            if item.unread:
                row.setForeground(0, QColor("#f4a35f"))
            self.mail_list.addTopLevelItem(row)

    def show_selected(self) -> None:
        selected = self.mail_list.selectedItems()
        if not selected:
            return
        item: MailItem = selected[0].data(0, Qt.ItemDataRole.UserRole)
        state = "未讀" if item.unread else "已讀"
        if item.flagged:
            state += " · 已加旗標"
        self.detail.setText(f"{item.subject}\n來自：{item.sender}\n分類：{item.category} · {state}")

    def go_home(self) -> None:
        self.hide()
        self.return_home.emit()

    def closeEvent(self, event) -> None:
        event.ignore()
        self.go_home()
