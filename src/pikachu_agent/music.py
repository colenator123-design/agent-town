from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, QThreadPool, QTimer, Signal
from PySide6.QtGui import QMovie
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget,
    QMainWindow, QMessageBox, QPushButton, QSlider, QTabWidget, QVBoxLayout, QWidget,
)

from .music_connector import SongResult, YouTubeMusicConnector, parse_music_command
from .music_memory import MusicMemory, PinnedPlaylist, SavedTrack
from .ui import FunctionWorker


class MeloettaMusicWindow(QMainWindow):
    return_home = Signal()

    def __init__(self, project_root: Path):
        super().__init__()
        self.project_root = project_root
        self.connector = YouTubeMusicConnector()
        self.memory = MusicMemory(project_root / "data" / "music.sqlite3")
        self.thread_pool = QThreadPool.globalInstance()
        self._status_worker: FunctionWorker | None = None
        self._control_worker: FunctionWorker | None = None
        self._search_worker: FunctionWorker | None = None
        self.search_results: list[SongResult] = []
        self._duration = 0.0
        self.current_info = None
        self._mini = False
        self.playlist_rows: list[PinnedPlaylist] = []
        self.saved_rows: list[SavedTrack] = []
        self.setWindowTitle("美洛耶塔｜YouTube Music 助理")
        self.setMinimumSize(900, 650)
        self.resize(1040, 760)
        self.setCentralWidget(self._build())
        self.timer = QTimer(self)
        self.timer.setInterval(4000)
        self.timer.timeout.connect(self.refresh_status)
        self.sleep_timer = QTimer(self)
        self.sleep_timer.setSingleShot(True)
        self.sleep_timer.timeout.connect(lambda: self.control("pause"))

    def _build(self) -> QWidget:
        root = QWidget()
        root.setStyleSheet(
            """
            QWidget{background:#15121d;color:white;font-family:-apple-system;}
            QFrame#side{background:#271b36;border-radius:20px;}
            QFrame#panel{background:#211b2b;border:1px solid #493a5b;border-radius:18px;}
            QLabel#title{font-size:24px;font-weight:900;background:transparent;}
            QLabel#song{font-size:24px;font-weight:850;background:transparent;}
            QLabel#muted{color:#b7a9c7;font-size:12px;background:transparent;}
            QPushButton{background:#d74b7c;color:white;border:none;border-radius:12px;padding:10px 15px;font-weight:800;}
            QPushButton:hover{background:#ec5e91;}
            QPushButton#round{border-radius:25px;font-size:20px;min-width:50px;min-height:50px;}
            QPushButton#secondary{background:#3b3048;color:#eadff4;}
            QLineEdit{background:#30263c;border:1px solid #59476a;border-radius:13px;padding:11px;color:white;font-size:13px;}
            QListWidget{background:#191520;border:1px solid #493a5b;border-radius:12px;outline:none;}
            QListWidget::item{padding:8px;border-bottom:1px solid #30263c;}
            QListWidget::item:selected{background:#583650;color:white;}
            QComboBox{background:#30263c;border:1px solid #59476a;border-radius:10px;padding:8px;color:white;}
            QTabWidget::pane{border:none;background:transparent;}
            QTabBar::tab{background:#30263c;color:#c8bcd4;padding:9px 17px;border-radius:9px;margin-right:5px;}
            QTabBar::tab:selected{background:#d74b7c;color:white;font-weight:800;}
            QSlider::groove:horizontal{height:5px;background:#44364f;border-radius:2px;}
            QSlider::handle:horizontal{width:16px;margin:-6px 0;background:#e55a8b;border-radius:8px;}
            """
        )
        outer = QHBoxLayout(root)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(14)

        self.side_frame = QFrame()
        self.side_frame.setObjectName("side")
        self.side_frame.setFixedWidth(230)
        side = QVBoxLayout(self.side_frame)
        side.setContentsMargins(18, 20, 18, 18)
        art = QLabel()
        art.setAlignment(Qt.AlignmentFlag.AlignCenter)
        movie_path = self.project_root / "assets" / "meloetta-animated.gif"
        if movie_path.exists():
            self.movie = QMovie(str(movie_path))
            self.movie.setCacheMode(QMovie.CacheMode.CacheAll)
            self.movie.setScaledSize(QSize(128, 128))
            art.setMovie(self.movie)
            self.movie.start()
        else:
            art.setText("♫")
            art.setStyleSheet("font-size:80px;color:#e55a8b;background:transparent;")
        name = QLabel("美洛耶塔")
        name.setObjectName("title")
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        role = QLabel("YOUTUBE MUSIC 助理")
        role.setObjectName("muted")
        role.setAlignment(Qt.AlignmentFlag.AlignCenter)
        open_button = QPushButton("開啟 YouTube Music")
        open_button.clicked.connect(lambda: self.connector.open())
        back = QPushButton("← 回到城鎮")
        back.setObjectName("secondary")
        back.clicked.connect(self.return_home.emit)
        side.addWidget(art)
        side.addWidget(name)
        side.addWidget(role)
        side.addSpacing(24)
        side.addWidget(open_button)
        side.addStretch()
        side.addWidget(back)

        main = QVBoxLayout()
        main.setSpacing(13)
        player = QFrame()
        player.setObjectName("panel")
        player_layout = QVBoxLayout(player)
        player_layout.setContentsMargins(25, 24, 25, 22)
        now = QLabel("NOW PLAYING")
        now.setObjectName("muted")
        player_top = QHBoxLayout()
        player_top.addWidget(now)
        player_top.addStretch()
        self.mini_button = QPushButton("迷你播放器")
        self.mini_button.setObjectName("secondary")
        self.mini_button.clicked.connect(self.toggle_mini)
        player_top.addWidget(self.mini_button)
        self.song = QLabel("尚未播放")
        self.song.setObjectName("song")
        self.song.setWordWrap(True)
        self.artist = QLabel("先在 Safari 開啟 YouTube Music")
        self.artist.setObjectName("muted")
        self.progress = QSlider(Qt.Orientation.Horizontal)
        self.progress.setRange(0, 1000)
        self.progress.sliderReleased.connect(self.seek_from_slider)
        self.time_label = QLabel("0:00 / 0:00")
        self.time_label.setObjectName("muted")
        controls = QHBoxLayout()
        previous = QPushButton("◀◀")
        previous.setObjectName("round")
        previous.clicked.connect(lambda: self.control("previous"))
        self.play_button = QPushButton("▶")
        self.play_button.setObjectName("round")
        self.play_button.clicked.connect(lambda: self.control("togglePlayPause"))
        next_button = QPushButton("▶▶")
        next_button.setObjectName("round")
        next_button.clicked.connect(lambda: self.control("next"))
        controls.addStretch()
        controls.addWidget(previous)
        controls.addWidget(self.play_button)
        controls.addWidget(next_button)
        controls.addStretch()
        volume_row = QHBoxLayout()
        volume_label = QLabel("系統音量")
        volume_label.setObjectName("muted")
        self.volume = QSlider(Qt.Orientation.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setValue(50)
        self.volume.sliderReleased.connect(lambda: self.set_volume(self.volume.value()))
        volume_row.addWidget(volume_label)
        volume_row.addWidget(self.volume, 1)
        player_layout.addLayout(player_top)
        player_layout.addWidget(self.song)
        player_layout.addWidget(self.artist)
        player_layout.addSpacing(8)
        player_layout.addWidget(self.progress)
        player_layout.addWidget(self.time_label, alignment=Qt.AlignmentFlag.AlignRight)
        player_layout.addLayout(controls)
        player_layout.addLayout(volume_row)

        self.assistant = QFrame()
        self.assistant.setObjectName("panel")
        assistant_layout = QVBoxLayout(self.assistant)
        assistant_layout.setContentsMargins(20, 17, 20, 18)
        tabs = QTabWidget()

        search_tab = QWidget()
        search_layout = QVBoxLayout(search_tab)
        search_layout.setContentsMargins(0, 10, 0, 0)
        command_row = QHBoxLayout()
        self.command = QLineEdit()
        self.command.setPlaceholderText("例如：播放告五人的歌、下一首、暫停、音量 30")
        self.command.returnPressed.connect(self.run_command)
        send = QPushButton("執行")
        send.clicked.connect(self.run_command)
        command_row.addWidget(self.command, 1)
        command_row.addWidget(send)
        self.results = QListWidget()
        self.results.setMaximumHeight(150)
        self.results.itemDoubleClicked.connect(lambda _item: self.play_selected())
        result_actions = QHBoxLayout()
        play_result = QPushButton("播放選取歌曲")
        play_result.clicked.connect(lambda: self.play_selected())
        radio_result = QPushButton("相似歌曲電台")
        radio_result.setObjectName("secondary")
        radio_result.clicked.connect(lambda: self.play_selected(radio=True))
        result_actions.addWidget(play_result)
        result_actions.addWidget(radio_result)
        result_actions.addStretch()
        moods = QHBoxLayout()
        for label in ("專注", "放鬆", "運動", "睡前"):
            button = QPushButton(label)
            button.setObjectName("secondary")
            button.clicked.connect(lambda _checked=False, mode=label: self.start_mode(mode))
            moods.addWidget(button)
        mode_label = QLabel("一鍵情境模式")
        mode_label.setObjectName("muted")
        search_layout.addLayout(command_row)
        search_layout.addWidget(self.results)
        search_layout.addLayout(result_actions)
        search_layout.addWidget(mode_label)
        search_layout.addLayout(moods)
        sleep_row = QHBoxLayout()
        self.sleep_choice = QComboBox()
        self.sleep_choice.addItems(("15 分鐘", "30 分鐘", "45 分鐘", "60 分鐘"))
        sleep_button = QPushButton("設定睡眠計時")
        sleep_button.setObjectName("secondary")
        sleep_button.clicked.connect(self.start_sleep_timer)
        self.sleep_state = QLabel("未設定睡眠計時")
        self.sleep_state.setObjectName("muted")
        sleep_row.addWidget(self.sleep_choice)
        sleep_row.addWidget(sleep_button)
        sleep_row.addWidget(self.sleep_state, 1)
        search_layout.addLayout(sleep_row)

        playlist_tab = QWidget()
        playlist_layout = QVBoxLayout(playlist_tab)
        playlist_layout.setContentsMargins(0, 10, 0, 0)
        self.playlists = QListWidget()
        self.playlists.itemDoubleClicked.connect(lambda _item: self.open_playlist())
        playlist_actions = QHBoxLayout()
        add_playlist = QPushButton("＋ 加入歌單網址")
        add_playlist.clicked.connect(self.add_playlist)
        open_playlist = QPushButton("播放歌單")
        open_playlist.clicked.connect(lambda: self.open_playlist())
        delete_playlist = QPushButton("移除捷徑")
        delete_playlist.setObjectName("secondary")
        delete_playlist.clicked.connect(self.delete_playlist)
        playlist_actions.addWidget(add_playlist)
        playlist_actions.addWidget(open_playlist)
        playlist_actions.addWidget(delete_playlist)
        playlist_actions.addStretch()
        playlist_layout.addWidget(self.playlists)
        playlist_layout.addLayout(playlist_actions)

        saved_tab = QWidget()
        saved_layout = QVBoxLayout(saved_tab)
        saved_layout.setContentsMargins(0, 10, 0, 0)
        self.saved = QListWidget()
        self.saved.itemDoubleClicked.connect(lambda _item: self.play_saved())
        saved_actions = QHBoxLayout()
        save_current = QPushButton("♡ 儲存目前歌曲")
        save_current.clicked.connect(self.save_current)
        play_saved = QPushButton("播放選取歌曲")
        play_saved.clicked.connect(lambda: self.play_saved())
        delete_saved = QPushButton("移除")
        delete_saved.setObjectName("secondary")
        delete_saved.clicked.connect(self.delete_saved)
        saved_actions.addWidget(save_current)
        saved_actions.addWidget(play_saved)
        saved_actions.addWidget(delete_saved)
        saved_actions.addStretch()
        saved_layout.addWidget(self.saved)
        saved_layout.addLayout(saved_actions)

        tabs.addTab(search_tab, "找音樂")
        tabs.addTab(playlist_tab, "我的歌單")
        tabs.addTab(saved_tab, "稍後聽")
        assistant_layout.addWidget(tabs)
        main.addWidget(player, 1)
        main.addWidget(self.assistant)
        outer.addWidget(self.side_frame)
        outer.addLayout(main, 1)
        self.refresh_library()
        return root

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.refresh_status()
        self.timer.start()

    def hideEvent(self, event) -> None:
        self.timer.stop()
        super().hideEvent(event)

    def refresh_status(self) -> None:
        if self._status_worker is not None:
            return
        worker = FunctionWorker(self.connector.status)
        self._status_worker = worker
        worker.signals.result.connect(self._apply_status)
        worker.signals.finished.connect(lambda: self._finish_status(worker))
        self.thread_pool.start(worker)

    def _apply_status(self, info) -> None:
        self.current_info = info
        self.song.setText(info.title)
        detail = info.artist + (f"  ·  {info.album}" if info.album else "")
        self.artist.setText(detail)
        self.play_button.setText("❚❚" if info.playing else "▶")
        self._duration = info.duration
        value = int(1000 * info.elapsed / info.duration) if info.duration > 0 else 0
        self.progress.setValue(max(0, min(1000, value)))
        self.time_label.setText(f"{self._clock(info.elapsed)} / {self._clock(info.duration)}")

    def _finish_status(self, worker: FunctionWorker) -> None:
        if self._status_worker is worker:
            self._status_worker = None

    def control(self, action: str) -> None:
        if self._control_worker is not None:
            return
        worker = FunctionWorker(lambda: self.connector.control(action))
        self._control_worker = worker
        worker.signals.error.connect(
            lambda error: QMessageBox.warning(
                self, "目前無法控制", f"{error}\n\n請先在 Safari 的 YouTube Music 播放一首歌。"
            )
        )
        worker.signals.finished.connect(lambda: self._finish_control(worker))
        self.thread_pool.start(worker)

    def _finish_control(self, worker: FunctionWorker) -> None:
        if self._control_worker is worker:
            self._control_worker = None
        self.refresh_status()

    def set_volume(self, value: int) -> None:
        try:
            self.connector.set_volume(value)
        except (OSError, RuntimeError) as error:
            QMessageBox.warning(self, "無法調整音量", str(error))

    def run_command(self) -> None:
        action, value = parse_music_command(self.command.text())
        if action == "search":
            self.search_music(str(value), autoplay=True)
        elif action == "volume":
            self.volume.setValue(int(value))
            self.set_volume(int(value))
        elif action in {"play", "pause", "next", "previous"}:
            self.control(action)
        else:
            QMessageBox.information(self, "可以這樣說", "試試：播放周杰倫、下一首、暫停、繼續、音量 30")
        self.command.clear()

    def search_music(self, query: str, *, autoplay: bool = False, radio: bool = False) -> None:
        if self._search_worker is not None or not query.strip():
            return
        self.results.clear()
        self.results.addItem("正在搜尋 YouTube Music…")
        worker = FunctionWorker(lambda: self.connector.search(query))
        self._search_worker = worker
        worker.signals.result.connect(lambda rows: self._show_results(rows, autoplay, radio))
        worker.signals.error.connect(lambda error: self._search_error(error))
        worker.signals.finished.connect(lambda: self._finish_search(worker))
        self.thread_pool.start(worker)

    def _show_results(self, rows: list[SongResult], autoplay: bool, radio: bool = False) -> None:
        self.search_results = rows
        self.results.clear()
        for song in rows:
            detail = " · ".join(part for part in (song.artist, song.album, song.duration) if part)
            self.results.addItem(f"{song.title}\n{detail}")
        if rows:
            self.results.setCurrentRow(0)
            if autoplay:
                self.connector.play_song(rows[0].video_id, radio=radio)
        else:
            self.results.addItem("找不到歌曲，換個關鍵字試試看")

    def _search_error(self, error: str) -> None:
        self.results.clear()
        self.results.addItem("搜尋失敗，請檢查網路後再試")
        QMessageBox.warning(self, "YouTube Music 搜尋失敗", error)

    def _finish_search(self, worker: FunctionWorker) -> None:
        if self._search_worker is worker:
            self._search_worker = None

    def play_selected(self, *, radio: bool = False) -> None:
        row = self.results.currentRow()
        if 0 <= row < len(self.search_results):
            self.connector.play_song(self.search_results[row].video_id, radio=radio)

    def seek_from_slider(self) -> None:
        if self._duration <= 0 or self._control_worker is not None:
            return
        seconds = self._duration * self.progress.value() / 1000
        worker = FunctionWorker(lambda: self.connector.seek(seconds))
        self._control_worker = worker
        worker.signals.error.connect(lambda error: QMessageBox.warning(self, "無法跳轉", error))
        worker.signals.finished.connect(lambda: self._finish_control(worker))
        self.thread_pool.start(worker)

    def start_sleep_timer(self) -> None:
        minutes = int(self.sleep_choice.currentText().split()[0])
        self.sleep_timer.start(minutes * 60 * 1000)
        self.sleep_state.setText(f"{minutes} 分鐘後自動暫停")

    def start_mode(self, mode: str) -> None:
        modes = {
            "專注": ("lofi hip hop radio beats to study", 30, 50),
            "放鬆": ("chill relaxing music mix", 35, 0),
            "運動": ("workout music mix", 55, 0),
            "睡前": ("sleep music peaceful", 20, 45),
        }
        query, volume, minutes = modes[mode]
        self.volume.setValue(volume)
        self.set_volume(volume)
        if minutes:
            self.sleep_timer.start(minutes * 60 * 1000)
            self.sleep_state.setText(f"{mode}模式 · {minutes} 分鐘後自動暫停")
        else:
            self.sleep_timer.stop()
            self.sleep_state.setText(f"{mode}模式")
        self.search_music(query, autoplay=True, radio=True)

    def refresh_library(self) -> None:
        self.playlist_rows = self.memory.playlists()
        self.playlists.clear()
        for playlist in self.playlist_rows:
            self.playlists.addItem(f"♫  {playlist.name}\n{playlist.url}")
        self.saved_rows = self.memory.saved_tracks()
        self.saved.clear()
        for track in self.saved_rows:
            detail = " · ".join(part for part in (track.artist, track.album) if part)
            self.saved.addItem(f"{track.title}\n{detail}")

    def add_playlist(self) -> None:
        name, accepted = QInputDialog.getText(self, "加入常用歌單", "歌單名稱：")
        if not accepted or not name.strip():
            return
        url, accepted = QInputDialog.getText(self, "加入常用歌單", "貼上 YouTube Music 歌單網址：")
        if not accepted:
            return
        try:
            self.memory.add_playlist(name, url)
            self.refresh_library()
        except ValueError as error:
            QMessageBox.warning(self, "無法加入歌單", str(error))

    def open_playlist(self) -> None:
        row = self.playlists.currentRow()
        if 0 <= row < len(self.playlist_rows):
            self.connector.open_url(self.playlist_rows[row].url)

    def delete_playlist(self) -> None:
        row = self.playlists.currentRow()
        if 0 <= row < len(self.playlist_rows):
            self.memory.delete_playlist(self.playlist_rows[row].row_id)
            self.refresh_library()

    def save_current(self) -> None:
        info = self.current_info
        if info is None:
            QMessageBox.information(self, "尚未取得歌曲", "請先播放一首歌，等歌名顯示後再儲存。")
            return
        try:
            self.memory.save_track(info.title, info.artist, info.album)
            self.refresh_library()
        except ValueError as error:
            QMessageBox.information(self, "無法儲存", str(error))

    def play_saved(self) -> None:
        row = self.saved.currentRow()
        if 0 <= row < len(self.saved_rows):
            track = self.saved_rows[row]
            self.search_music(f"{track.title} {track.artist}", autoplay=True)

    def delete_saved(self) -> None:
        row = self.saved.currentRow()
        if 0 <= row < len(self.saved_rows):
            self.memory.delete_track(self.saved_rows[row].row_id)
            self.refresh_library()

    def toggle_mini(self) -> None:
        self._mini = not self._mini
        self.side_frame.setVisible(not self._mini)
        self.assistant.setVisible(not self._mini)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, self._mini)
        if self._mini:
            self.setMinimumSize(500, 300)
            self.resize(560, 340)
            self.mini_button.setText("展開完整介面")
        else:
            self.setMinimumSize(900, 650)
            self.resize(1040, 760)
            self.mini_button.setText("迷你播放器")
        self.show()

    @staticmethod
    def _clock(seconds: float) -> str:
        value = max(0, int(seconds))
        return f"{value // 60}:{value % 60:02d}"

    def closeEvent(self, event) -> None:
        event.ignore()
        self.hide()
