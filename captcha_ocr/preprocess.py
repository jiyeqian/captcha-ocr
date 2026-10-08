"""图像预处理：二值化 + 连通域去噪 + 放大。

设计目标：处理「白底 + 彩色字形 + 彩色噪点(点/短斜线) + 可能少量浅色字」的验证码。
- 白底：亮度 < 阈值 的像素即前景。
- 噪声：字形笔画粗、连通域面积大；噪点/干扰线小 → 按面积剔除(连通域滤波)。
- 小图：tesseract 对 < ~200px 的图很弱 → 放大到合理尺寸。

仅依赖 Pillow，纯 Python 实现连通域标记(无需 numpy/opencv)。
"""
from __future__ import annotations

import os
from collections import deque
from typing import Iterable

from PIL import Image, ImageOps

from .config import OcrParam


def luminance_to_mask(img: Image.Image, threshold: int) -> list[bool]:
    """把图转灰度，产生前景掩码(前景=True)。

    RGBA/带 alpha 的图先压平到 RGB(用白做底)再取灰度，避免透明像素干扰。
    """
    if img.mode in ("RGBA", "LA", "P", "PA"):
        bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
        img = img.convert("RGBA")
        bg.alpha_composite(img)
        img = bg.convert("RGB")
    gray = img.convert("L")
    thr = max(0, min(255, threshold))
    # 'L' 图的 tobytes() 即逐像素亮度(0~255)，比 getdata() 更稳且不弃用
    pixels = gray.tobytes()
    return [p < thr for p in pixels], img.size[0], img.size[1]


def _denoise(conn_mask: list[bool], width: int, height: int, min_area: int) -> list[bool]:
    """8 邻域连通域标记；面积 < min_area 的块整体清掉(判为噪点)。

    用显式栈的扫描线标记，避免递归深度问题；对小图(几百~上万像素)足够快。
    """
    width = int(width)
    height = int(height)
    if min_area <= 1:
        # 不滤噪，但仍规整成 bool 列表
        return [bool(v) for v in conn_mask]

    conn = [bool(v) for v in conn_mask]
    visited = [False] * (width * height)
    kept: list[bool] = [False] * (width * height)

    stack: deque[int] = deque()
    for start in range(width * height):
        if not conn[start] or visited[start]:
            continue
        # 收集该连通块所有像素
        stack.append(start)
        visited[start] = True
        members: list[int] = []
        while stack:
            cur = stack.pop()
            members.append(cur)
            cy, cx = divmod(cur, width)
            for ny in (cy - 1, cy, cy + 1):
                if ny < 0 or ny >= height:
                    continue
                row_base = ny * width
                for nx in (cx - 1, cx, cx + 1):
                    if nx < 0 or nx >= width:
                        continue
                    ni = row_base + nx
                    if conn[ni] and not visited[ni]:
                        visited[ni] = True
                        stack.append(ni)
        if len(members) >= min_area:
            for m in members:
                kept[m] = True
    return kept


def preprocess(img: Image.Image, param: OcrParam) -> Image.Image:
    """按给定参数产出「黑字白底」的高对比度灰度图，可直接喂给 tesseract。"""
    mask, w, h = luminance_to_mask(img, param.threshold)
    kept = _denoise(mask, w, h, param.min_area)

    # 前景→黑(0)，背景→白(255)
    arr = bytearray((0 if v else 255) for v in kept)
    out = Image.frombytes("L", (w, h), bytes(arr))

    scale = max(1, int(param.scale))
    if scale != 1:
        out = out.resize((w * scale, h * scale), Image.LANCZOS)

    # 加白边：tesseract 对顶到边界的字识别更稳。
    out = ImageOps.expand(out, border=max(4, 8 * scale // 4), fill=255)
    return out


def save_debug(img: Image.Image, param: OcrParam, debug_dir: str, tag: str = "") -> str:
    """保存预处理后的图到 debug_dir，返回路径(便于肉眼复核)。"""
    os.makedirs(debug_dir, exist_ok=True)
    path = os.path.join(debug_dir, f"{tag or 'img'}_{param.label().replace(' ', '').replace('=', '_')}.png")
    out = preprocess(img, param)
    out.save(path)
    return path
