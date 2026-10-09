"""captcha_ocr

A configurable, multi-strategy OCR pipeline for noisy captcha images.

Public API:
    from captcha_ocr import recognize, recognize_file, Config

    result = recognize_file("captcha.png")
    print(result.text)          # 最佳识别结果
    print(result.confidence)    # 主候选的一致性置信度
    for c in result.candidates: # 其它候选及次数
        print(c.text, c.count)
"""
from .config import Config, OcrParam, default_config
from .errors import TesseractNotFoundError
from .pipeline import Recognition, recognize, recognize_file

__version__ = "0.1.0"

__all__ = [
    "Config",
    "OcrParam",
    "Recognition",
    "TesseractNotFoundError",
    "__version__",
    "default_config",
    "recognize",
    "recognize_file",
]
