# 变更日志

本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [0.1.0] - 2025-10-08

### 新增
- 多策略验证码识别流水线:预处理(二值化 + 连通域去噪 + 放大) → Tesseract OCR → 清洗/形近字纠正/投票。
- 命令行工具 `captcha-ocr`:子命令 `recognize`(默认)与 `eval`,支持 `--show / --csv / --length / --thresholds / --whitelist`。
- 库 API:`recognize` / `recognize_file` / `Config` / `default_config`。
- 数据集评测:`samples/labels.csv` + 准确率报告(✓/✗ + 置信度)。
- 仅依赖 Pillow,纯 Python 连通域滤波(无需 numpy/opencv)。
- 已知坑处理:规避 macOS 下 Tesseract 无法读 `/tmp` 的问题(临时文件落 cwd);`Z→3`、`O→0` 形近字纠正。
- 测试:单元测试(逻辑/预处理/CLI 回归)+ 端到端(无 tesseract 自动 skip)。
- 工程化:`uv` 管理;`hatchling` 构建;GitHub Actions CI(矩阵 3.10–3.13,ruff + pytest + 构建)。
- 开源:MIT License,README,CHANGELOG;公开仓库 `jiyeqian/captcha-ocr`。

### 已知限制
- 困难样本(如 65×40 小图、浅字、`j/w/y` 易混)识别率有限;工具输出置信度与候选列表,便于目视复核。
- Tesseract 为外部命令行依赖,需自行安装(macOS: `brew install tesseract`)。
