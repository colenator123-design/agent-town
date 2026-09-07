from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse


@dataclass(frozen=True)
class PinnedPlaylist:
    row_id: int
    name: str
    url: str


@dataclass(frozen=True)
class SavedTrack:
    row_id: int
    title: str
    artist: str
    album: str


class MusicMemory:
    def __init__(self, database: Path):
        database.parent.mkdir(parents=True, exist_ok=True)
        self.database = database
        self._initialize()

    def _initialize(self) -> None:
        with sqlite3.connect(self.database) as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS music_playlists(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    url TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS saved_tracks(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    artist TEXT NOT NULL,
                    album TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    UNIQUE(title, artist)
                );
                """
            )

    def add_playlist(self, name: str, url: str) -> PinnedPlaylist:
        clean_name = name.strip()
        clean_url = url.strip()
        if not clean_name:
            raise ValueError("歌單名稱不能是空白")
        parsed = urlparse(clean_url)
        allowed_hosts = {"music.youtube.com", "youtube.com", "www.youtube.com", "youtu.be"}
        if parsed.scheme != "https" or parsed.hostname not in allowed_hosts:
            raise ValueError("請貼上有效的 YouTube Music 或 YouTube 網址")
        if parsed.hostname != "youtu.be" and not (parse_qs(parsed.query).get("list") or parsed.path.startswith("/playlist")):
            raise ValueError("這個網址看起來不是播放清單")
        timestamp = datetime.now(timezone.utc).isoformat()
        try:
            with sqlite3.connect(self.database) as connection:
                cursor = connection.execute(
                    "INSERT INTO music_playlists(name, url, created_at) VALUES (?, ?, ?)",
                    (clean_name, clean_url, timestamp),
                )
                row_id = int(cursor.lastrowid)
        except sqlite3.IntegrityError as error:
            raise ValueError("這個歌單已經加入過了") from error
        return PinnedPlaylist(row_id, clean_name, clean_url)

    def playlists(self) -> list[PinnedPlaylist]:
        with sqlite3.connect(self.database) as connection:
            rows = connection.execute("SELECT id, name, url FROM music_playlists ORDER BY id DESC").fetchall()
        return [PinnedPlaylist(int(row[0]), str(row[1]), str(row[2])) for row in rows]

    def delete_playlist(self, row_id: int) -> None:
        with sqlite3.connect(self.database) as connection:
            connection.execute("DELETE FROM music_playlists WHERE id = ?", (row_id,))

    def save_track(self, title: str, artist: str, album: str = "") -> SavedTrack:
        clean_title = title.strip()
        clean_artist = artist.strip()
        if not clean_title or clean_title == "尚未播放":
            raise ValueError("目前沒有可以儲存的歌曲")
        timestamp = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.database) as connection:
            connection.execute(
                """INSERT INTO saved_tracks(title, artist, album, created_at) VALUES (?, ?, ?, ?)
                   ON CONFLICT(title, artist) DO UPDATE SET album=excluded.album, created_at=excluded.created_at""",
                (clean_title, clean_artist, album.strip(), timestamp),
            )
            row = connection.execute(
                "SELECT id, title, artist, album FROM saved_tracks WHERE title = ? AND artist = ?",
                (clean_title, clean_artist),
            ).fetchone()
        assert row is not None
        return SavedTrack(int(row[0]), str(row[1]), str(row[2]), str(row[3]))

    def saved_tracks(self) -> list[SavedTrack]:
        with sqlite3.connect(self.database) as connection:
            rows = connection.execute(
                "SELECT id, title, artist, album FROM saved_tracks ORDER BY created_at DESC"
            ).fetchall()
        return [SavedTrack(int(row[0]), str(row[1]), str(row[2]), str(row[3])) for row in rows]

    def delete_track(self, row_id: int) -> None:
        with sqlite3.connect(self.database) as connection:
            connection.execute("DELETE FROM saved_tracks WHERE id = ?", (row_id,))
