# captcha-ocr

[![CI](https://github.com/jiyeqian/captcha-ocr/actions/workflows/ci.yml/badge.svg)](https://github.com/jiyeqian/captcha-ocr/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](#环境要求)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](./LICENSE)
[![version](https://img.shields.io/badge/version-0.1.0-orange.svg)]()

对「带噪声的图形验证码」做 OCR 识别。目标场景：**白底 + 彩色字形 + 彩色噪点/干扰线 + 少量浅色字**。

它**不是**一个魔法模型，而是把三件事串成流水线，并在其上做**多策略投票**以提高稳定性：

```
原图 ──▶ 预处理(二值化 + 连通域去噪 + 放大) ──▶ Tesseract OCR ──▶ 清洗 + 形近字纠正 + 投票 ──▶ 结果 + 置信度
```

设计取舍：

- **只依赖 Pillow**（图像处理）；Tesseract 为**外部命令行工具**（uv 无法管理），需自行安装。
- 纯 Python 实现连通域滤波（无 numpy / 无 opencv），对小图也很轻。
- 不追求 100% 识别率，但**如实暴露不确定性**：给出置信度、全部候选，并可 `--show` 保存去噪中间图目视复核。

---

## 环境要求

- Python ≥ 3.10
- [uv](https://docs.astral.sh/uv/) 管理环境与依赖
- Tesseract（系统二进制）

```bash
# macOS
brew install tesseract
# Debian/Ubuntu
sudo apt install tesseract-ocr
```

---

## 安装

### A. 项目内开发（推荐，随 uv 环境走）

```bash
cd captcha-ocr
uv sync --all-extras        # 建立 .venv，安装 pillow + pytest
```

之后**在项目根目录**用 `uv run` 调用（等价于用项目虚拟环境）：

```bash
uv run captcha-ocr samples/3u70.png
uv run python -m captcha_ocr samples/3u70.png
```

### B. 装成「到处可执行」的全局命令

`uv sync` 只把脚本装进项目的 `.venv/bin`，**不进 PATH**。若希望像普通命令一样在任意目录直接调用：

```bash
# 以源码安装为独立工具(隔离虚拟环境 + 生成 ~/.local/bin/captcha-ocr)
# 需先确保 ~/.local/bin 在 PATH 上
uv tool install .
captcha-ocr samples/3u70.png      # 任意目录下裸调
```

> `~/.local/bin` 是 uv 工具的默认安装目录；若 PATH 未包含，可执行
> `uv tool update-shell` 或手动把 `~/.local/bin` 加入 PATH。

---

## 使用

### 1) 识别图片

```bash
# 项目内(方式 A)
uv run captcha-ocr samples/3u70.png
# 或
uv run python -m captcha_ocr samples/3u70.png v92e.png
# 全局命令(方式 B)
captcha-ocr samples/3u70.png

# 保存去噪中间图到 debug/ 便于目视复核
uv run captcha-ocr 3u70.png --show

# CSV 输出(结果,置信度,文件)
uv run captcha-ocr *.png --csv

# 调整/限定参数
uv run captcha-ocr 3u70.png --length 6 --thresholds 230,240,250 --whitelist 0123456789
```

输出示例：

```
3u70.png
  识别结果: 3u70   置信度 100.00%
  其它候选: v92e×...
```

### 2) 在样本集上评测准确率

`samples/labels.csv`：

```csv
label,filename
3u70,3u70.png
v92e,v92e.png
rwjx,rwjx.png
```

```bash
uv run captcha-ocr eval
# 或指定其它 labels 文件
uv run captcha-ocr eval samples/labels.csv --show
```

输出形如：

```
准确率 2/3 = 66.67%
  ✓ 期望 '3u70' / 得到 '3u70'
  ✓ 期望 'v92e' / 得到 'v92e'
  ✗ 期望 'rwjx' / 得到 'rwyx'
```

> 说明：`rwjx.png` 是困难样本（65×40 小图、字浅、`j`/`w` 易混）。Tesseract 会把 `j` 稳定误读为 `y`。工程层面已做到「识别 + 暴露不确定性」，进一步提升见下文。

---

## 作为库调用

```python
from captcha_ocr import recognize_file, default_config

res = recognize_file("3u70.png")
print(res.text)        # '3u70'
print(res.confidence)  # 0.98 ...
for c in res.candidates:
    print(c.text, c.count)

# 自定义配置
from captcha_ocr import Config
cfg = default_config()
cfg.thresholds = (230, 240, 250)
cfg.psms = (6, 7)
cfg.whitelist = "0123456789abcdef"
res = recognize_file("3u70.png", cfg)
```

---

## 已知坑与对策

| 现象 | 原因 | 对策（代码已处理） |
| --- | --- | --- |
| Tesseract 报 `failed to open locally` | 本机 Homebrew 版 Tesseract 无法读 `/tmp` 下文件 | 临时图写到 **cwd 下**的隐藏目录 `.tmp/`（见 `ocr.py`） |
| 浅色/小字（如 `u`、`e`、`j`）漏识别 | 阈值/去噪过严 | 参数网格含较高阈值；面积过滤按图面积自适应；小图额外放大 |
| `3→Z`、`0→O` 等形近误读 | Tesseract 字体混淆 | `Config.forced_confusions` 默认纠正 `Z→3`、`O→0` |
| 结果不稳 | 单参数 OCR 噪声大 | 多参数笛卡尔积 + 投票 + 长度就近打分 |

## 提升准确率的路线

1. **扩充字符集 / 训练轻量模型**：用大量带标签样本训练 CNN / 用 `tesseract` 训练自定义 `.traineddata`。
2. **加特征做字符级消歧**：如「带顶点的长降线 = `j`」的启发式，解决 `j/w/y` 混淆。
3. **接入 OCR 服务 / 云端模型**：把 `TesseractClient` 换成任意推理后端（接口已隔离）。

---

## 目录结构

```
captcha-ocr/
├── pyproject.toml           # uv / hatch 项目配置、入口脚本、依赖
├── .python-version          # 锁定 Python 3.12
├── README.md
├── captcha_ocr/
│   ├── __init__.py          # 对外 API
│   ├── __main__.py          # python -m captcha_ocr
│   ├── cli.py               # 命令行(reconcize/eval)
│   ├── config.py            # Config / OcrParam / 参数网格
│   ├── preprocess.py        # 二值化 + 连通域去噪 + 放大
│   ├── ocr.py               # TesseractClient(临时文件落在 cwd)
│   ├── postprocess.py       # 清洗/纠正/投票/置信度
│   ├── pipeline.py          # 串联 + Recognition 结果对象
│   ├── dataset.py           # 读 labels.csv、评测
│   └── errors.py            # TesseractNotFoundError 等
├── samples/                 # 3 张测试图 + labels.csv
└── tests/                   # pytest
```

## 开发

```bash
uv sync --all-extras
uv run pytest            # 跑测试(含端到端；无 tesseract 时自动 skip)
uv run ruff check .      # 可选：代码风格
```

## License

MIT
