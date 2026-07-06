# Dify 投研知识库 PoC 样本数据（2026）

> 对应 [案例 1.1](../zh-CN/dify-banking-case-1.1-milvus-migration.md) 六类 Dataset 的 PDF 样本，覆盖 **英伟达、寒武纪、新易盛、贵州茅台** 及其所在行业。  
> 文件均为 **2026 年发布/披露** 的公开资料（内部研究库为标注「演示样本」的模拟文档）。

**相关文档**：[Milvus 迁移指南](../zh-CN/dify-banking-case-1.1-milvus-migration.md) · [Docker 数据库运维](../zh-CN/dify-docker-database-operations.md) · [案例 1.1 完整说明](../zh-CN/dify-banking-case-1.md)

## 目录

- [目录结构](#目录结构)
- [标的与行业映射](#标的与行业映射)
- [导入 Dify 操作步骤](#导入-dify-操作步骤)
- [数据来源说明](#数据来源说明)
- [文件清单](#文件清单)

## 目录结构

| 文件夹 | Dataset 类型 | 文件数 | 覆盖主题 |
|---|---|---|---|
| `macro/` | 宏观策略库 | 3 | 货币政策、全球/中国宏观展望 |
| `industry/` | 行业研究库 | 5 | AI算力/光模块/CPO、白酒、GTC2026 |
| `equity/` | 个股研报库 | 7 | NVDA、688256、300502、600519 |
| `filings/` | 财报公告库 | 11 | 年报、季报、10-K、业绩说明会 |
| `regulation/` | 监管政策库 | 2 | AI伦理审查、AI监管全景 |
| `internal/` | 内部研究库 | 4 | 演示样本（非真实券商内部报告） |

## 标的与行业映射

| 标的 | 代码 | 行业 | 相关文件 |
|---|---|---|---|
| 英伟达 | NVDA | AI算力/GPU | `filings/NVDA_*`、`equity/NVDA_*`、`industry/2026_英伟达GTC*` |
| 寒武纪 | 688256 | 国产AI芯片 | `filings/688256_*`、`equity/688256_*`、`industry/2026_国产算力*` |
| 新易盛 | 300502 | 光模块/CPO | `filings/300502_*`、`equity/300502_*`、`industry/2026_光*` |
| 贵州茅台 | 600519 | 白酒 | `filings/600519_*`、`equity/600519_*`、`industry/2026_中国白酒*` |

## 导入 Dify 操作步骤

> 前置条件：本地 Dify 已启用 `VECTOR_STORE=milvus` 且 `MILVUS_ENABLE_HYBRID_SEARCH=true`（须在**创建任何 Dataset 之前**生效）；控制台 **Settings → Model Provider** 已配置 Embedding `bge-m3` 与 Rerank `bge-reranker-v2-m3`。  
> 访问地址：http://localhost （或你的 Dify 域名） · Milvus 可视化：[Attu](http://localhost:8000)（认证 `root` / `Milvus`，见 [数据库运维文档](../zh-CN/dify-docker-database-operations.md)）

**两种导入方式**：

| 方式 | 适用场景 |
|---|---|
| **控制台手动** | 首次 PoC、熟悉 UI 配置 |
| **脚本批量** | 重复导入、CI/自动化（见 Step 1 可选 + Step 3 批量入库） |

### Step 0：确认环境

```bash
cd docker
# 确认 Milvus 与 API 正常
curl -f http://localhost:9091/healthz
docker compose ps api milvus-standalone
```

- [ ] Milvus 健康检查通过
- [ ] 控制台可登录（已完成安装则访问 `/signin`）
- [ ] Embedding / Rerank 模型在控制台可用
- [ ] 已获取 **Dataset API Key**：控制台 **Settings → API Keys → Create → Dataset API**（格式 `dataset-...`，写入 `config.json`）

**常见报错**

| 报错 | 原因 | 处理 |
|---|---|---|
| `401 UNAUTHORIZED` | `config.json` 中仍是占位符 `dataset-xxx...`，或未创建 Key | 在控制台创建 Dataset API Key，粘贴到 `scripts/banking-research/config.json` |
| `400 Provider ... does not exist` | Embedding/Rerank 模型与控制台不一致 | 打开 **Settings → Model Provider**，将 `config.json` 中的 `embedding_model*` / `reranking_*` 改为你已配置的模型（当前环境示例：通义 `multimodal-embedding-v1` + `qwen3-rerank`） |

---

### Step 1：创建 6 个 Dataset（按文件夹一一对应）

控制台路径：**知识库 → 创建知识库**（重复 6 次）

| 序号 | 本地文件夹 | Dataset 名称 | 权限建议 |
|---|---|---|---|
| 1 | `macro/` | 宏观策略库 | 全部团队成员 |
| 2 | `industry/` | 行业研究库 | 全部团队成员 |
| 3 | `equity/` | 个股研报库 | 全部团队成员 |
| 4 | `filings/` | 财报公告库 | 全部团队成员 |
| 5 | `regulation/` | 监管政策库 | 全部团队成员 |
| 6 | `internal/` | 内部研究库 | **部分成员**（模拟内评隔离） |

每个 Dataset 创建时统一配置：

| 配置项 | 值 |
|---|---|
| 索引方式 | **高质量** |
| Embedding 模型 | **bge-m3**（6 库必须一致） |
| 检索方式 | **混合检索（Hybrid Search）** |
| Rerank | **开启**，模型选 `bge-reranker-v2-m3` |
| Top K | **15** |
| 分数阈值 | **开启**，阈值 **0.52**（Rerank 后） |

创建完成后，在知识库列表记录每个 Dataset 的 **ID**（后续 API / 工作流绑定需要）。

**可选：脚本批量创建**

```bash
# 1. 复制并编辑配置（填入 dataset_api_key、模型 Provider）
cp scripts/banking-research/config.example.json scripts/banking-research/config.json

# 2. 创建 6 库 + 元数据 Schema（doc_kind / effective_date / ticker / industry / is_valid）
uv run --project api python scripts/banking-research/setup_datasets.py
# 状态写入 scripts/banking-research/config/datasets_state.json
```

---

### Step 2：声明元数据 Schema（每个 Dataset 各执行一次）

控制台路径：进入某个 Dataset → **设置 → 元数据 → 添加元数据**

为 **6 个 Dataset 均添加** 以下 5 个字段：

| 字段名 | 类型 | 说明 | 示例值 |
|---|---|---|---|
| `doc_kind` | 字符串 | 文档子类型 | `macro_report` / `equity_report` / `filing` 等 |
| `effective_date` | 时间 | 报告生效/披露日期 | `2026-04-24` |
| `ticker` | 字符串 | 股票代码（宏观/行业可为空） | `688256` / `NVDA` / `600519` |
| `industry` | 字符串 | 所属行业 | `国产AI芯片` / `光模块` / `白酒` |
| `is_valid` | 数字 | 是否有效（废止政策过滤用） | `1`（有效） |

`doc_kind` 与文件夹的推荐映射：

| 文件夹 | `doc_kind` 值 |
|---|---|
| `macro/` | `macro_report` |
| `industry/` | `industry_report` |
| `equity/` | `equity_report` |
| `filings/` | `filing` |
| `regulation/` | `regulation` |
| `internal/` | `internal_report` |

---

### Step 3：上传 PDF 并填写元数据

对每个 Dataset：**添加文件 → 上传 `docs/data/{文件夹}/` 下全部 PDF**

#### 3.1 分块设置（6 库统一）

| 配置项 | 值 |
|---|---|
| 分段模式 | **自定义** |
| 分段标识符 | `\n\n` |
| 最大分段长度 | **650** tokens |
| 分段重叠 | **120** tokens |
| 预处理 | 勾选「替换连续空格、换行、制表符」 |

#### 3.2 按文件填写元数据（上传后逐文档编辑）

**macro/**（`doc_kind=macro_report`，`ticker` 留空，`industry=宏观`）

| 文件 | effective_date | is_valid |
|---|---|---|
| `2026Q1_中国货币政策执行报告.pdf` | 2026-05-08 | 1 |
| `2026_全球宏观展望_KKR.pdf` | 2026-01-22 | 1 |
| `2026_中国宏观经济中期展望_浦银国际.pdf` | 2026-06-01 | 1 |

**industry/**（`doc_kind=industry_report`）

| 文件 | effective_date | industry | is_valid |
|---|---|---|---|
| `2026_国产算力趋势不可逆_东方证券.pdf` | 2026-05-09 | 国产AI算力 | 1 |
| `2026_英伟达GTC2026_AI基础设施_行业点评.pdf` | 2026-03-23 | AI算力/GPU | 1 |
| `2026_光互联CPO行业深度_通信.pdf` | 2026-06-07 | 光模块/CPO | 1 |
| `2026_光模块行业CPO趋势_IDC.pdf` | 2026-01-01 | 光模块/CPO | 1 |
| `2026_中国白酒市场中期研究报告_毕马威.pdf` | 2026-06-01 | 白酒 | 1 |

**equity/**（`doc_kind=equity_report`）

| 文件 | effective_date | ticker | industry | is_valid |
|---|---|---|---|---|
| `NVDA_英伟达_FY2026Q4财报点评_华龙证券.pdf` | 2026-02-27 | NVDA | AI算力/GPU | 1 |
| `NVDA_英伟达_FY27Q1业绩点评_信达证券.pdf` | 2026-05-25 | NVDA | AI算力/GPU | 1 |
| `688256_寒武纪_2026Q1更新报告_第一上海.pdf` | 2026-04-27 | 688256 | 国产AI芯片 | 1 |
| `300502_新易盛_2025年报点评_开源证券.pdf` | 2026-04-26 | 300502 | 光模块/CPO | 1 |
| `300502_新易盛_2026Q1快报点评_山西证券.pdf` | 2026-05-27 | 300502 | 光模块/CPO | 1 |
| `600519_贵州茅台_2026Q1财报点评_国信证券.pdf` | 2026-04-27 | 600519 | 白酒 | 1 |
| `600519_贵州茅台_淡季提价点评_中银证券.pdf` | 2026-04-02 | 600519 | 白酒 | 1 |

**filings/**（`doc_kind=filing`）

| 文件 | effective_date | ticker | industry | is_valid |
|---|---|---|---|---|
| `NVDA_英伟达_FY2026_10K.pdf` | 2026-02-25 | NVDA | AI算力/GPU | 1 |
| `688256_寒武纪_2025年年度报告.pdf` | 2026-03-13 | 688256 | 国产AI芯片 | 1 |
| `688256_寒武纪_2026年第一季度报告.pdf` | 2026-04-28 | 688256 | 国产AI芯片 | 1 |
| `688256_寒武纪_2026Q1资产减值准备公告.pdf` | 2026-04-28 | 688256 | 国产AI芯片 | 1 |
| `300502_新易盛_2025年年度报告.pdf` | 2026-04-24 | 300502 | 光模块/CPO | 1 |
| `300502_新易盛_2025年年度报告摘要.pdf` | 2026-04-24 | 300502 | 光模块/CPO | 1 |
| `300502_新易盛_2026年第一季度报告.pdf` | 2026-04-24 | 300502 | 光模块/CPO | 1 |
| `300502_新易盛_2025年度业绩说明会记录.pdf` | 2026-04-29 | 300502 | 光模块/CPO | 1 |
| `600519_贵州茅台_2025年年度报告.pdf` | 2026-04-17 | 600519 | 白酒 | 1 |
| `600519_贵州茅台_2025年年度报告摘要.pdf` | 2026-04-17 | 600519 | 白酒 | 1 |
| `600519_贵州茅台_2026年第一季度报告.pdf` | 2026-04-24 | 600519 | 白酒 | 1 |

**regulation/**（`doc_kind=regulation`，`ticker` 留空）

| 文件 | effective_date | industry | is_valid |
|---|---|---|---|
| `工信部75号_人工智能科技伦理审查与服务办法.pdf` | 2026-04-02 | AI监管 | 1 |
| `2026_中国人工智能监管法规全景解析_汉坤.pdf` | 2026-04-29 | AI监管 | 1 |

**internal/**（`doc_kind=internal_report`）

| 文件 | effective_date | ticker | industry | is_valid |
|---|---|---|---|---|
| `2026_内部_AI算力产业链配置策略_华东投研.pdf` | 2026-06-15 | — | AI算力 | 1 |
| `2026_内部_寒武纪深度跟踪_华东投研.pdf` | 2026-05-06 | 688256 | 国产AI芯片 | 1 |
| `2026_内部_新易盛光模块景气跟踪_华东投研.pdf` | 2026-05-28 | 300502 | 光模块/CPO | 1 |
| `2026_内部_白酒板块淡季策略_华东投研.pdf` | 2026-04-10 | 600519 | 白酒 | 1 |

#### 3.3 等待索引完成

上传后 Celery Worker 会异步建索引。在 Dataset 文档列表确认状态为 **已完成**；Milvus 中每个 Dataset 对应一个 Collection：`Vector_index_{dataset_id}_Node`。

**可选：脚本批量入库（32 个 PDF）**

元数据已预置在 [`manifest.json`](./manifest.json)，与 Step 3.2 表格一致：

```bash
# 先完成 Step 1 setup_datasets.py

# 预览命令（不实际上传）
uv run --project api python scripts/banking-research/ingest_batch.py --dry-run

# 批量上传 + 自动路由 doc_kind → dataset_id
uv run --project api python scripts/banking-research/ingest_batch.py
```

单文件入库示例：

```bash
uv run --project api python scripts/banking-research/ingest_document.py \
  docs/data/regulation/工信部75号_人工智能科技伦理审查与服务办法.pdf \
  --meta '{"doc_kind":"regulation","effective_date":"2026-04-02","industry":"AI监管","is_valid":1}'
```

---

### Step 4：Hit Test 验收（混合检索 + Rerank）

在每个 Dataset 内打开 **召回测试**，用以下 query 验证：

| Dataset | 测试 Query | 期望命中 |
|---|---|---|
| 宏观策略库 | `2026年中国货币政策基调是什么？` | 2026Q1 货币政策执行报告 |
| 行业研究库 | `国产算力 DeepSeek V4 适配进展` | 东方证券国产算力报告 |
| 个股研报库 | `寒武纪 2026Q1 净利润多少？` | 寒武纪 Q1 更新报告 |
| 财报公告库 | `新易盛 2026Q1 营收 83.38 亿` | 新易盛 Q1 季报 |
| 监管政策库 | `人工智能科技伦理审查 工信部 75 号` | 伦理审查办法 |
| 内部研究库 | `华东投研 AI算力产业链配置建议` | 内部策略样本 |

控制台确认：检索方式为 **混合检索**，Rerank 已启用，Top 结果 score ≥ 0.52。

```bash
# 或使用脚本批量 Hit Test
uv run --project api python scripts/banking-research/hit_test.py
```

---

### Step 5：部署投研知识库智能体（推荐）

一键生成并导入 **生产级 Workflow 应用**（13 节点：参数提取 → 改写 → 意图路由 → 分库 hybrid/Rerank + `is_valid=1` → 引用式回答 → 合规质检）：

```bash
# config.json 需填写 console_email；密码可用 --via-docker 跳过
uv run --project api python scripts/banking-research/generate_agent_app.py
uv run --project api python scripts/banking-research/deploy_agent_app.py --via-docker
```

部署成功后，用 [§7.4.1 十条演示输入](../zh-CN/dify-banking-case-1.md#741-演示输入案例10-条) 在 Console 预览中逐条验证（案例按 **已索引完成** 的文档编写；问「茅台 2025 年报全文」见边界案例 A）。

详见 [dify-banking-case-1.md §7.4–7.5](../zh-CN/dify-banking-case-1.md#74-投研知识库智能体生产应用)（含 **元数据如何区分政策/财报年份**）。

### Step 5（备选）：手动绑定工作流

创建 **Chatflow** 或 **Workflow** 应用时：

1. 添加 **知识检索** 节点
2. 绑定 **6 个 Dataset**（`retrieval_mode: multiple`）
3. 检索配置：混合检索 + Rerank，`top_k=15`
4. 元数据过滤（Manual）：`is_valid = 1`（过滤废止政策）
5. 可按 query 意图追加 `ticker` / `industry` 过滤（如「寒武纪业绩」→ `ticker=688256`）

简易 DSL：`scripts/banking-research/dsl/banking-research-rag.template.yml`。

---

### 导入检查清单

- [ ] 6 个 Dataset 均已创建，Embedding 均为 bge-m3
- [ ] 6 库检索均为 **hybrid_search + Rerank**，top_k=15，score_threshold=0.52
- [ ] 32 个 PDF 全部上传完毕，索引状态 **已完成**
- [ ] 每个文档已填写 `doc_kind`、`effective_date`、`ticker`（如有）、`industry`、`is_valid=1`
- [ ] Hit Test 通过（至少每库 1 条 query）
- [ ] Attu 中可看到 6 个 Milvus Collection（http://localhost:8000，认证 `root` / `Milvus`）

---

## 数据来源说明

- **公开资料**：巨潮资讯（cninfo）、深交所、SEC/NVIDIA IR、央行/工信部、券商研报（东方财富 pdf.dfcfw.com）等。
- **内部研究库**：`internal/` 下文件为 **PoC 演示用模拟文档**，内容基于公开业绩数据整理，不代表任何机构真实内部报告。

## 文件清单

### macro/

- `2026Q1_中国货币政策执行报告.pdf`
- `2026_全球宏观展望_KKR.pdf`
- `2026_中国宏观经济中期展望_浦银国际.pdf`

### industry/

- `2026_国产算力趋势不可逆_东方证券.pdf`
- `2026_英伟达GTC2026_AI基础设施_行业点评.pdf`
- `2026_光互联CPO行业深度_通信.pdf`
- `2026_光模块行业CPO趋势_IDC.pdf`
- `2026_中国白酒市场中期研究报告_毕马威.pdf`

### equity/

- `NVDA_英伟达_FY2026Q4财报点评_华龙证券.pdf`
- `NVDA_英伟达_FY27Q1业绩点评_信达证券.pdf`
- `688256_寒武纪_2026Q1更新报告_第一上海.pdf`
- `300502_新易盛_2025年报点评_开源证券.pdf`
- `300502_新易盛_2026Q1快报点评_山西证券.pdf`
- `600519_贵州茅台_2026Q1财报点评_国信证券.pdf`
- `600519_贵州茅台_淡季提价点评_中银证券.pdf`

### filings/

- `NVDA_英伟达_FY2026_10K.pdf`
- `688256_寒武纪_2025年年度报告.pdf`
- `688256_寒武纪_2026年第一季度报告.pdf`
- `688256_寒武纪_2026Q1资产减值准备公告.pdf`
- `300502_新易盛_2025年年度报告.pdf`
- `300502_新易盛_2025年年度报告摘要.pdf`
- `300502_新易盛_2026年第一季度报告.pdf`
- `300502_新易盛_2025年度业绩说明会记录.pdf`
- `600519_贵州茅台_2025年年度报告.pdf`
- `600519_贵州茅台_2025年年度报告摘要.pdf`
- `600519_贵州茅台_2026年第一季度报告.pdf`

### regulation/

- `工信部75号_人工智能科技伦理审查与服务办法.pdf`
- `2026_中国人工智能监管法规全景解析_汉坤.pdf`

### internal/（演示样本）

- `2026_内部_AI算力产业链配置策略_华东投研.pdf`
- `2026_内部_寒武纪深度跟踪_华东投研.pdf`
- `2026_内部_新易盛光模块景气跟踪_华东投研.pdf`
- `2026_内部_白酒板块淡季策略_华东投研.pdf`
