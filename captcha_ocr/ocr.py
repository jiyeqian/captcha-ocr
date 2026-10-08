"""Tesseract 封装。

要点：某些环境(本机 Homebrew 构建的 tesseract)无法读取 /tmp 下的文件，
但对「当前工作目录」下的文件正常。故临时文件统一落在 Config 指定的
临时目录(默认 cwd 下的隐藏 `.tmp/`)，并保证清理。
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from typing import Sequence

from PIL import Image

from .errors import TesseractNotFoundError


def resolve_tesseract(cmd: str) -> str:
    """解析 tesseract 可执行路径；找不到则抛 TesseractNotFoundError。"""
    found = shutil.which(cmd) if os.path.sep not in cmd and cmd not in (".", "..") else cmd
    if found and os.path.exists(found):
        return found
    raise TesseractNotFoundError(f"'{cmd}' 无法在 PATH 中找到")


class TesseractClient:
    """对单张图反复调用 tesseract 的轻量客户端，管理临时文件。"""

    def __init__(
        self,
        cmd: str = "tesseract",
        oem: int = 1,
        whitelist: str = "",
        temp_dir: str | None = None,
    ) -> None:
        self.cmd = resolve_tesseract(cmd)
        self.oem = int(oem)
        self.whitelist = whitelist
        self._temp_dir = temp_dir or tempfile.mkdtemp(prefix=".captcha_", dir=_cwd())
        self._path = os.path.join(self._temp_dir, "frame.png")

    def recognize(self, image: Image.Image, psm: int) -> str:
        """把已预处理的黑字白底图送 tesseract，返回原始字符串(未清洗)。

        psm: tesseract 页分割模式。
        """
        image.save(self._path, "PNG")
        args: list[str] = [self.cmd, self._path, "stdout", "--oem", str(self.oem), "--psm", str(psm)]
        if self.whitelist:
            args += ["-c", f"tessedit_char_whitelist={self.whitelist}"]
        try:
            proc = subprocess.run(args, capture_output=True, text=False)
        except OSError as exc:
            raise TesseractNotFoundError(str(exc)) from exc
        return proc.stdout.decode("utf-8", "ignore").replace(" ", "").strip()

    def __del__(self) -> None:  # pragma: no cover
        self.cleanup()

    def cleanup(self) -> None:
        try:
            if os.path.exists(self._path):
                os.remove(self._path)
        except OSError:
            pass
        try:
            os.rmdir(self._temp_dir)
        except OSError:
            pass


def _cwd() -> str:
    """临时文件落盘目录：当前工作目录(规避 /tmp 不可读问题)。"""
    return os.getcwd()
