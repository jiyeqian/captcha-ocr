"""配置与参数网格。

识别流程是「多策略投票」：对同一张图，用一组参数组合分别预处理 + OCR，
再对结果做投票与形近字纠正。`Config` 描述整个搜索空间，`OcrParam` 描述其中单点。
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field, replace

# 形近字纠正：tesseract 在验证码字体上常见的误读 → 正确值。
# 仅对「几乎总是误读」的字符做强制纠正，避免误伤。
DEFAULT_FORCED_CONFUSIONS: dict[str, str] = {
    "Z": "3",  # 3 常被读成 Z
    "O": "0",  # 0 常被读成 O
}

DEFAULT_WHITELIST = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"


@dataclass(frozen=True)
class OcrParam:
    """单个预处理 + OCR 参数点。

    threshold   : 亮度阈值，越小越严格(只留深色笔画)，越大保留越多(含浅色字)。
    min_area    : 连通域最小面积过滤，剔除该面积以下的噪点(小点/短干扰线)。
    scale       : 预处理后的放大倍数。小图需要更大倍数。
    psm         : tesseract 的页分割模式(6=块,7=单行,10=单词,11=文本行,13=单词...)。
    """

    threshold: int
    min_area: int
    scale: int
    psm: int

    def label(self) -> str:
        return f"thr={self.threshold} ma={self.min_area} sc={self.scale} psm={self.psm}"


@dataclass
class Config:
    """整条流水线的配置(参数搜索空间)。

    除单值字段外，多数字段为「可序列」→ 取笛卡尔积生成全部候选组合。
    """

    # ---- 预处理搜索 ----
    thresholds: tuple[int, ...] = field(
        default_factory=lambda: (215, 230, 235, 240, 250)
    )
    # 连通域面积：既给相对因子(随图大小自适应)，也给绝对下限，二者取较大者。
    min_area_factors: tuple[float, ...] = field(
        default_factory=lambda: (0.0006, 0.0012, 0.0025)
    )
    min_area_floor: int = 1
    # 预处理后最长边目标像素数，由此推算放大倍数 → 对大小不同的图都稳。
    target_long_side: int = 512
    # ---- OCR 搜索 ----
    psms: tuple[int, ...] = field(default_factory=lambda: (6, 7, 10, 11))
    oem: int = 1  # 1=LSTM(新)，0=旧引擎。验证码用 LSTM 更稳。
    whitelist: str = DEFAULT_WHITELIST

    # ---- tesseract 接入 ----
    tesseract_cmd: str = "tesseract"

    # ---- 投票/纠正 ----
    forced_confusions: dict[str, str] = field(
        default_factory=lambda: dict(DEFAULT_FORCED_CONFUSIONS)
    )
    # 期望验证码长度，用于长度就近打分与剪枝。
    expected_length: int = 4
    # 只保留长度在 [expected_length-2, expected_length+1] 内的候选参与统计。
    drop_out_of_length: bool = True

    # ---- 调试 ----
    verbose: bool = False
    debug_dir: str | None = None

    # -----------------------------------------------------------------
    def param_grid(self, image_width: int, image_height: int) -> list[OcrParam]:
        """根据图像尺寸展开完整参数网格。

        放大倍数按「最长边 → target_long_side」自适应，保证小图也被充分放大；
        面积过滤按因子 × 图像面积并加绝对下限。
        """
        area = image_width * image_height
        long_side = max(image_width, image_height)
        base_scale = max(3, round(self.target_long_side / max(long_side, 1)))
        # 小图(最长边 < 100)再给额外放大，tesseract 对小图极不友好。
        if long_side < 100:
            base_scale = max(base_scale, 12)
        else:
            base_scale = max(base_scale, 4)

        scales = self._scale_variants(base_scale)
        out: list[OcrParam] = []
        for thr in self.thresholds:
            for factor in self.min_area_factors:
                area_filter = max(self.min_area_floor, int(round(area * factor)))
                for scale in scales:
                    for psm in self.psms:
                        out.append(
                            OcrParam(
                                threshold=int(thr),
                                min_area=int(area_filter),
                                scale=int(scale),
                                psm=int(psm),
                            )
                        )
        return out

    def _scale_variants(self, base: int) -> tuple[int, ...]:
        """围绕基准倍数给出 2~3 个候选。"""
        hi = min(base + 4, 40)
        return tuple(sorted({max(3, base - 2), base, hi}))


def default_config() -> Config:
    """返回一套经过实测调优的默认配置。"""
    return Config()
