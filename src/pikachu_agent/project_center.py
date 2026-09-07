from __future__ import annotations

import subprocess
from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QMovie
from PySide6.QtWidgets import (
    QAbstractItemView, QFrame, QHBoxLayout, QInputDialog, QLabel, QListWidget,
    QListWidgetItem, QMainWindow, QMessageBox, QPushButton, QStyle, QVBoxLayout, QWidget,
)

from .project_tools import ProjectTools
from .safety import SafetyError


class ProjectCenterWindow(QMainWindow):
    return_home = Signal()

    def __init__(self, project_root: Path, storage_root: Path | None = None):
        super().__init__()
        self.project_root = project_root
        self.tools = ProjectTools(storage_root or Path.home() / "Project")
        self.current = self.tools.root
        self.setWindowTitle("多邊獸｜Project 專案中心")
        self.setMinimumSize(900, 620)
        self.resize(1060, 720)
        self.setCentralWidget(self._build())
        self.refresh()

    def _build(self) -> QWidget:
        root = QWidget()
        root.setStyleSheet(
            """
            QWidget{background:#edf0f7;color:#20283a;font-family:-apple-system;}
            QFrame#sidebar{background:#202846;border-radius:18px;}
            QFrame#toolbar,QFrame#content{background:white;border:1px solid #d9deeb;border-radius:16px;}
            QLabel#title{font-size:23px;font-weight:900;color:white;background:transparent;}
            QLabel#muted{font-size:11px;color:#aeb9d8;background:transparent;}
            QLabel#path{font-size:13px;font-weight:700;color:#3b4561;background:transparent;}
            QPushButton{background:#5368e8;color:white;border:none;border-radius:10px;padding:9px 13px;font-weight:750;}
            QPushButton:hover{background:#4056dc;}
            QPushButton#secondary{background:#e8ebf6;color:#34405c;}
            QPushButton#danger{background:#fee8e8;color:#a12c36;}
            QListWidget{background:transparent;border:none;outline:none;font-size:13px;}
            QListWidget::item{background:#f8f9fc;border:1px solid #e2e6f0;border-radius:11px;padding:11px;margin:3px;}
            QListWidget::item:selected{background:#e2e7ff;border:2px solid #6478ee;color:#1f2f76;}
            """
        )
        outer = QHBoxLayout(root)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(14)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(228)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(18, 20, 18, 18)
        art = QLabel()
        art.setAlignment(Qt.AlignmentFlag.AlignCenter)
        movie_path = self.project_root / "assets" / "porygon-animated.gif"
        if movie_path.exists():
            self.movie = QMovie(str(movie_path))
            self.movie.setCacheMode(QMovie.CacheMode.CacheAll)
            self.movie.setScaledSize(QSize(112, 112))
            art.setMovie(self.movie)
            self.movie.start()
        else:
            art.setText("⬡")
            art.setStyleSheet("font-size:72px;color:#8fa0ff;background:transparent;")
        title = QLabel("多邊獸")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        role = QLabel("PROJECT 管理員")
        role.setObjectName("muted")
        role.setAlignment(Qt.AlignmentFlag.AlignCenter)
        help_text = QLabel("所有操作只限於：\n~/Project\n\n刪除會移到垃圾桶，\n不會永久清除。")
        help_text.setObjectName("muted")
        help_text.setWordWrap(True)
        back = QPushButton("← 回到城鎮")
        back.setObjectName("secondary")
        back.clicked.connect(self.return_home.emit)
        side.addWidget(art)
        side.addWidget(title)
        side.addWidget(role)
        side.addSpacing(22)
        side.addWidget(help_text)
        side.addStretch()
        side.addWidget(back)

        main = QVBoxLayout()
        main.setSpacing(12)
        toolbar = QFrame()
        toolbar.setObjectName("toolbar")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(14, 12, 14, 12)
        up = QPushButton("↑ 上一層")
        up.setObjectName("secondary")
        up.clicked.connect(self.go_up)
        folder = QPushButton("＋ 新增資料夾")
        folder.clicked.connect(self.new_folder)
        file_button = QPushButton("＋ 新增文字檔")
        file_button.clicked.connect(self.new_file)
        finder = QPushButton("在 Finder 打開")
        finder.setObjectName("secondary")
        finder.clicked.connect(self.open_finder)
        terminal = QPushButton("Terminal")
        terminal.setObjectName("secondary")
        terminal.clicked.connect(self.open_terminal)
        toolbar_layout.addWidget(up)
        toolbar_layout.addWidget(folder)
        toolbar_layout.addWidget(file_button)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(finder)
        toolbar_layout.addWidget(terminal)

        content = QFrame()
        content.setObjectName("content")
        body = QVBoxLayout(content)
        body.setContentsMargins(16, 15, 16, 14)
        self.path_label = QLabel()
        self.path_label.setObjectName("path")
        self.items = QListWidget()
        self.items.setViewMode(QListWidget.ViewMode.IconMode)
        self.items.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.items.setMovement(QListWidget.Movement.Static)
        self.items.setIconSize(QSize(52, 52))
        self.items.setGridSize(QSize(146, 106))
        self.items.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.items.itemDoubleClicked.connect(self.open_item)
        self.items.itemSelectionChanged.connect(self.update_actions)
        hint = QLabel("雙擊資料夾進入；雙擊檔案用預設 App 開啟")
        hint.setStyleSheet("color:#7e879d;font-size:11px;")
        actions = QHBoxLayout()
        self.rename_button = QPushButton("重新命名")
        self.rename_button.setObjectName("secondary")
        self.rename_button.clicked.connect(self.rename_selected)
        self.trash_button = QPushButton("移到垃圾桶")
        self.trash_button.setObjectName("danger")
        self.trash_button.clicked.connect(self.trash_selected)
        actions.addWidget(hint)
        actions.addStretch()
        actions.addWidget(self.rename_button)
        actions.addWidget(self.trash_button)
        body.addWidget(self.path_label)
        body.addWidget(self.items, 1)
        body.addLayout(actions)
        main.addWidget(toolbar)
        main.addWidget(content, 1)
        outer.addWidget(sidebar)
        outer.addLayout(main, 1)
        return root

    def refresh(self, select_path: Path | None = None) -> None:
        self.items.clear()
        relative = self.tools.relative(self.current)
        self.path_label.setText("Project" if str(relative) == "." else f"Project / {relative}")
        folder_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon)
        file_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon)
        for path in self.tools.children(self.current):
            item = QListWidgetItem(folder_icon if path.is_dir() else file_icon, path.name)
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            item.setToolTip(str(path))
            self.items.addItem(item)
            if select_path and path == select_path:
                item.setSelected(True)
        self.update_actions()

    def selected_path(self) -> Path | None:
        selected = self.items.selectedItems()
        return Path(selected[0].data(Qt.ItemDataRole.UserRole)) if selected else None

    def update_actions(self) -> None:
        enabled = self.selected_path() is not None
        self.rename_button.setEnabled(enabled)
        self.trash_button.setEnabled(enabled)

    def open_item(self, item: QListWidgetItem) -> None:
        path = Path(item.data(Qt.ItemDataRole.UserRole))
        if path.is_dir():
            self.current = self.tools.resolve(path)
            self.refresh()
        else:
            subprocess.Popen(["open", str(path)])

    def go_up(self) -> None:
        if self.current != self.tools.root:
            previous = self.current
            self.current = self.current.parent
            self.refresh(previous)

    def new_folder(self) -> None:
        name, accepted = QInputDialog.getText(self, "新增資料夾", "資料夾名稱：")
        if accepted:
            self._run(lambda: self.tools.create_folder(self.current, name))

    def new_file(self) -> None:
        name, accepted = QInputDialog.getText(self, "新增文字檔", "檔案名稱：", text="筆記.md")
        if accepted:
            self._run(lambda: self.tools.create_text_file(self.current, name))

    def rename_selected(self) -> None:
        path = self.selected_path()
        if not path:
            return
        name, accepted = QInputDialog.getText(self, "重新命名", "新名稱：", text=path.name)
        if accepted and name != path.name:
            self._run(lambda: self.tools.rename(path, name))

    def trash_selected(self) -> None:
        path = self.selected_path()
        if not path:
            return
        kind = "資料夾及裡面的全部內容" if path.is_dir() else "檔案"
        answer = QMessageBox.warning(
            self, "確認移到垃圾桶",
            f"要把「{path.name}」{kind}移到垃圾桶嗎？\n之後仍可從垃圾桶復原。",
            QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes,
            QMessageBox.StandardButton.Cancel,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._run(lambda: self.tools.trash(path))

    def open_finder(self) -> None:
        subprocess.Popen(["open", str(self.current)])

    def open_terminal(self) -> None:
        subprocess.Popen(["open", "-a", "Terminal", str(self.current)])

    def _run(self, operation) -> None:
        try:
            result = operation()
            self.refresh(result if isinstance(result, Path) else None)
        except (SafetyError, OSError) as error:
            QMessageBox.critical(self, "多邊獸無法執行", str(error))

    def closeEvent(self, event) -> None:
        event.ignore()
        self.hide()
