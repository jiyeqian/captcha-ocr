"""预处理单元与逻辑测试(不依赖 tesseract / numpy)。"""
from PIL import Image

from captcha_ocr.config import Config, OcrParam, default_config
from captcha_ocr.postprocess import apply_forced_confusions, clean_alnum, vote
from captcha_ocr.preprocess import _denoise, luminance_to_mask, preprocess


def test_param_grid_adapts_to_size():
    small = default_config().param_grid(65, 40)
    big = default_config().param_grid(184, 134)
    # 小图放大倍数应 >= 12；两者都非空
    assert small and big
    assert max(p.scale for p in small) >= 12
    # 面积过滤因子随图大小自适应：大图 min_area 更大
    assert all(p.min_area >= 1 for p in big)
    assert max(p.min_area for p in big) > max(p.min_area for p in small)


def test_clean_alnum_and_whitelist():
    assert clean_alnum("3*u7-0!", "") == "3u70"
    assert clean_alnum("3uZ0", whitelist="0123456789") == "30"  # 字母被白名单挡掉


def test_forced_confusions():
    out = apply_forced_confusions("Zu7O", {"Z": "3", "O": "0"})
    assert out == "3u70"


def test_vote_picks_mode_and_length():
    cands = vote(
        raw_results=["Zu70", "Zu70", "Sui70", "370", "v97e", "junk"],
        whitelist="",
        forced={"Z": "3"},
        expected_length=4,
        drop_out_of_length=True,
    )
    assert cands, "应至少有候选"
    assert cands[0].text == "3u70"
    assert cands[0].count >= 2


def test_vote_drops_out_of_length():
    cands = vote(
        raw_results=["3u70abcd", "3u70xyz"],
        whitelist="",
        forced={},
        expected_length=4,
        drop_out_of_length=True,
    )
    assert cands == []  # 全部超长被剪


def test_luminance_mask_threshold():
    img = Image.new("L", (10, 10), 200)  # 全较亮背景
    mask, w, h = luminance_to_mask(img, threshold=150)
    assert w == 10 and h == 10
    assert all(not p for p in mask)  # 全背景

    img2 = Image.new("L", (10, 10), 50)  # 全暗前景
    mask2, _, _ = luminance_to_mask(img2, threshold=150)
    assert all(p for p in mask2)


def test_denoise_drops_small_components():
    w = h = 10
    mask = [False] * (w * h)
    # 一个 2x2 小点(面积 4) 与一条 5 像素长线(面积 5)
    mask[0 * w + 0] = mask[0 * w + 1] = mask[1 * w + 0] = mask[1 * w + 1] = True
    for i in range(5):
        mask[3 * w + i] = True
    kept = _denoise(mask, w, h, min_area=3)
    # 长线(5)保留，点(4<... )—这里 4>=3 也保留，故都留；换成 min_area 大些
    kept = _denoise(mask, w, h, min_area=5)
    # 点(4) 被删，线(5) 保留
    assert not kept[0 * w + 0]
    assert kept[3 * w + 1]


def test_preprocess_shape_and_mode():
    img = Image.new("RGBA", (20, 12), (255, 255, 255, 255))
    out = preprocess(img, OcrParam(threshold=200, min_area=1, scale=4, psm=7))
    assert out.mode == "L"
    assert out.width > 20 and out.height > 12  # 放大 + 白边
