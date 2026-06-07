---
type: concept
created: 2026-06-07
updated: 2026-06-07
tags: [工具链, PDF, OCR, Ingest]
---

# PDF 本地解析工具链

## 目标

为书籍 ingest 提供一套本地可重复使用的 PDF 解析基础设施：

- 文本型 PDF：直接提取文本层
- 扫描型 PDF：自动逐页 OCR
- 混合型 PDF：按页自动选择文本层或 OCR
- 识别结果：落盘到本地缓存，后续 ingest 直接复用

## 推荐方案

当前推荐的本地方案是：

- `pypdf`：提取文本层
- `pypdfium2`：把扫描页渲染成图片
- `rapidocr_onnxruntime`：对渲染图片做中文 OCR

这套组合比单独用 `pypdf`、`pdfminer` 更稳，因为很多营养书是扫描版或混合版。

## 安装

运行：

```bash
bash scripts/setup_pdf_tools.sh
```

激活环境：

```bash
source .venv-pdf/bin/activate
```

## 使用

### 1. 先判断 PDF 类型

```bash
source .venv-pdf/bin/activate
python scripts/pdf_extract.py inspect "raw/营养书籍/202504 常见疾病膳食营养案例.pdf"
```

### 2. 抽取少量页面测试效果

```bash
source .venv-pdf/bin/activate
python scripts/pdf_extract.py extract "raw/营养书籍/202504 常见疾病膳食营养案例.pdf" --page-from 1 --page-to 5
```

### 3. 全书抽取到本地文件

```bash
source .venv-pdf/bin/activate
python scripts/pdf_extract.py extract "raw/营养书籍/202504 常见疾病膳食营养案例.pdf" --output "/tmp/常见疾病膳食营养案例.txt"
```

### 4. 把识别结果导出到本地派生层

```bash
source .venv-pdf/bin/activate
python scripts/pdf_extract.py cache "raw/营养书籍/202504 常见疾病膳食营养案例.pdf"
```

### 5. 作为本地后台长任务运行

如果文件页数较多，或你希望尽量减少 Agent 监控调用，优先使用：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\start_local_derive_job.ps1 "raw\营养书籍\202504 常见疾病膳食营养案例.pdf"
```

默认行为：

- 本地后台持续运行
- 进度写入 `.derived/job_runs/<job_id>/progress.json`
- PDF 默认每处理 `10` 页更新一次进度
- 任务结束后保留最终状态、标准输出和标准错误日志

查看轻量状态：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\check_local_derive_job.ps1 -JobId <job_id>
```

如果要修改页数进度步长：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\start_local_derive_job.ps1 "raw\营养书籍\202504 常见疾病膳食营养案例.pdf" -ProgressEveryPages 5
```

默认会写入：

- `.derived/pdf_extract/raw/营养书籍/202504 常见疾病膳食营养案例/full.auto.md`
- `.derived/pdf_extract/raw/营养书籍/202504 常见疾病膳食营养案例/full.auto.json`

其中：

- `.md`：适合人工阅读和直接喂给后续整理流程
- `.json`：保留页码、识别方式、统计信息和逐页文本，适合程序复用

虽然命令名仍然叫 `cache`，但输出目录已经按“长期保留的派生层”来使用，不再把它理解成一次性临时缓存。

- 单书 ingest 完成后，不清空、不删除对应 PDF 导出结果
- 后续子 agent 重跑、主 agent 串行补充共享知识点页、来源页复核时，都可以继续引用这些导出结果
- 只有当原 PDF 发生变化，或你明确决定重跑识别策略时，才需要用 `--force` 刷新导出结果

如果只是先测试部分页面：

```bash
source .venv-pdf/bin/activate
python scripts/pdf_extract.py cache "raw/营养书籍/202504 常见疾病膳食营养案例.pdf" --page-from 1 --page-to 5
```

对应会生成类似：

- `.derived/pdf_extract/raw/营养书籍/202504 常见疾病膳食营养案例/p0001-p0005.auto.md`
- `.derived/pdf_extract/raw/营养书籍/202504 常见疾病膳食营养案例/p0001-p0005.auto.json`

重复运行同一参数时，如果源 PDF 没变，脚本会直接复用已有缓存；要强制重跑可加 `--force`。

## 推荐策略

- 默认用 `--strategy auto`
- 如果确定是纯扫描版，可显式使用 `--strategy ocr`
- 如果确定是纯文字版，可显式使用 `--strategy text`
- 书籍正式 ingest 前，优先先跑一次 `cache`，避免后续反复 OCR

## 对 Ingest 的建议用法

1. `inspect` 看书是 text / scan / hybrid
2. 先抽前 5-10 页确认效果
3. 用 `cache` 把需要的页面范围或全书结果落到 `.derived/pdf_extract/`
4. ingest 时优先读取对应缓存的 `.md` / `.json`
5. ingest 完成后继续保留 cache，供后续复核、补充和主 agent 串行合并时参考
6. 用抽取结果回写 `source/` 和 `wiki/`

## 低调用建议

- 本地 OCR / 文本抽取持续运行，不会直接增加 Agent 调用费用
- 增加费用的是 Agent 频繁读取日志、反复解释中间状态
- 因此长文件默认推荐：
  - 本地程序高频写小型进度文件
  - Agent 只在异常、卡住、或人工要求时读取一次状态
  - 优先看 `progress.json`，尽量不看整份大日志

## 关联

- [[Ingest工作流]]
- [[串行Ingest队列工作流]]
