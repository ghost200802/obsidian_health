---
type: concept
created: 2026-06-07
updated: 2026-06-07
tags: [知识管理, 工作流, Agent, Ingest, 队列]
---

# 串行 Ingest 队列工作流

## 目标

把 ingest 任务拆成**一轮一个来源对象**，避免一次塞入太多原始资料导致上下文失控。

这个队列现在分成两种模式：

- **补漏模式**：处理 `raw/` 中还没有进入 `source/` 的资料
- **书籍重跑模式**：对已经有 `source` 页、但提取不够细的书，逐本重新执行 [[Ingest工作流]]

对于书籍重跑，现在进一步拆成两个阶段：

- **缓存阶段**：先把整本 PDF 识别并导出到 `.derived/pdf_extract/`
- **Ingest 阶段**：只消费“已经缓存好”的书，严格按现有 [[Ingest工作流]] 回写 `source/` 和 `wiki/`

这里的 PDF 导出目录默认是**长期保留的参考层**：

- 不因单本书 ingest 完成而清空
- 不因一个批次结束而删除
- 后续子 agent 重跑、主 agent 串行补充共享知识点页、来源页复核时，都可以继续引用

## 核心原则

- **一轮只处理一个来源对象**：默认是一个 `raw/` 文件或一本书
- **完成判定不能只靠口头记录**：必须落到 `source/` 或 frontmatter 标记
- **每轮结束再取下一轮**：上一轮落盘、自检、提交后，再跑下一项
- **大文件也不扩任务边界**：即使是大书，也只围绕这一份来源产出

## 补漏模式

适用场景：`raw/` 里有新资料，但还没有对应 `source/source-*.md`。

### 完成判定

脚本 [`scripts/ingest_queue.py`](/Users/work/obsidian_health/scripts/ingest_queue.py) 会扫描 `source/source-*.md` 的这些字段：

- `raw_path`
- `raw_variants`
- `pdf`

判定规则：

1. 如果这些字段指向某个 `raw/` 文件，则该文件视为已 ingest
2. 如果 `raw_path` 指向某个 `raw/` 目录，则该目录下所有文件视为已被该来源页覆盖
3. 如果一个来源页覆盖多个原文件，这些文件都视为已 ingest

### 常用命令

```bash
python3 scripts/ingest_queue.py status
python3 scripts/ingest_queue.py list --limit 10
python3 scripts/ingest_queue.py next
python3 scripts/ingest_queue.py prompt
```

如果要强制处理某个指定文件：

```bash
python3 scripts/ingest_queue.py prompt --path "raw/私域运营课/老板发朋友圈，留下三大痕迹.pdf"
```

## 书籍重跑模式

适用场景：书已经有 `source` 页，但之前提取过浅，需要**逐本重新执行 ingest**。

这是你当前应该使用的模式。

### 适合你的执行方式

因为你有很多目录，而且单本书上下文很重，推荐把**一个文件夹**作为一个批次单位，例如：

1. `raw/营养书籍`
2. `raw/减肥营养书`
3. `raw/心理学`
4. `raw/高敏感人群`
5. `raw/商业职场`
6. `raw/个人成长`
7. `raw/教练思维`
8. `raw/中国营养学会`

原则是：

- 同一时间只推进**一个文件夹**
- 文件夹内部允许“缓存阶段”和“Ingest 阶段”并行
- 但每个阶段自身仍然是**单本串行**
- 不允许同一本书一边缓存、一边 ingest

### 书籍候选范围

默认从这些书籍型目录中自动识别候选：

- `raw/营养书籍`
- `raw/减肥营养书`
- `raw/心理学`
- `raw/高敏感人群`
- `raw/商业职场`
- `raw/个人成长`
- `raw/教练思维`
- `raw/中国营养学会` 中符合书籍特征的文件

脚本会自动排除明显不是“书”的资料，例如：

- 指南、规范、标准、共识、问答
- issue 封面或目录页
- 单页卡、行动条目、导航类文件
- 已在 `raw_variants` 中声明为同书变体的压缩版或格式变体

### 重跑完成判定

书籍重跑**不再**以“已有 `source` 页”作为完成条件，也不只看口头说明。

本轮详细重跑的完成标记是来源页 frontmatter 中同时写入：

```yaml
ingest_version: book-detailed-v2
raw_review_version: single-file-detailed-v1
```

含义分别是：

- `ingest_version: book-detailed-v2`
  表示这本书已经按当前书籍重跑标准完成了一轮正式 ingest
- `raw_review_version: single-file-detailed-v1`
  表示该来源页关联的 canonical raw 文件及其声明的变体，已经完成过详细的单文件 ingest 复核

只有这两个标识都满足，该书才会从重跑队列中消失。

### 常用命令

```bash
python3 scripts/ingest_queue.py books-status
python3 scripts/ingest_queue.py books-list --limit 10
python3 scripts/ingest_queue.py books-next
python3 scripts/ingest_queue.py books-prompt
```

如果只看某个文件夹：

