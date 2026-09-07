from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass
from pathlib import Path

from PIL import Image


SUPPORTED_IMAGES = {".png", ".jpg", ".jpeg", ".heic", ".webp", ".tiff", ".bmp"}


@dataclass(frozen=True)
class ImageInfo:
    path: Path
    width: int
    height: int
    format: str
    size_bytes: int


class LocalImageTools:
    """Read-only image understanding backed by Pillow and macOS Vision."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.ocr_binary = project_root / "bin" / "vision-ocr"
        self.ocr_source = project_root / "tools" / "vision_ocr.swift"

    @staticmethod
    def is_image(path: Path) -> bool:
        return path.is_file() and not path.is_symlink() and path.suffix.lower() in SUPPORTED_IMAGES

    def inspect(self, paths: list[Path]) -> list[ImageInfo]:
        details = []
        for path in paths:
            resolved = path.expanduser().resolve()
            if not self.is_image(resolved):
                continue
            try:
                with Image.open(resolved) as image:
                    details.append(
                        ImageInfo(
                            path=resolved,
                            width=image.width,
                            height=image.height,
                            format=image.format or resolved.suffix.removeprefix(".").upper(),
                            size_bytes=resolved.stat().st_size,
                        )
                    )
            except (OSError, ValueError):
                continue
        return details

    def recognize_text(self, paths: list[Path]) -> str:
        if not self.ocr_binary.exists():
            raise RuntimeError("找不到 macOS Vision OCR helper，請執行 scripts/build_ocr.sh")
        sections = []
        for path in paths:
            resolved = path.expanduser().resolve()
            if not self.is_image(resolved):
                continue
            process = subprocess.run(
                [str(self.ocr_binary), "ocr", str(resolved)],
                capture_output=True,
                text=True,
                timeout=90,
                check=False,
            )
            if process.returncode != 0:
                raise RuntimeError(process.stderr.strip() or f"無法辨識 {resolved.name}")
            text = process.stdout.strip() or "（沒有辨識到文字）"
            sections.append(f"## {resolved.name}\n\n{text}")
        return "\n\n".join(sections) if sections else "沒有可辨識的圖片。"

    def analyze(self, paths: list[Path]) -> str:
        sections = []
        for path in paths:
            resolved = path.expanduser().resolve()
            if not self.is_image(resolved):
                continue
            labels = self._vision_request("classify", resolved)
            codes = self._vision_request("codes", resolved)
            label_lines = []
            for line in labels.splitlines():
                parts = line.split("\t", 1)
                if len(parts) == 2:
                    label_lines.append(f"- {parts[0]} ({float(parts[1]) * 100:.0f}%)")
            code_lines = [f"- {line.replace(chr(9), ': ', 1)}" for line in codes.splitlines()]
            body = "\n".join(label_lines) or "- 沒有足夠可信的分類標籤"
            if code_lines:
                body += "\n\n偵測到的 QR／條碼：\n" + "\n".join(code_lines)
            sections.append(f"## {resolved.name}\n\n{body}")
        return "\n\n".join(sections) if sections else "沒有可分析的圖片。"

    def find_duplicates(self, paths: list[Path]) -> list[list[Path]]:
        groups: dict[str, list[Path]] = {}
        for path in paths:
            resolved = path.expanduser().resolve()
            if not self.is_image(resolved):
                continue
            digest = hashlib.sha256()
            with resolved.open("rb") as handle:
                for block in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(block)
            groups.setdefault(digest.hexdigest(), []).append(resolved)
        return [items for items in groups.values() if len(items) > 1]

    def _vision_request(self, mode: str, path: Path) -> str:
        if not self.ocr_binary.exists():
            raise RuntimeError("找不到 macOS Vision helper，請執行 scripts/build_ocr.sh")
        process = subprocess.run(
            [str(self.ocr_binary), mode, str(path)],
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )
        if process.returncode != 0:
            raise RuntimeError(process.stderr.strip() or f"無法分析 {path.name}")
        return process.stdout.strip()
