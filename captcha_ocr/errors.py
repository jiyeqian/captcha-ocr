"""异常定义。"""


class CaptchaOcrError(Exception):
    """captcha_ocr 基础异常。"""


class TesseractNotFoundError(CaptchaOcrError):
    """系统 PATH 中找不到 tesseract 可执行程序。"""

    def __init__(self, detail: str = ""):
        msg = (
            "未找到 tesseract 可执行程序。\n"
            "  macOS: brew install tesseract\n"
            "  Debian/Ubuntu: sudo apt install tesseract-ocr\n"
            "  或通过 Config.tesseract_cmd 显式指定路径。\n"
            + (f"详情: {detail}" if detail else "")
        )
        super().__init__(msg)
