"""命令行接口。

用法：
    captcha-ocr <img> [img2 ...] [--show] [--length 4] [--csv]
        识别一张或多张验证码图(默认命令 = recognize)。
    captcha-ocr recognize <img> ...     同上，显式写法。
    captcha-ocr eval [labels.csv] [--show]   在样本集上评测准确率。

安装后可用 `captcha-ocr`；开发期可用 `uv run captcha-ocr ...` 或
`python -m captcha_ocr ...`。
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from collections.abc import Sequence
from typing import TextIO

from . import __version__
from .config import default_config
from .dataset import EvalResult, load_samples
from .errors import TesseractNotFoundError
from .pipeline import Recognition, recognize, recognize_file

DEFAULT_LABELS = os.path.join("samples", "labels.csv")


def _add_common_options(sp: argparse.ArgumentParser) -> None:
    sp.add_argument("--length", type=int, default=4, help="期望字符数(默认 4)，用于投票打分")
    sp.add_argument("--show", action="store_true", help="保存去噪中间图到 debug/ 便于复核")
    sp.add_argument("--csv", action="store_true", help="以 CSV 输出(仅 recognize)")
    sp.add_argument("--whitelist", type=str, default=None, help="限定可识别字符集")
    sp.add_argument("--thresholds", type=str, default=None,
                    help="逗号分隔的亮度阈值网格，如 '230,240,250'")
    sp.add_argument("--expected-lengths", type=int, default=None, help="同 --length 的别名")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="captcha-ocr",
        description="对噪声验证码做 OCR 识别(预处理 + Tesseract + 多策略投票)。",
    )
    p.add_argument("--version", action="version", version=f"captcha-ocr {__version__}")
    sub = p.add_subparsers(dest="command", metavar="{recognize,eval}")

    rec = sub.add_parser("recognize", help="识别图片(默认)")
    rec.add_argument("images", nargs="*", help="待识别的图片路径")
    _add_common_options(rec)

    ev = sub.add_parser("eval", help="在样本集上评测准确率")
    ev.add_argument("labels", nargs="?", default=DEFAULT_LABELS,
                    help="labels.csv 路径(默认 samples/labels.csv)")
    ev.add_argument("--length", type=int, default=4, help="期望字符数(默认 4)")
    ev.add_argument("--show", action="store_true", help="保存去噪中间图到 debug/")
    return p


def _parse_args(raw: Sequence[str], parser: argparse.ArgumentParser) -> tuple[str, argparse.Namespace]:
    """把「直接给图片」的老式调用归一到 recognize 子命令。"""
    first = raw[0] if raw else ""
    if raw and first not in ("recognize", "eval", "help") and not first.startswith("-"):
        raw = ["recognize", *raw]
    ns = parser.parse_args(raw)
    cmd = ns.command or "recognize"
    return cmd, ns


def _make_config(ns: argparse.Namespace) -> object:
    cfg = default_config()
    length = getattr(ns, "expected_lengths", None) or getattr(ns, "length", 4)
    cfg.expected_length = int(length)
    if getattr(ns, "show", False):
        cfg.debug_dir = "debug"
    if getattr(ns, "whitelist", None):
        cfg.whitelist = ns.whitelist
    th = getattr(ns, "thresholds", None)
    if th:
        cfg.thresholds = tuple(int(x) for x in th.split(",") if x.strip())
    return cfg


def _run_recognize(ns: argparse.Namespace, parser: argparse.ArgumentParser, out: TextIO) -> int:
    images = getattr(ns, "images", None)
    if not images:
        # 无图片参数：打印帮助而非崩溃
        parser.print_help()
        return 1
    cfg = _make_config(ns)
    results: list[tuple[str, Recognition]] = []
    for path in images:
        try:
            res = recognize_file(path, cfg)  # type: ignore[arg-type]
        except TesseractNotFoundError as exc:
            print(exc, file=sys.stderr)
            return 2
        except OSError as exc:
            print(f"[跳过] {path}: {exc}", file=sys.stderr)
            continue
        results.append((path, res))

    if getattr(ns, "csv", False):
        w = csv.writer(out)
        w.writerow(["result", "confidence", "file"])
        for path, res in results:
            w.writerow([res.text, f"{res.confidence:.2f}", path])
        return 0

    for path, res in results:
        print(path)
        print(f"  识别结果: {res.text or '(空)'}   置信度 {res.confidence:.2%}")
        alts = [f"{c.text}×{c.count}" for c in res.candidates[1:5]]
        if alts:
            print(f"  其它候选: {'  '.join(alts)}")
        if res.confidence < 0.5 and res.text:
            print("  注意: 置信度偏低，建议 `--show` 保存中间图后目视复核。")
    return 0


def _run_eval(ns: argparse.Namespace, out: TextIO) -> int:
    from .config import default_config as dc

    cfg = dc()
    cfg.expected_length = int(getattr(ns, "length", 4))
    if getattr(ns, "show", False):
        cfg.debug_dir = "debug"
    try:
        samples = load_samples(ns.labels)
    except OSError as exc:
        print(f"[错误] 无法读取 {ns.labels}: {exc}", file=sys.stderr)
        return 1
    if not samples:
        print(f"[错误] {ns.labels} 中没有样本", file=sys.stderr)
        return 1

    per: list[tuple[str, str, str]] = []
    correct = 0
    for s in samples:
        try:
            res = recognize(s.filename, cfg)
            pred = res.text
            ok = pred == s.label
        except TesseractNotFoundError as exc:
            print(exc, file=sys.stderr)
            return 2
        except OSError as exc:
            print(f"[跳过] {s.label} ({s.filename}): {exc}", file=sys.stderr)
            continue
        if ok:
            correct += 1
        per.append((s.label, pred, "ok" if ok else "miss"))

    er = EvalResult(correct=correct, total=len(per), per_sample=per)
    print(er)
    return 0 if er.total == er.correct else 3


def main(argv: Sequence[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    parser = _build_parser()
    # 无任何参数：打印帮助
    if not raw:
        parser.print_help()
        return 0
    cmd, ns = _parse_args(raw, parser)
    if cmd == "eval":
        return _run_eval(ns, sys.stdout)
    return _run_recognize(ns, parser, sys.stdout)


if __name__ == "__main__":
    raise SystemExit(main())