```bash
python3 scripts/ingest_queue.py books-status --prefix raw/营养书籍
python3 scripts/ingest_queue.py books-list --limit 10 --prefix raw/营养书籍
python3 scripts/ingest_queue.py books-next --prefix raw/营养书籍
python3 scripts/ingest_queue.py books-prompt --prefix raw/营养书籍
```

### 缓存阶段命令

```bash
python3 scripts/ingest_queue.py books-cache-status --prefix raw/营养书籍
python3 scripts/ingest_queue.py books-cache-list --limit 10 --prefix raw/营养书籍
python3 scripts/ingest_queue.py books-cache-next --prefix raw/营养书籍
python3 scripts/ingest_queue.py books-cache-prompt --prefix raw/营养书籍
```

这些命令只关心一件事：这本书有没有标准全书缓存：

- `.derived/pdf_extract/.../full.auto.md`
- `.derived/pdf_extract/.../full.auto.json`

并且导出结果必须和当前源 PDF 的大小、修改时间一致，才算有效。

导出结果一旦有效，就默认持续保留，供后续多个阶段反复参考，而不是“用完即删”。

### 已缓存待 Ingest 阶段命令

```bash
python3 scripts/ingest_queue.py books-ready-status --prefix raw/营养书籍
python3 scripts/ingest_queue.py books-ready-list --limit 10 --prefix raw/营养书籍
python3 scripts/ingest_queue.py books-ready-next --prefix raw/营养书籍
python3 scripts/ingest_queue.py books-ready-prompt --prefix raw/营养书籍
```

这些命令只返回：

- 已经缓存完成
- 但还没有同时写入 `ingest_version: book-detailed-v2` 和 `raw_review_version: single-file-detailed-v1`

的书。

如果要强制指定某一本书：

```bash
python3 scripts/ingest_queue.py books-prompt --path "raw/中国营养学会/中国营养科学全书：全2册（第2版） (杨月欣，葛可佑) (Z-Library).pdf"
```

### 单本书重跑要求

把 `books-prompt` 或 `books-ready-prompt` 生成的提示词发给 Codex，然后严格按以下标准执行：

1. 只处理这一本书，不顺带碰第二本
2. 优先重写或大幅扩充现有 `source-*.md`，不要只补几行摘要
3. 至少覆盖目录、核心章节、关键模型、重要论据和高价值知识点
4. 只新增或更新与这本书直接相关的 `wiki/` 页面，并补齐双链
5. 完成后把 `ingest_version: book-detailed-v2` 和 `raw_review_version: single-file-detailed-v1` 一起写回来源页

## 双阶段并行规则

### 可以并行

可以，但要把并行拆成两层：

1. 阶段并行

- 终端 A：做“下一本未缓存书”的 PDF 全书缓存
- 终端 B：做“下一本已缓存书”的 ingest

2. 子 agent 并行

- 当某个文件夹里已经有多本“已缓存待 ingest”的书时，可以按书粒度并行
- 每本书单独分配给一个子 agent
- 每个子 agent 必须使用**完全独立的上下文空间**
- 每个子 agent 只拿到：这一本书路径、对应缓存路径、现有来源页路径、[[Ingest工作流]]
- 主 agent 在后续串行补充共享知识点页时，也可以继续引用这些导出结果

这意味着：

- 两个阶段可以同时跑
- Ingest 阶段内部也可以多本并行
- 但每个子 agent 处理的必须是**不同的一本书**
- 任何时刻都不要让同一本书同时处于“缓存中”和“ingest 中”
- 主 agent 只负责挑选任务、分发任务和回收结果，不负责把多本书塞进同一个上下文里

### 子 agent 调度方式

推荐由主 agent 先生成一个固定批次，再并行分发，避免多个子 agent 抢到同一本书。

例如：

```bash
python3 scripts/ingest_queue.py books-ready-list --limit 5 --prefix raw/营养书籍
```

主 agent 拿到这 5 本后：

1. 为每一本书启动一个子 agent
2. 给每个子 agent 分配唯一书目
3. 子 agent 只按 [[Ingest工作流]] 执行，不自行扩展范围
4. 子 agent 完成后，主 agent 复核并确认 frontmatter 双标识已经写入
5. 不清理该书对应的 PDF 导出结果，保留给后续复核和补充阶段继续使用

这套方式的目的不是让子 agent 自己决定做哪本，而是让主 agent 先切好批次，再并行执行。

### 并行写入约束

子 agent 并行时，最容易出问题的是多个 agent 同时修改同一个共享知识点页。

因此必须遵守下面的写入边界：

- 子 agent **可以直接修改**：
  - 自己这本书对应的 `source/source-*.md`
  - 自己新建的、明确只服务于这本书的 `wiki/` 页面
- 子 agent **不能直接并行修改**：
  - 已存在的通用知识点页
  - 索引页
  - 高复用的总纲页
  - 其他子 agent 已经在处理的共享 `wiki/` 页面

