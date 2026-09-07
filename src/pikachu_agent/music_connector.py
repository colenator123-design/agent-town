from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from urllib.parse import quote_plus


@dataclass(frozen=True)
class NowPlaying:
    title: str = "尚未播放"
    artist: str = "在 Safari 開啟 YouTube Music 後即可控制"
    album: str = ""
    playing: bool = False
    elapsed: float = 0
    duration: float = 0


@dataclass(frozen=True)
class SongResult:
    title: str
    artist: str
    album: str
    duration: str
    video_id: str


def parse_music_command(text: str) -> tuple[str, str | int | None]:
    command = text.strip()
    lowered = command.lower()
    volume = re.search(r"(?:音量|volume)\s*(\d{1,3})", lowered)
    if volume:
        return "volume", min(100, int(volume.group(1)))
    if any(word in lowered for word in ("下一首", "next")):
        return "next", None
    if any(word in lowered for word in ("上一首", "前一首", "previous")):
        return "previous", None
    if any(word in lowered for word in ("暫停", "pause")):
        return "pause", None
    if any(word in lowered for word in ("繼續", "resume")):
        return "play", None
    search = re.search(r"(?:搜尋|找|播放)\s*(.+)", command, re.IGNORECASE)
    if search and search.group(1).strip():
        return "search", search.group(1).strip()
    if lowered in {"播放", "play"}:
        return "play", None
    return "unknown", command


class YouTubeMusicConnector:
    base_url = "https://music.youtube.com"

    def __init__(self):
        self.binary = shutil.which("nowplaying-cli")

    @property
    def available(self) -> bool:
        return self.binary is not None

    def open(self, query: str = "") -> None:
        url = self.base_url
        if query.strip():
            url = f"{url}/search?q={quote_plus(query.strip())}"
        subprocess.Popen(["open", "-a", "Safari", url])

    def search(self, query: str, limit: int = 8) -> list[SongResult]:
        from ytmusicapi import YTMusic

        rows = YTMusic().search(query.strip(), filter="songs", limit=limit)
        results: list[SongResult] = []
        for row in rows:
            video_id = row.get("videoId")
            if not video_id:
                continue
            artists = ", ".join(item.get("name", "") for item in row.get("artists") or [] if item.get("name"))
            album = (row.get("album") or {}).get("name", "")
            results.append(SongResult(
                title=str(row.get("title") or "未知歌曲"),
                artist=artists or "未知演出者",
                album=str(album),
                duration=str(row.get("duration") or ""),
                video_id=str(video_id),
            ))
            if len(results) >= limit:
                break
        return results

    def play_song(self, video_id: str, *, radio: bool = False) -> None:
        suffix = f"&list=RDAMVM{video_id}" if radio else ""
        subprocess.Popen(["open", "-a", "Safari", f"{self.base_url}/watch?v={video_id}{suffix}"])

    @staticmethod
    def open_url(url: str) -> None:
        subprocess.Popen(["open", "-a", "Safari", url])

    def status(self) -> NowPlaying:
        if not self.binary:
            return NowPlaying(artist="缺少 nowplaying-cli，請先安裝")
        result = subprocess.run(
            [self.binary, "get", "--json", "title", "artist", "album", "playbackRate", "duration", "elapsedTime"],
            capture_output=True, text=True, timeout=4, check=False,
        )
        if result.returncode != 0:
            return NowPlaying(artist="目前無法讀取播放狀態")
        try:
            data = json.loads(result.stdout)
        except (json.JSONDecodeError, TypeError):
            return NowPlaying(artist="目前沒有可控制的媒體")
        title = data.get("title")
        if not title:
            return NowPlaying()
        return NowPlaying(
            title=str(title),
            artist=str(data.get("artist") or "未知演出者"),
            album=str(data.get("album") or ""),
            playing=float(data.get("playbackRate") or 0) > 0,
            elapsed=float(data.get("elapsedTime") or 0),
            duration=float(data.get("duration") or 0),
        )

    def control(self, action: str) -> None:
        if action not in {"play", "pause", "togglePlayPause", "next", "previous"}:
            raise ValueError(f"不支援的播放操作：{action}")
        if not self.binary:
            raise RuntimeError("找不到 nowplaying-cli")
        result = subprocess.run([self.binary, action], capture_output=True, text=True, timeout=4, check=False)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "目前沒有可控制的音樂")

    def seek(self, seconds: float) -> None:
        if not self.binary:
            raise RuntimeError("找不到 nowplaying-cli")
        result = subprocess.run(
            [self.binary, "seek", str(max(0, int(seconds)))],
            capture_output=True, text=True, timeout=4, check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "目前無法跳轉播放位置")

    @staticmethod
    def set_volume(value: int) -> None:
        safe_value = max(0, min(100, int(value)))
        subprocess.run(
            ["osascript", "-e", f"set volume output volume {safe_value}"],
            capture_output=True, text=True, timeout=4, check=True,
        )
