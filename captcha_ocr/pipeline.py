"""编排整条流水线：预处理网格 × tesseract × 后处理投票 → Recognition。"""
from __future__ import annotations

from dataclasses import dataclass, field

from PIL import Image

from .config import Config, default_config
from .ocr import TesseractClient
from .postprocess import Candidate, confidence, vote
from .preprocess import preprocess, save_debug


@dataclass
class Recognition:
    """一次识别的完整结果。

    text       : 最佳猜测
    confidence : 最佳候选的一致性(0~1)
    candidates : 全部候选(含票数)
    raw        : 每个参数点的原始 tesseract 输出(调试用)
    """

    text: str
    confidence: float
    candidates: list[Candidate]
    raw: list[tuple[str, str]] = field(default_factory=list)
    image: str | None = None

    def __str__(self) -> str:
        head = f"{self.text} (置信度 {self.confidence:.2%})"
        alt = ", ".join(f"{c.text}×{c.count}" for c in self.candidates[1:4])
        return head + (f"  其它候选: {alt}" if alt else "")


def _load_image(source: str | Image.Image) -> Image.Image | None:
    if isinstance(source, str):
        return Image.open(source)
    return source


def recognize(image: Image.Image | str, config: Config | None = None) -> Recognition:
    """识别一张验证码图(文件路径或已打开的 PIL.Image)。

    返回 Recognition；若某参数点全部识别失败，text 可能为空字符串。
    """
    cfg = config or default_config()
    img = _load_image(image)
    if img is None:
        raise ValueError("无法加载图像")

    params = cfg.param_grid(img.width, img.height)
    client = TesseractClient(cmd=cfg.tesseract_cmd, oem=cfg.oem, whitelist=cfg.whitelist)
    raw: list[str] = []
    pairs: list[tuple[str, str]] = []
    try:
        for p in params:
            clean = preprocess(img, p)
            if cfg.debug_dir:
                save_debug(img, p, cfg.debug_dir, tag=cfg.verbose and "ok")
            out = client.recognize(clean, psm=p.psm)
            raw.append(out)
            pairs.append((p.label(), out))
    finally:
        client.cleanup()

    candidates = vote(
        raw_results=raw,
        whitelist=cfg.whitelist,
        forced=cfg.forced_confusions,
        expected_length=cfg.expected_length,
        drop_out_of_length=cfg.drop_out_of_length,
    )
    top = candidates[0] if candidates else Candidate(text="", count=0)
    conf = confidence(top, total=len([r for r in raw if r]))
    return Recognition(
        text=top.text,
        confidence=conf,
        candidates=candidates,
        raw=pairs,
    )


def recognize_file(path: str, config: Config | None = None) -> Recognition:
    """按路径识别文件。"""
    res = recognize(path, config)
    res.image = path
    return res