如果某本书需要补充已有共享知识点页，子 agent 的处理方式应改为：

1. 在本书来源页中正常记录该知识点与本书的关联
2. 如有必要，新建一个本书专属的过渡页面或在来源页中整理“建议补充内容”
3. 由主 agent 在所有子 agent 返回后，**串行**合并到共享知识点页

主 agent 在这个串行合并阶段可以继续直接参考：

- `.derived/pdf_extract/.../full.auto.md`
- `.derived/pdf_extract/.../full.auto.json`

原则很简单：

- 并行阶段优先产出“单书专属内容”
- 共享页面的最终合并始终由主 agent 串行完成
- PDF 导出结果始终保留，作为后续补充和复核的稳定参考层

### 推荐缓冲深度

不要把缓存阶段一次性跑太远。推荐：

- 永远只比 ingest 阶段领先 `1-3` 本

这样可以避免：

- 先缓存一大批，结果后面又改策略
- 一个文件夹还没吃完，就把别的文件夹也大量 OCR 了
- 管理上看不清哪些书已经真正完成

## 按文件夹推进的标准流程

以下流程以 `raw/营养书籍` 为例。

### 方案 A：单终端串行

适合你想把边界压到最稳的时候。

1. 先看文件夹总状态

```bash
python3 scripts/ingest_queue.py books-status --prefix raw/营养书籍
```

2. 取下一本未缓存书并缓存

```bash
python3 scripts/ingest_queue.py books-cache-prompt --prefix raw/营养书籍
source .venv-pdf/bin/activate && python scripts/pdf_extract.py cache "<该书路径>"
```

3. 取下一本已缓存书并 ingest

```bash
python3 scripts/ingest_queue.py books-ready-prompt --prefix raw/营养书籍
```

4. 完成后重复第 1 步，直到该文件夹：

- `Pending cache: 0`
- `Pending detailed re-ingest: 0`

5. 再切到下一个文件夹

### 方案 B：双终端流水线

适合你想提高吞吐，但又不想让单轮上下文失控。

终端 A 只做缓存：

```bash
python3 scripts/ingest_queue.py books-cache-status --prefix raw/营养书籍
python3 scripts/ingest_queue.py books-cache-prompt --prefix raw/营养书籍
```

然后执行：

```bash
source .venv-pdf/bin/activate && python scripts/pdf_extract.py cache "<该书路径>"
```

终端 B 只做 ingest：

```bash
python3 scripts/ingest_queue.py books-ready-status --prefix raw/营养书籍
python3 scripts/ingest_queue.py books-ready-list --limit 3 --prefix raw/营养书籍
```

然后把列表中的 3 本分别分给 3 个子 agent。每个子 agent：

- `.derived/pdf_extract/.../full.auto.md`
- `.derived/pdf_extract/.../full.auto.json`
- 严格按 [[Ingest工作流]] 执行
- 不直接并行改共享知识点页、索引页、总纲页
- 完成后不删除该书的 PDF 导出结果，保留给主 agent 后续串行补充时参考
- 完成后写回：

```yaml
ingest_version: book-detailed-v2
raw_review_version: single-file-detailed-v1
```

### 文件夹切换条件

只有当前文件夹同时满足以下条件，才切下一个文件夹：

1. `books-cache-status --prefix <文件夹>` 显示 `Pending cache: 0`
2. `books-status --prefix <文件夹>` 显示 `Pending detailed re-ingest: 0`
3. 该批次子 agent 提交的共享知识点页修改建议，已经由主 agent 串行合并完成

如果只满足第 1 条，说明 OCR 都做完了，但 ingest 还没吃完，不能切。
如果只满足第 2 条，通常说明完成判定不对，或者还有书没进入候选集，需要先排查。

## 当前推荐顺序

1. 选定一个文件夹，例如 `raw/营养书籍`
2. 用 `books-cache-status --prefix <文件夹>` 看还有多少本没缓存
3. 用 `books-ready-status --prefix <文件夹>` 看已有多少本可直接 ingest
4. 缓存阶段和 ingest 阶段在该文件夹内并行推进
5. 直到该文件夹缓存和 ingest 都清空
6. 再切到下一个文件夹

## 为什么这个流程能控制上下文

- 每轮只暴露一个来源对象给 Agent
- “补漏”和“重跑”分开，不会互相误伤
- 书籍重跑有独立版本标记，不会被旧的浅层 ingest 误判为已完成
- “缓存”和“ingest”分成两个队列，允许并行但不会混成同一轮上下文
- “正式 ingest 完成”和“raw 单文件详细复核完成”拆成两个 frontmatter 标识，完成判定更严格
- 子 agent 并行是按书粒度拆开的，每个 agent 只保留一本书的上下文
- `--prefix` 把任务边界锁在单个文件夹，避免跨目录来回切换
- 队列每次动态重算，不怕中途新增原书、补 source 页或替换变体文件

## 关联

- [[Ingest工作流]]
- [[PDF本地解析工具链]]
- [[Raw层]]
- [[Wiki层]]
