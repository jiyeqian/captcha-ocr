"""样本数据集与评测(accuracy)。

`samples/labels.csv` 形如：
    label,filename
    3u70,3u70.png
    v92e,v92e.png

文件名相对 labels.csv 所在目录解析。
"""
from __future__ import annotations

import csv
import os
from dataclasses import dataclass


@dataclass
class Sample:
    label: str
    filename: str


def load_samples(labels_csv: str) -> list[Sample]:
    """从 csv 读取 (label, filename)。兼容表头为 label,filename。"""
    path = os.path.abspath(labels_csv)
    base = os.path.dirname(path)
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        rows = [r for r in reader if r and any(cell.strip() for cell in r)]
    if not rows:
        return []
    # 第一行可能是表头
    header = [c.strip().lower() for c in rows[0]]
    start = 0
    if header and {"label", "filename"} & set(header):
        idx_label = header.index("label")
        idx_file = header.index("filename")
        start = 1
    else:
        idx_label, idx_file = 0, 1
    samples: list[Sample] = []
    for row in rows[start:]:
        if len(row) < 2:
            continue
        label = row[idx_label].strip()
        fname = row[idx_file].strip()
        if not fname:
            continue
        samples.append(Sample(label=label, filename=os.path.join(base, fname)))
    return samples


@dataclass
class EvalResult:
    correct: int
    total: int
    per_sample: list[tuple[str, str, str]]  # (label, predicted, status)

    @property
    def accuracy(self) -> float:
        return round(self.correct / self.total, 4) if self.total else 0.0

    def __str__(self) -> str:
        lines = [f"准确率 {self.correct}/{self.total} = {self.accuracy:.2%}"]
        for label, pred, status in self.per_sample:
            mark = "✓" if status == "ok" else "✗"
            lines.append(f"  {mark} 期望 '{label}' / 得到 '{pred}'")
        return "\n".join(lines)
