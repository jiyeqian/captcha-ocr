"""CLI 行为测试(不依赖 tesseract 真实推理)。"""
import pytest

from captcha_ocr.cli import _build_parser, main


def test_no_args_prints_help(capsys):
    """无参数应打印帮助并返回 0(不崩溃)。"""
    rc = main([])
    out = capsys.readouterr().out
    assert rc == 0
    assert "usage" in out.lower()


def test_recognize_without_images_returns_help(capsys):
    """recognize 子命令但未给图片路径，应返回 1(非崩溃)。"""
    rc = main(["recognize"])
    out = capsys.readouterr().out
    assert rc == 1
    assert "usage" in out.lower()


def test_help_and_version_run():
    parser = _build_parser()
    assert parser.prog == "captcha-ocr"


def test_main_version_flag(monkeypatch, capsys):
    with pytest.raises(SystemExit) as exc:
        # 直接走 argparse 的 --version 会 raise SystemExit(0)
        from captcha_ocr.cli import _build_parser

        _build_parser().parse_args(["--version"])
    assert exc.value.code == 0
