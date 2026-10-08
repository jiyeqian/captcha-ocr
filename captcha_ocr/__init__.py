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
from .config import Config, default_config, OcrParam
from .pipeline import Recognition, recognize, recognize_file
from .errors import TesseractNotFoundError

__version__ = "0.1.0"

__all__ = [
    "Config",
    "default_config",
    "OcrParam",
    "Recognition",
    "recognize",
    "recognize_file",
    "TesseractNotFoundError",
    "__version__",
]
