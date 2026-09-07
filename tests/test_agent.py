from pathlib import Path
from types import SimpleNamespace
from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

from pikachu_agent.core import AgentCore
from pikachu_agent.ai_planner import AIPlanner
from pikachu_agent.executor import Executor
from pikachu_agent.file_tools import FileTools
from pikachu_agent.memory import MemoryStore
from pikachu_agent.models import ActionKind, RiskLevel
from pikachu_agent.planner import RuleBasedPlanner
from pikachu_agent.image_tools import LocalImageTools
from pikachu_agent.mail_connector import AppleMailConnector, MailItem
from pikachu_agent.project_tools import ProjectTools
from pikachu_agent.music_connector import parse_music_command
from pikachu_agent.music_memory import MusicMemory
from pikachu_agent.safety import SafetyError, WorkspacePolicy


def make_project(tmp_path: Path) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "workspace").mkdir()
    (tmp_path / "data").mkdir()
    return tmp_path


def test_policy_rejects_paths_outside_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    policy = WorkspacePolicy(workspace)
    assert policy.resolve("file.txt") == workspace / "file.txt"
    with pytest.raises(SafetyError):
        policy.resolve("../secret.txt")


def test_planner_previews_type_based_moves(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    (project / "workspace" / "paper.pdf").write_text("paper")
    (project / "workspace" / "photo.jpg").write_text("photo")
    core = AgentCore(project)

    plan = core.plan("圖片放 Images，PDF 放 Documents")

    descriptions = [action.describe() for action in plan.actions]
    assert any("paper.pdf" in line and "Documents" in line for line in descriptions)
    assert any("photo.jpg" in line and "Images" in line for line in descriptions)
    assert (project / "workspace" / "paper.pdf").exists()


def test_execute_and_undo(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    source = project / "workspace" / "paper.pdf"
    source.write_text("paper")
    core = AgentCore(project)
    plan = core.plan("整理檔案")

    result = core.execute(plan)
    assert result.success
    assert not source.exists()
    assert (project / "workspace" / "Documents" / "paper.pdf").exists()

    undo = core.undo()
    assert undo.success
    assert source.exists()
    assert not (project / "workspace" / "Documents" / "paper.pdf").exists()
    history = core.memory.recent_runs()
    assert history[0]["request"] == "整理檔案"
    assert history[0]["action_count"] == 2
    assert history[0]["undone"] is True


def test_executor_requires_confirmation(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    (project / "workspace" / "note.txt").write_text("hello")
    core = AgentCore(project)
    plan = core.planner.create_plan("整理")
    result = core.executor.execute(plan)
    assert not result.success
    assert "確認" in result.errors[0]


def test_recursive_scan_and_collision_numbering(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    nested = project / "workspace" / "incoming"
    nested.mkdir()
    (nested / "photo.jpg").write_text("new")
    destination = project / "workspace" / "Images"
    destination.mkdir()
    (destination / "photo.jpg").write_text("existing")
    core = AgentCore(project)

    plan = core.plan("整理所有檔案")
    move = next(action for action in plan.actions if action.source == Path("incoming/photo.jpg"))
    assert move.destination == Path("Images/photo_2.jpg")


def test_drag_drop_import_is_copied_after_confirmation(tmp_path: Path) -> None:
    project = make_project(tmp_path / "project")
    external = tmp_path / "outside.txt"
    external.write_text("keep me")
    core = AgentCore(project)

    plan = core.plan_import([external])
    assert external.exists()
    assert any(action.kind.value == "import_file" for action in plan.actions)
    result = core.execute(plan)

    assert result.success
    assert external.exists()
    assert (project / "workspace" / "Inbox" / "outside.txt").read_text() == "keep me"


def test_ai_plan_is_schema_bounded_and_still_only_a_preview(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    source = project / "workspace" / "research.pdf"
    source.write_text("paper")

    class FakeResponses:
        def create(self, **kwargs):
            assert kwargs["store"] is False
            assert kwargs["text"]["format"]["type"] == "json_schema"
            return SimpleNamespace(
                output_text='{"moves":[{"source":"research.pdf","folder":"Papers/AI","reason":"paper"}]}'
            )

    fake_client = SimpleNamespace(responses=FakeResponses())
    tools = FileTools(WorkspacePolicy(project / "workspace"))
    planner = AIPlanner(tools, client=fake_client)
    plan = planner.create_plan("把研究文件整理好")

    assert source.exists()
    assert plan.needs_confirmation
    assert plan.actions[-1].destination == Path("Papers/AI/research.pdf")


def test_today_screenshots_require_red_confirmation_and_go_to_trash(tmp_path: Path) -> None:
    project = make_project(tmp_path / "project")
    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    screenshot = desktop / "截圖 2026-09-05.png"
    screenshot.write_text("pixels")
    (desktop / "holiday.png").write_text("not a screenshot")
    trashed: list[str] = []
    tools = FileTools(
        WorkspacePolicy(project / "workspace"),
        external_roots=[desktop],
        trash_callback=trashed.append,
    )
    planner = RuleBasedPlanner(tools)

    plan = planner.create_plan("幫我把今天截圖的檔案刪除")

    assert len(plan.actions) == 1
    assert plan.actions[0].kind is ActionKind.TRASH_FILE
    assert plan.actions[0].risk is RiskLevel.RED
    assert screenshot.exists()
    blocked = Executor(tools, MemoryStore(project / "data" / "test.sqlite3")).execute(plan)
    assert not blocked.success
    assert not trashed

    result = Executor(tools, MemoryStore(project / "data" / "test.sqlite3")).execute(plan, confirmed=True)
    assert result.success
    assert trashed == [str(screenshot.resolve())]


def test_image_inspection_and_ocr_note_plan(tmp_path: Path) -> None:
    from PIL import Image

    project = make_project(tmp_path)
    image_path = tmp_path / "sample.png"
    Image.new("RGB", (320, 180), "white").save(image_path)
    image_tools = LocalImageTools(project)

    info = image_tools.inspect([image_path])[0]
    assert (info.width, info.height, info.format) == (320, 180, "PNG")

    core = AgentCore(project)
    plan = core.plan_note("sample-ocr", "recognized text")
    assert plan.needs_confirmation
    assert plan.actions[-1].kind is ActionKind.WRITE_TEXT
    result = core.execute(plan)
    assert result.success
    assert (project / "workspace" / "Notes" / "sample-ocr.md").read_text() == "recognized text"

    duplicate = tmp_path / "sample-copy.png"
    duplicate.write_bytes(image_path.read_bytes())
    groups = image_tools.find_duplicates([image_path, duplicate])
    assert groups == [[image_path.resolve(), duplicate.resolve()]]


def test_smart_image_import_sanitizes_ocr_filename(tmp_path: Path) -> None:
    project = make_project(tmp_path / "project")
    source = tmp_path / "screen.png"
    source.write_bytes(b"image bytes")
    core = AgentCore(project)

    plan = core.plan_named_import(source, "Project / Status: Ready?")

    assert plan.needs_confirmation
    destination = plan.actions[-1].destination
    assert destination is not None
    assert destination.parent == Path("Images")
    assert "/" not in destination.name and ":" not in destination.name


@pytest.mark.parametrize(
    ("subject", "category"),
    [
        ("Security alert: new login", "安全警示"),
        ("Your payment receipt", "帳單付款"),
        ("Meeting invitation for tomorrow", "行程會議"),
        ("Your order has shipped", "物流購物"),
        ("Weekly newsletter - unsubscribe", "電子報廣告"),
        ("Research project deadline", "工作學校"),
    ],
)
def test_mail_classifier(subject: str, category: str) -> None:
    item = MailItem("sender@example.com", subject, True, False)
    classified = AppleMailConnector.classify(item)
    assert classified.category == category


def test_memory_prunes_records_older_than_seven_days(tmp_path: Path) -> None:
    database = tmp_path / "memory.sqlite3"
    memory = MemoryStore(database, retention_days=7)
    old_timestamp = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
    recent_timestamp = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO runs(created_at, request, success, actions_json) VALUES (?, ?, 1, '[]')",
            (old_timestamp, "old"),
        )
        connection.execute(
            "INSERT INTO runs(created_at, request, success, actions_json) VALUES (?, ?, 1, '[]')",
            (recent_timestamp, "recent"),
        )

    assert memory.prune() == 1
    assert [row["request"] for row in memory.recent_runs()] == ["recent"]


def test_project_tools_create_rename_and_trash(tmp_path: Path) -> None:
    trashed: list[str] = []
    tools = ProjectTools(tmp_path / "Project", trash_callback=trashed.append)

    project = tools.create_folder(".", "我的網站")
    note = tools.create_text_file(project, "README.md", "hello")
    renamed = tools.rename(note, "規劃.md")
    tools.trash(project)

    assert renamed.read_text() == "hello"
    assert trashed == [str(project)]


def test_project_tools_reject_escape_and_root_delete(tmp_path: Path) -> None:
    tools = ProjectTools(tmp_path / "Project", trash_callback=lambda _path: None)

    with pytest.raises(SafetyError):
        tools.create_folder(".", "../outside")
    with pytest.raises(SafetyError):
        tools.trash(tools.root)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("下一首", ("next", None)),
        ("暫停", ("pause", None)),
        ("繼續", ("play", None)),
        ("音量 130", ("volume", 100)),
        ("播放 告五人的歌", ("search", "告五人的歌")),
        ("搜尋 睡眠音樂", ("search", "睡眠音樂")),
    ],
)
def test_parse_music_command(text: str, expected: tuple[str, str | int | None]) -> None:
    assert parse_music_command(text) == expected


def test_music_memory_playlists_and_saved_tracks(tmp_path: Path) -> None:
    memory = MusicMemory(tmp_path / "music.sqlite3")
    playlist = memory.add_playlist(
        "工作歌單", "https://music.youtube.com/playlist?list=PL123456789"
    )
    track = memory.save_track("你的樣子", "宇宙人", "理想狀態")

    assert memory.playlists() == [playlist]
    assert memory.saved_tracks() == [track]

    memory.delete_playlist(playlist.row_id)
    memory.delete_track(track.row_id)
    assert memory.playlists() == []
    assert memory.saved_tracks() == []


def test_music_memory_rejects_non_playlist_url(tmp_path: Path) -> None:
    memory = MusicMemory(tmp_path / "music.sqlite3")
    with pytest.raises(ValueError):
        memory.add_playlist("錯誤", "https://example.com/playlist")
    with pytest.raises(ValueError):
        memory.add_playlist("不是歌單", "https://music.youtube.com/watch?v=abc")
