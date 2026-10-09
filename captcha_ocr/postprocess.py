"""结果后处理：清洗、形近字纠正、多候选投票。"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass


def clean_alnum(text: str, whitelist: str = "") -> str:
    """只保留字符集内的字符。whitelist 为空则保留全部字母数字。"""
    out = []
    for ch in text:
        if not ch.isalnum():
            continue
        if whitelist and ch not in whitelist:
            continue
        out.append(ch)
    return "".join(out)


def apply_forced_confusions(text: str, table: dict[str, str]) -> str:
    """按纠正表把字符映射为期望值(如 Z->3, O->0)。"""
    return "".join(table.get(ch, ch) for ch in text)


@dataclass
class Candidate:
    text: str
    count: int = 0

    def __post_init__(self) -> None:
        self.count = max(self.count, 0)


def vote(
    raw_results: list[str],
    *,
    whitelist: str,
    forced: dict[str, str],
    expected_length: int = 4,
    drop_out_of_length: bool = True,
) -> list[Candidate]:
    """对一批原始识别串做清洗 → 纠正 → 投票。

    返回按 (频次降序, 长度就近, 文本) 排序的候选列表。
    """
    cleaned: list[str] = []
    for raw in raw_results:
        c = clean_alnum(raw, whitelist=whitelist)
        c = apply_forced_confusions(c, forced)
        if not c:
            continue
        if drop_out_of_length and expected_length > 0:
            low = max(1, expected_length - 2)
            high = expected_length + 1
            if not (low <= len(c) <= high):
                continue
        cleaned.append(c)

    counter: Counter[str] = Counter(cleaned)
    if not counter:
        return []

    def sort_key(item: tuple[str, int]) -> tuple[int, int, str]:
        text, n = item
        return (-n, abs(len(text) - expected_length), text)

    ordered = sorted(counter.items(), key=sort_key)
    return [Candidate(text=t, count=n) for t, n in ordered]


def confidence(top: Candidate, total: int) -> float:
    """主候选的一致性置信度 = 票数 / 总票数。"""
    return round(top.count / max(total, 1), 4) if total else 0.0
