# 多格式文档处理与办公 Agent 设计文档

| 项目项 | 内容 |
|---|---|
| 文档版本 | 1.1 |
| 文档状态 | MVP 架构设计基线 |
| 日期 | 2026-11-15 |
| 上游文档 | `Requirements.md` v1.1 |
| 设计范围 | 系统架构、Agent 编排、文档处理、接口、数据库、前端、测试与运行 |

## 1. 文档目的

本文将已确认的 MVP 需求转化为可实现、可测试的系统设计，回答以下问题：

1. 系统由哪些进程和模块组成，各自负责什么。
2. Agent 如何理解任务、判断歧义、选择工具、验证并修复结果。
3. Word、Excel、PPT、PDF、CSV、Markdown、TXT 和图片如何解析、转换、合成、生成和验证。
4. 如何用 Job DAG 表达编辑、转换、模板生成、从零生成和图片合成之间的依赖。
5. API 与 SSE 如何表达任务、文件角色、澄清、Job 依赖、执行和结果状态。
6. SQLite 与本地文件系统如何保存任务、Job DAG、模板诊断、快照、事件、中间产物和最终产物。
7. 前端如何呈现文件角色、依赖时间线、模板映射、多格式预览和结果血缘。
8. 如何验证核心功能、转换保真、生成结构、视觉质量、安全边界和性能目标。

本文档不替代 `Requirements.md`。产品行为和验收要求以需求文档为准，本文档描述满足这些要求的技术方案。

## 2. 设计原则

1. **原件不可变**：上传文件只读；所有修改写入新工作副本和新结果文件。
2. **模型不直接碰文件**：模型只能规划和选择受控工具，不能生成任意执行代码或获得真实文件路径。
3. **确定性优先**：常规文档操作由确定性工具完成，模型负责理解、规划和解释。
4. **验证后才能发布**：结果先进入暂存区，完成结构和视觉验证后才登记为可下载产物。
5. **Job 级隔离与显式依赖**：每个交付型 Job 只声明一个目标产物或有序逻辑结果集，纯读取 Job 可以不产生产物；独立 Job 互不阻塞，依赖 Job 仅通过已发布产物 ID 和哈希连接。
6. **状态可恢复**：任务、事件和产物状态持久化；进程异常后可识别中断并恢复稳定状态。
7. **过程可解释**：向用户展示计划、工具步骤、变更、警告和验证证据，不展示原始思维链。
8. **本地优先**：单用户、本机存储、本机渲染；只有完成任务所需的必要内容发送到外部 AI 服务。
9. **通过约束获得自主性**：清晰任务自动执行，关键歧义先澄清，执行预算和修复轮次均有硬上限。
10. **转换必须显式**：只允许转换注册表中的源到目标组合，每个组合绑定保真级别与验证器，不做隐式近邻格式替换。
11. **生成结构可检查**：模板标记和从零生成规格必须编译为结构化任务，文件存在不能替代字段、数量、结构和版式验证。
12. **依赖失败只影响后继**：前驱失败或警告沿 DAG 精确传播，不得把无关分支降级，也不得用半成品继续下游。

## 3. 已确认技术决策

| 领域 | 决策 |
|---|---|
| 总体技术栈 | Python 3.11 + FastAPI 后端；React + TypeScript + Vite 前端 |
| Python 包管理 | `uv` |
| 前端包管理 | `pnpm` |
| 数据库 | SQLite，WAL 模式；SQLAlchemy 2 + Alembic |
| 后台执行 | API 进程与单 Worker 进程分离 |
| 实时进度 | REST + SSE，持久事件与断线回放 |
| 模型接入 | OpenAI 兼容适配层，配置文本模型与视觉模型 |
| Agent 编排 | 阶段化状态机，不使用自由 ReAct 循环 |
| Job 调度 | 持久化 Job DAG、拓扑就绪检查、深度优先的上限校验；单 Worker 串行执行就绪 Job |
| Office 修改 | 原生库优先，受控 OOXML 补丁处理复杂结构 |
| Office 渲染与重算 | Microsoft Office COM |
| PDF 读取 | PyMuPDF 原生解析；扫描页使用多模态视觉模型 |
| CSV/Markdown/TXT | 受控文本解码、CSV 方言解析、数据表转换与安全文本重写 |
| 图片处理 | Pillow/pyexif 类受控解码与方向处理；多模态模型负责 OCR 和视觉分析 |
| 格式转换 | 版本化 Conversion Registry；每个转换对包含输入校验、转换器、保真元数据和验证器 |
| 模板生成 | 原生 OOXML 标记解析、模板诊断、字段映射和结构渲染 |
| 从零生成 | Document Generation Planner 将结构化规格交给格式专用构建器 |
| 文档表示 | 统一结构化快照与格式原生定位器，覆盖文本、表格、图片区域和模板标记 |
| 长文档检索 | 结构感知切片、SQLite FTS5、分层摘要 |
| 文件预览 | Word/PPT/PDF 渲染页面图片；Excel/CSV 展示结构化表格；MD/TXT 使用安全文本视图；图片展示缩略图 |
| 前端组件 | Ant Design 5 + 自定义主题 |
| 前端状态 | TanStack Query + Zustand + React Router |
| 页面布局 | 桌面三栏工作台 |
| 视觉方向 | 冷静蓝图，深海军蓝导航与钴蓝主操作 |
| 运行方式 | 原生 Windows 启动器；交付期 FastAPI 托管前端构建产物 |
| 测试 | Pytest、Vitest、Testing Library、Playwright |

## 4. 系统架构

### 4.1 运行时拓扑

```text
Browser
  |
  | HTTP / SSE (127.0.0.1)
  v
FastAPI API Process
  |-- Auth-free local session guard
  |-- Upload / preflight
  |-- Task and turn services
  |-- SSE event stream
  |-- Download and deletion services
  |
  | SQLAlchemy repositories
  v
SQLite (WAL) + Local Task Workspace
  ^
  | Atomic queue claim / status / event writes
  |
Single Worker Process
  |-- Agent Orchestrator
  |-- Job DAG Scheduler
  |-- Model Gateway
  |-- Tool Registry
  |-- Document / Text / Table / Image Adapters
  |-- Conversion Registry
  |-- Template Engine
  |-- Generation Planner
  |-- Validation Pipeline
  |-- Office COM Subprocesses
```

开发期由 Vite 提供前端开发服务器；交付期使用 React 构建产物，由 FastAPI 同源托管。

### 4.2 组件职责

| 组件 | 职责 | 明确不负责 |
|---|---|---|
| Web SPA | 上传、任务导航、对话、执行时间线、澄清、预览、下载 | 不直接访问本地文件路径，不保存密钥 |
| API 进程 | HTTP 接口、上传和预检、任务与轮次服务、SSE、下载、删除 | 不执行耗时文档修改或 Office COM |
| Worker 进程 | 领取任务、执行 Agent、调用工具、调度 Job、验证、修复、发布产物 | 不提供公网接口，不处理前端会话 |
| Agent Orchestrator | 状态机、意图识别、Job DAG 计划校验、预算、修复控制 | 不生成或执行任意代码 |
| Job DAG Scheduler | 校验 Job 数量/深度/环，计算就绪与阻塞状态，按拓扑串行执行 | 不解释用户意图，不修改计划 |
| Model Gateway | 统一规划、生成、视觉能力；结构化输出校验；记录调用用量 | 不直接读写文件 |
| Tool Registry | 注册工具、校验参数、解析产物 ID、限制工作区与预算 | 不接受模型给出的任意命令或绝对路径 |
| Document / Text / Table / Image Adapters | 解析和写回各格式、生成统一快照和格式定位器 | 不决定用户意图或任务范围 |
| Conversion Registry | 管理源→目标格式、保真级别、转换器和验证器 | 不猜测矩阵外组合 |
| Template Engine | 解析标记、诊断模板、映射数据并生成单一输出 | 不执行表达式、宏或脚本 |
| Generation Planner | 将结构化生成规格编译为 DOCX/XLSX/PPTX/MD/TXT/CSV 构建计划 | 不绕过转换 Job 直接制作 PDF |
| Renderer | Office COM 渲染、重算、目录更新、页面图片生成 | 不修改业务内容 |
| Validator | 完整性、指令断言、编码、表格、转换、模板、生成、公式、图表和视觉验证 | 不把未验证项目标记为通过 |
| Repository | 事务、查询、状态流转和事件持久化 | 不包含 Agent 决策 |

### 4.3 依赖方向

依赖只能从外层进入内层：

```text
api / worker
    -> application services
    -> domain models and interfaces
    -> infrastructure implementations
```

Agent、验证器和文件工具通过抽象接口依赖数据库、模型与文件存储，不直接依赖具体供应商 SDK。

### 4.4 推荐目录边界

```text
backend/
  app/
    api/
    application/
    agent/
    documents/
      text/
      tables/
      images/
    conversion/
    templates/
    generation/
    scheduling/
    validation/
    infrastructure/
    worker/
  migrations/
  tests/
frontend/
  src/
    app/
    components/
    features/
    lib/
    styles/
  tests/
scripts/
data/
```

顶层目录的具体实现可以调整，但 API、Agent、文档能力、基础设施和验证之间不得混成单个大模块。

## 5. Agent 设计

### 5.1 编排状态机

```text
intake
  -> preflight
  -> understand
  -> detect_file_roles
  -> ambiguity_gate
      -> awaiting_clarification
      -> compile_job_dag
  -> validate_job_dag
  -> schedule_ready_jobs
      -> waiting_dependency
      -> execute_job
          -> validate
              -> repairing (最多 2 轮)
              -> publish_artifact
      -> blocked
  -> update_dependents
  -> aggregate
  -> succeeded / partial_success / warning / failed / interrupted
```

任务内各处理单元拥有独立 `job`。DAG Scheduler 按依赖计算就绪队列；单 Worker 串行执行就绪 Job，避免 Office COM 和大型文档同时争用资源。一个 Job 可以引用零个或多个输入；交付型 Job 只声明一个目标产物或一个有序逻辑结果集，纯读取 Job 可以不声明文件产物。

### 5.2 意图与约束

理解阶段输出结构化对象，而不是自由文本计划：

```json
{
  "task_kinds": ["read | edit | convert | image_compose | template_generate | generate_from_scratch"],
  "goal": "用户目标的简短描述",
  "files": [
    {
      "file_id": "...",
      "candidate_roles": ["source_file | conversion_input | template | data_source | reference_image"],
      "selected_role": "template",
      "confidence": 0.96,
      "evidence": ["扩展名与模板标记检测"]
    }
  ],
  "outputs": [
    {
      "label": "清洗后的订单表",
      "format": "csv",
      "source_job_hint": "edit-orders"
    }
  ],
  "conversion_targets": [],
  "generation": {
    "requested": false,
    "source_file_ids": [],
    "structure": null
  },
  "required_operations": ["csv.transform", "document.convert"],
  "hard_constraints": ["标题一号黑体居中"],
  "assumptions": [],
  "clarification": {
    "required": false,
    "question": null,
    "suggested_answers": []
  }
}
```

该对象必须通过 Pydantic 校验。缺少关键字段、任务类型冲突、文件角色不确定且影响结果，或需要输出的任务缺少可执行目标文件规格时，不得进入 DAG 编排阶段。任务可以同时包含多类意图，但每个 Job 必须有单一主类型。

### 5.3 歧义门禁

以下情况必须触发针对性澄清或明确拒绝：

1. 未指定要修改的多个候选文件、幻灯片、工作表、CSV 区域、Markdown/TXT 章节或图片区域，且不同选择会产生实质差异。
2. 统计口径、汇总字段、缺失值规则或去重规则不明确。
3. 输出格式、转换对、保真要求、生成结构、目录层级或目标样式没有可执行标准。
4. 模板标记存在影响生成的诊断问题，或字段映射无法从模板和多数据源中可靠推断。
5. 从零生成没有来源且用户要求的事实无法从输入或明确假设得到支持。
6. 用户要求与文档实际结构冲突，例如要求修改不存在的章节。
7. 任务被判断为不支持或超出安全边界时明确拒绝，不通过澄清诱导用户选择不支持能力。

以下情况不触发确认：

1. 用户给出的样式、范围和操作足够明确。
2. 可以采用非实质性的排版默认值，并能在变更摘要中披露。
3. 任务只需读取，且不影响任何文件。

澄清会创建 `clarification` 记录，任务进入 `awaiting_clarification`。每个问题必须提供 2 至 3 个互斥选项，其中一个标记为推荐项并说明推荐原因，同时保留自由输入。用户回答后恢复同一轮次，不重新创建任务。

### 5.4 Job DAG 计划

理解结果由确定性的 Plan Compiler 编译为 Job DAG。每个 Job 包含：

```json
{
  "job_id": "generate-report",
  "job_type": "generate_from_scratch | edit | convert | template_generate | image_compose | read",
  "goal": "Job 级目标",
  "input_refs": [
    {"kind": "uploaded_file", "id": "..."},
    {"kind": "job_artifact", "job_id": "previous-job"}
  ],
  "depends_on": ["previous-job"],
  "output": {
    "format": "docx",
    "artifact_slot": "generated-docx"
  },
  "operation": {
    "tool": "document.generate",
    "arguments": {},
    "expected_effect": "可检查的预期结果"
  },
  "verification_checks": ["所有必需章节存在", "页面无溢出"]
}
```

计划只能引用上传 ID、Job ID、产物 ID、快照块 ID 和受控定位器，不能包含真实的绝对文件路径。工具注册表会再次验证每个参数和定位器。DAG 校验必须满足：

1. 1 至 20 个唯一 Job ID。
2. 依赖边深度不超过 3，引用不得悬空。
3. 无环；每个交付型 Job 的目标产物槽在轮次内唯一，纯读取 Job 可以不声明产物槽。
4. 转换 Job 的源→目标组合必须存在注册项。
5. 模板 Job 必须有恰好一个模板角色，且可引用零个或多个数据源。
6. 从零生成 Job 必须声明一个直接可构建的目标格式；PDF 目标必须拆为生成 Job 和后继转换 Job。

### 5.5 执行预算

| 约束 | 上限 |
|---|---|
| 单文件模型调用 | 12 次 |
| 单文件工具调用 | 30 次 |
| 单任务硬超时 | 15 分钟 |
| 验证失败后的修复轮次 | 2 轮 |
| 单轮 Job 数量 | 20 个 |
| 依赖边深度 | 3 |
| 队列长度 | 3 个任务 |
| 同时运行任务 | 1 个 |

模型请求的网络重试也计入调用预算。达到上限时，Worker 停止当前 Job，记录最后阶段、未完成项和建议，不继续扩大任务范围。

### 5.6 上下文与长文档检索

文档处理遵循以下顺序：

1. 从结构化快照生成目录、页面摘要和内容块索引。
2. 对短文档，将目录和全部内容块按模型上下文预算送入理解阶段。
3. 对长文档，先使用目录和 FTS5 召回候选片段，再按章节执行分层摘要。
4. 修改任务只给模型提供目标区域及必要上下文，不默认发送整份文档。
5. 回答中的来源定位直接来自快照定位器，不依赖模型自行编造页码。

来源片段最多占模型输入预算的 60%，其余预算保留给系统指令、用户要求、工具 Schema 和输出。

### 5.7 文档内容安全

1. 系统指令、用户指令和文档内容位于不同消息角色和不同结构化字段中。
2. 文档内容统一标记为不可信数据，不能产生工具调用权限。
3. 文档中出现的命令、链接、宏或“忽略之前指令”等内容只作为文本分析对象。
4. 工具结果也不能升级为系统指令；模型只能把工具结果用于当前任务。
5. 模型输出必须通过计划 Schema 和工具参数 Schema 校验后才能执行。

### 5.8 修复循环

验证器返回结构化失败项：

```json
{
  "code": "TEXT_OVERFLOW",
  "status": "failed",
  "severity": "error",
  "locator": "page:3/paragraph:18",
  "expected": "段落完整显示在当前页",
  "observed": "文字超出正文区域",
  "suggested_action": "缩小字号或调整段前段后"
}
```

修复阶段只能针对已定位失败项调整当前文件，不得借机扩展用户未要求的修改。达到 2 轮上限后，文件按影响标记为 `warning` 或 `failed`。

### 5.9 Job DAG 调度与失败传播

1. Plan Compiler 在写库前用 Kahn 算法校验环，并计算每个 Job 的依赖深度；超过 20 个 Job、深度超过 3、悬空依赖或重复目标产物时整轮拒绝。
2. Scheduler 只选择所有必要前驱均为 `succeeded` 或 `warning`、且对应产物已发布并校验哈希的 Job。单 Worker 按确定性的拓扑顺序串行执行，优先选择创建顺序更早的就绪 Job。
3. 前驱处于 `failed`、`interrupted` 或产物不可用状态时，后继转为 `blocked`；无关分支继续执行，不跟随失败分支。
4. 警告前驱可以驱动后继，但 `warning_codes` 和证据引用会写入后继 Job 的输入元数据，最终聚合时不能被清除。
5. Job 重试是新的 `attempt` 记录，不覆盖已发布产物。工具只能读取创建本次 attempt 时冻结的输入哈希。
6. Scheduler 的每次状态变化同时写入数据库和 `job.status` 事件；崩溃恢复后从数据库重新计算就绪、执行中、被阻塞和中断状态。
7. 若任务因执行器或应用异常中断且验证未完成，则保持 `interrupted`，不得按 `failed`、`partial_success` 或 `warning` 覆盖中断事实；否则没有任何可交付终态 Job 时为 `failed`，成功或警告与失败或阻塞并存时为 `partial_success`，并列出每个 Job 的可下载产物和阻塞链。

## 6. 文档平台设计

### 6.1 统一文档快照

所有读取和修改共享 `DocumentSnapshot`：

```json
{
  "schema_version": 1,
  "source_kind": "artifact | uploaded_file",
  "source_id": "...",
  "format": "docx | xlsx | pptx | pdf | csv | md | txt | png | jpeg | webp",
  "content_hash": "...",
  "metadata": {},
  "outline": [],
  "blocks": [
    {
      "id": "block-id",
      "kind": "heading | paragraph | table | cell | row | section | slide | shape | page | text_span | image_region | template_marker",
      "text": "规范化文本",
      "locator": {},
      "parent_id": null,
      "attributes": {}
    }
  ],
  "tables": [],
  "template_diagnostics": null,
  "warnings": []
}
```

定位器规则：

| 格式 | 定位信息 |
|---|---|
| DOCX | 段落索引、表格坐标、XML 路径、书签或样式标识 |
| XLSX | 工作表名称、单元格或区域坐标、表格范围 |
| PPTX | 幻灯片 ID、形状 ID、备注定位 |
| PDF | 页码、文本块坐标和阅读顺序 |
| CSV | 头部行标识、记录序号、列名或列序号、字符偏移 |
| Markdown | 标题路径、块序号、源码行号或字符区间 |
| TXT | 行号、段落/章节标识和字符区间 |
| PNG/JPEG/WebP | 图像宽高、OCR 区域、对象区域、页面序号和像素坐标 |

模板产物在同一快照中额外保存标记类型、原始标记、解析位置、目标字段、映射状态和诊断结果。图片快照必须记录 EXIF 方向转换后的逻辑方向，避免预览、转换和文档合成使用不同坐标系。

快照是 Agent 的语义视图，不替代原始 Office 文件。任何修改完成后都重新解析并生成新快照和新内容哈希。

### 6.2 Word

处理顺序：

1. 用 `python-docx` 读取段落、表格、样式和关系。
2. 对目录、节、页眉页脚、交叉引用等结构建立 OOXML 索引。
3. 常规文字、样式、段落和表格使用 `python-docx` 修改。
4. 库无法安全表达的结构使用受控 OOXML 补丁工具。
5. 用 Office COM 更新目录、字段和页码。
6. 导出 PDF，再用 PyMuPDF 渲染页面图片。
7. 执行结构断言、文本检查和页面视觉验证。

MVP 输出为已接受修改的干净 `.docx`，不创建修订痕迹。

### 6.3 Excel

处理顺序：

1. 用 `openpyxl` 读取工作簿结构、公式、样式和图表关系。
2. 使用结构化表头和数据区域建立快照。
3. 清洗、筛选、排序、分组和统计由受控数据处理工具完成。
4. 常规公式和基础图表由工具写入。
5. 用 Office COM 打开工作簿并重算。
6. 重新读取关键单元格和公式结果，检查图表引用。
7. 输出新的 `.xlsx`，原工作簿保持不变。

对于超过内存预算的大工作表，使用只读迭代模式读取，并在数据块层面执行统计。首版不处理跨工作簿关联、外部数据源、宏或 Power Query。

### 6.4 PPT

处理顺序：

1. 用 `python-pptx` 读取幻灯片、文本框、表格、图片、主题和备注。
2. 对形状、母版和复杂关系建立 OOXML 索引。
3. 常规文字、图片位置、幻灯片增删和重排由 `python-pptx` 修改。
4. 主题色、对齐、间距和标题正文一致性由版式工具统一处理。
5. SmartArt、动画、切换效果、媒体和嵌入对象默认保留；无法确认完整性时记录警告。
6. 用 Office COM 导出 PDF，再渲染为幻灯片图片。
7. 执行结构断言和逐页视觉检查。

### 6.5 PDF

处理顺序：

1. 用 PyMuPDF 提取文本、页面、坐标、阅读顺序和可识别表格。
2. 对扫描页或无有效文本层的页面渲染为图片。
3. 通过 Model Gateway 的视觉能力提取文字、表格和置信度。
4. 将识别结果写入快照并标注页码、区域和风险。
5. 对低置信度内容生成警告，不将不确定结果表述为确定事实。
6. 用户要求导出时，通过独立导出工具生成 `.txt`、`.md`、`.csv` 或 PNG/JPEG/WebP 页面图片；不支持直接导出为 XLSX。

PDF 原件始终只读，任何派生文件都必须标明来源 PDF 和页码。

### 6.6 CSV、Markdown 与 TXT

#### 文本解码

`TextAdapter` 对 `.csv`、`.md`、`.txt` 使用同一受控解码层：

1. 优先识别 UTF-8 BOM、UTF-16LE BOM 和 UTF-16BE BOM。
2. 无 BOM 时先执行严格 UTF-8 解码，不使用 `errors="replace"` 静默吞掉非法字节。
3. UTF-8 失败后把 GB18030 作为候选，并由检测置信度、字符分布和用户预览共同判定。
4. 低置信度、多种编码均可解码或结果含异常控制字符时要求用户确认。预检记录保存候选编码、置信度、检测依据和归一化警告。
5. 输出默认 UTF-8 无 BOM；用户明确指定目标编码时，仅允许写入 Requirements 中的受支持集合，并在发布前重新严格解码验证。

#### CSV

1. 解析器支持逗号、制表符、分号和竖线分隔，支持标准引号、转义引号、CRLF/LF 和多行字段。方言不确定且影响字段结构时澄清。
2. 使用结构化数据表保存列名、推断类型、记录序号和原始字符偏移；统计工具不依赖字符串拼接。
3. 缺失值、去重、筛选、排序、分组和汇总必须输出命中范围与规则。公式文本只作为字符串，不执行。
4. 写入由不可信文档或模型内容产生的单元格前，扫描以 `=`, `+`, `-`, `@` 开头的值。默认在逻辑值前添加安全转义并记录 `CSV_FORMULA_INJECTION_ESCAPED` 警告；只有用户明确要求原始公式语义时才保留，且仍不得在服务端执行。
5. 新 CSV 写入 staging，完成后重新解析并比较行数、字段数、关键统计和编码，再发布产物。

#### Markdown

1. 使用 CommonMark 兼容 AST 读取标题、段落、列表、表格、代码块和链接，同时保留安全原始块以支持未结构化重写。
2. 编辑只作用于定位块或章节；输出重新序列化时必须避免无意规范化所有空行和列表符号。
3. 预览通过服务端 AST 和前端白名单清洗，禁止原始 HTML 中的脚本、事件属性、iframe 和外部资源。
4. Markdown 转 TXT 时明确移除标记；转 DOCX/PPTX/PDF 时按标题层级、列表、表格和代码块执行固定基础映射并记录降级项。

#### TXT

1. 以行号、段落和字符偏移建立可逆定位，保留原始换行类型的归一化元数据。
2. 章节识别只作为提示，不凭空改写结构。重写后的文本通过字符区间、段落数和关键内容断言验证。
3. TXT 转 Markdown 时只保留内容与基础段落，不自动生成未经推断的标题；转 DOCX/PPTX/PDF 时使用明确的段落和分页规则。

### 6.7 图片

1. 图片在隔离子进程中执行 header 探测和实际解码；解码前检查声明的宽、高、格式和帧数，解码中执行总像素、边长、内存和 CPU 预算。仅接受单帧 PNG、JPEG、WebP。
2. 统一使用 EXIF transpose 生成逻辑图像，快照记录原始方向、逻辑方向和是否应用旋转。预览、转换和文档合成都使用逻辑图像。
3. 图片快照包含宽高、颜色模式、Alpha、ICC 或色彩空间摘要、DPI、透明比例、OCR 区域和视觉分析结果。原始像素不写入数据库。
4. OCR 和视觉模型只接收必要区域；低置信度文本必须保留区域、置信度和模型版本。OCR 结果不能成为系统指令。
5. PNG/JPEG/WebP 互转由 `image.convert` 执行。PNG/WebP 保留 Alpha；JPEG 输出默认在白色 RGB 画布上合成，允许用户指定纯色背景，并把透明比例和背景色写入转换元数据。
6. 图片合成 PDF 时一张图片对应一页，页面尺寸按图片逻辑像素和 DPI 计算并受页面上限约束；合成 DOCX 时一图一页，按可用页面宽高等比容纳、不裁切；合成 PPTX 时每图一张幻灯片，默认 16:9 等比居中、不裁切。用户可显式覆盖布局。
7. 图片输出重新解码验证 MIME、尺寸、颜色模式和透明度策略。MVP 不提供像素编辑、抠图或独立图片生成工具。

### 6.8 格式转换

`Conversion Registry` 是唯一允许的格式转换入口。每个注册项包含：

```json
{
  "key": "docx->pdf",
  "source_formats": ["docx"],
  "target_format": "pdf",
  "fidelity": "visual_high | content_high | structural_approx | lossy_declared",
  "converter": "office.export_pdf",
  "input_rules": ["single_published_artifact"],
  "validator": "validate.pdf_render_and_content",
  "version": 1,
  "enabled": true
}
```

支持矩阵与 Requirements 5.2 完全一致：

| 源 | 目标 | 实现要点 |
|---|---|---|
| CSV | XLSX | 结构化表格写入；记录类型推断和样式降级 |
| XLSX | CSV | 指定工作表/区域；公式使用缓存值或重算值并标明 |
| TXT/MD | 对方格式 | 固定结构映射并声明格式变化 |
| DOCX/XLSX/PPTX | PDF | Office COM 导出，检查页数和页面渲染 |
| DOCX | TXT/MD | 解析标题、段落、列表、表格并声明复杂对象降级 |
| PDF | TXT/MD/CSV | PyMuPDF/OCR 提取，保留页码、阅读顺序和置信度 |
| PDF | PNG/JPEG/WebP 页面图片 | 每页一个图片项，组成同一 Job 的有序逻辑结果集 |
| TXT/MD | DOCX/PPTX/PDF | 通过受控文档构建器执行基础排版 |
| CSV | DOCX/PPTX/PDF | 表格渲染、分页/缩放和超宽警告 |
| PNG/JPEG/WebP | PNG/JPEG/WebP | 受控图像转换，透明转 JPEG 使用背景合成 |
| 多张 PNG/JPEG/WebP | PDF/DOCX/PPTX | 顺序化图片合成，验证页数或幻灯片数 |

转换规则：

1. Plan Compiler 先查询 `(source, target)`；未注册组合返回 `UNSUPPORTED_CONVERSION`，不尝试模型自由重建。
2. 转换 Job 固化源产物哈希；工具只接收 artifact ID。转换器输出写入 staging，验证通过后才发布。
3. 内容保真转换至少验证可解析性、内容抽样和结构数量；视觉保真转换至少验证页数、页面渲染和空白页/异常裁切。
4. `PDF → Office`、Office 跨家族重建和 Office 直接转图片不注册路由，即使第三方工具偶然可做也不暴露。
5. PDF 是只读产物类型。转换后的 PDF 不注册编辑工具，后续只能读取、预览、下载或作为其他受支持转换的只读输入。

### 6.9 模板生成

#### 模板标记

MVP 固定四类标记：

| 标记 | 语法 | 适用格式 | 语义 |
|---|---|---|---|
| 命名值 | `{{field}}` | DOCX/XLSX/PPTX | 插入标量值；缺失必填值时阻止生成 |
| 重复区 | `{{#each items}}...{{/each}}` | DOCX 表格行、XLSX 行、PPTX 幻灯片块 | 按数据项重复结构 |
| 可选区块 | `{{#if flag}}...{{/if}}` | DOCX/XLSX/PPTX | 仅支持布尔值，不执行任意表达式 |
| 图片 | `{{image:field}}` | DOCX/PPTX 段落或形状；XLSX 单元格锚点 | 用图片字段替换占位符 |

该语法不是通用模板语言。嵌套、比较、算术、过滤器、路径函数和脚本均不支持；遇到时必须报告危险或不支持标记。

#### 解析与诊断

1. `template.inspect` 解析 OOXML 关系、段落/单元格/形状结构和标记，生成 `TemplateManifest`。
2. Word 标记可能被拆分到多个 run，解析器按逻辑段落重组后定位，但保存原始 run 范围，写回时不得破坏未标记文本格式。
3. XLSX 重复区必须以完整行作为最小重复单位；可选区块只能包含完整行或完整单元格，避免破坏合并单元格和公式区域。
4. PPTX 图片占位符使用标记文本或受控占位形状；重复区以完整形状组或幻灯片为最小单位。
5. 诊断结果使用稳定代码，例如 `TEMPLATE_MARKER_UNCLOSED`、`TEMPLATE_MARKER_DUPLICATE`、`TEMPLATE_FIELD_MISSING`、`TEMPLATE_EXPRESSION_UNSUPPORTED`、`TEMPLATE_IMAGE_TYPE_INVALID`、`TEMPLATE_OPTIONAL_UNIT_INVALID`。
6. 阻止级诊断产生澄清或使 Job 在生成前失败。允许级诊断可以继续生成但必须沿验证链进入最终警告。

#### 映射与生成

1. 每个模板 Job 恰好声明一个模板和零个或多个数据源；Agent 产出 `field_path -> data_source + selector` 映射。
2. 数据源可以是 CSV/XLSX 的字段、PDF/MD/TXT 的结构化提取、图片 OCR 或文档事实。映射不确定且改变结果时先澄清。
3. 渲染始终创建模板副本，不修改上传模板。生成后重新读取 OOXML，验证标记清零、重复数量、图片关系、可选区块和关键字段。
4. DOCX 更新目录/字段并渲染页面；XLSX 重算并验证关键单元格；PPTX 渲染逐页检查。验证失败只能修复受影响 Job，最多 2 轮。

### 6.10 从零生成

从零生成先编译为结构化 `GenerationSpec`，不是把一段自由文本直接交给文件写入器：

```json
{
  "target_format": "docx",
  "title": "季度经营分析报告",
  "source_refs": ["...", "..."],
  "structure": {
    "sections": [{"heading": "经营概况", "required_facts": ["..."]}],
    "tables": [],
    "slides": null
  },
  "images": [],
  "theme": {"name": "plain_business"},
  "constraints": ["8 页以内", "关键数字引用来源"],
  "verification_assertions": ["所有来源数字可追溯", "无占位文字"]
}
```

生成规则：

1. `Generation Planner` 根据目标格式产出 DOCX 章节/表格、XLSX 工作表/字段、PPTX 幻灯片大纲、MD/TXT 章节或 CSV 列定义。
2. 格式专用 Builder 只接受经过 Schema 校验的规格和数据，不执行模型生成的 Python、VBA、宏或任意公式脚本。
3. 有来源时，关键事实和数据必须带来源引用或结构化 evidence ID；来源不足时披露假设或澄清，不得编造引用。
4. 无输入文件时允许按用户明确规格生成空模板化内容，但不得把未提供的事实、图片或品牌素材宣称已生成。
5. 已有图片可以通过 `images[].source_ref` 和显式位置嵌入生成的 DOCX、XLSX 或 PPTX；PDF 中的图片来源先生成受支持格式再转换。MVP 不生成新图片。
6. 每个生成 Job 只产生一个直接目标格式。PDF 目标拆为生成 DOCX/XLSX/PPTX/MD/TXT/CSV 的后继转换 Job。
7. 多格式请求按目标拆为多个独立 Job；共享来源通过只读引用使用，一个 Job 失败不删除其他已发布产物。
8. 生成后执行结构解析、必需字段、数量、来源定位、图片位置和渲染验证。DOCX/PPTX 至少渲染全部代表页，XLSX/CSV 检查关键数据和嵌入图片，MD/TXT 检查结构和编码。

### 6.11 Office COM 运行规则

1. COM 只在 Worker 启动的受控子进程中执行，不在 API 进程或前端执行。
2. 每次调用设置独立超时，超时后终止对应的 Word、Excel 或 PowerPoint 进程。
3. 打开文档时关闭提示、链接更新和最近文件记录；宏格式在入口处已被拒绝。
4. Worker 串行使用 COM 资源，避免多个 Office 实例互相影响。
5. 上传深度预检和 Worker 渲染共享同一跨进程 Office Gate，任何 COM 子进程都必须在获得 Gate 后才能启动。
6. COM 失败时记录应用名称、阶段、退出码和清理结果，不吞掉异常。
7. 文档渲染结果与验证证据绑定到具体产物哈希，避免误用旧预览。

### 6.12 预览

1. Word：导出 PDF，按页生成缩略图和页面大图。
2. PPT：每张幻灯片生成缩略图和页面大图。
3. PDF：直接按页生成缩略图和页面大图。
4. Excel：提供工作表选择、行列范围和分页数据结构，不把表格转为不可检索的图片。
5. 页面图片使用 WebP，缩略图与大图分目录缓存。
6. 前端按需加载页面，不使用一次请求返回全部大图。
7. CSV：返回表头和记录分页，危险公式只作为文本展示；超出列宽时支持横向滚动，不一次发送全部行。
8. MD/TXT：返回清洗后的结构化文本块和源码定位，不渲染任意 HTML。
9. 图片：返回受控缩略图、尺寸、方向、Alpha、OCR 区域和转换摘要；大图按需加载。

## 7. 工具设计

### 7.1 工具调用协议

模型不得直接传入文件路径。每次调用使用统一信封：

```json
{
  "call_id": "uuid",
  "tool": "word.format",
  "tool_version": 1,
  "task_id": "uuid",
  "turn_id": "uuid",
  "job_id": "uuid",
  "job_type": "edit | convert | template_generate | generate_from_scratch | image_compose | read",
  "input_artifact_ids": ["uuid"],
  "input_upload_ids": ["uuid"],
  "output_slot": "artifact-slot",
  "arguments": {},
  "limits": {
    "timeout_seconds": 60,
    "max_output_bytes": 209715200
  }
}
```

工具结果：

```json
{
  "call_id": "uuid",
  "status": "succeeded | warning | failed",
  "output_artifacts": [],
  "observations": [],
  "warnings": [],
  "error": null,
  "metrics": {
    "duration_ms": 0,
    "bytes_in": 0,
    "bytes_out": 0
  }
}
```

### 7.2 工具目录

| 工具 | 输入 | 输出 | 主要边界 |
|---|---|---|---|
| `document.inspect` | 产物或上传 ID、格式 | 快照、结构元数据、定位器和警告 | 只读；所有格式共用入口 |
| `csv.transform` | CSV/XLSX 表、清洗/筛选/排序/汇总操作 | 新 CSV 或表格结果集 | 不执行公式；统计输出必须可复算 |
| `text.edit` | TXT 工作副本、字符区间或重写规格 | 新 TXT | 固定编码与换行策略 |
| `markdown.edit` | Markdown 工作副本、章节/块操作 | 新 MD | 保留未修改块结构 |
| `image.analyze` | 图片产物、区域和分析类型 | OCR、视觉描述、区域和置信度 | 只读；限制发送区域 |
| `image.convert` | 图片产物、目标格式、背景色 | 新 PNG/JPEG/WebP | 透明转 JPEG 必须有背景处理元数据 |
| `image.compose_document` | 有序图片列表、目标 PDF/DOCX/PPTX、布局规格 | 单一 PDF/DOCX/PPTX 产物 | 不裁切，页面或幻灯片顺序必须可验证 |
| `document.convert` | 源产物、已注册 source→target | 新目标产物 | 只调用 Conversion Registry，矩阵外拒绝 |
| `template.inspect` | 模板上传 ID、目标格式 | TemplateManifest、映射候选、诊断 | 只读；不执行标记 |
| `template.generate` | 一个模板、零个或多个数据源、映射和输出槽 | 新 DOCX/XLSX/PPTX | 不做任意表达式、宏或脚本 |
| `document.generate` | GenerationSpec、可选来源、目标格式 | 新 DOCX/XLSX/PPTX/MD/TXT/CSV | PDF 必须由后继转换 Job 产生 |
| `document.extract` | 快照块、区域 | 文本、表格、结构化片段 | 只读 |
| `word.edit` | DOCX 工作副本、受控编辑操作 | 新 DOCX 工作副本 | 不执行宏 |
| `word.format` | DOCX 工作副本、样式和版式操作 | 新 DOCX 工作副本 | 不伪造目录结果 |
| `excel.transform` | XLSX 工作副本、清洗/筛选/排序/汇总操作 | 新 XLSX 工作副本 | 不访问外部数据源 |
| `excel.chart` | XLSX 工作副本、数据范围和图表规格 | 新 XLSX 工作副本 | 图表引用必须可验证 |
| `ppt.edit` | PPTX 工作副本、幻灯片和形状操作 | 新 PPTX 工作副本 | 复杂对象默认保留 |
| `ppt.layout` | PPTX 工作副本、主题和对齐规则 | 新 PPTX 工作副本 | 不重建未支持的动画 |
| `pdf.read` | PDF 只读产物、页面范围 | 快照、文本、表格和置信度 | 不写回 PDF |
| `export.derived` | 快照或表格结果 | 注册矩阵允许的文本、表格或页面图片 | 原件保持不变 |
| `render.preview` | 产物 ID、页面范围 | 缩略图、页面图和元数据 | 只读渲染 |
| `validate.result` | Job 产物、预期断言、来源哈希、证据范围 | 验证结果 | 不自行修改文件 |

工具注册必须声明版本、支持的格式、参数 Schema、允许的资源上限和输出类型。未注册工具、版本不匹配或参数校验失败时，Orchestrator 立即拒绝调用。

## 8. 后端与任务执行

### 8.1 API 进程

API 负责：

1. 接收 multipart 上传，流式写入暂存目录并计算 SHA-256。
2. 验证扩展名、文件内容、压缩包结构、大小、格式可解析性和规模限制。
3. 创建、查询、删除任务和轮次。
4. 提供持久化对话、澄清和事件流。
5. 通过受控产物或结果组 ID 提供下载和预览，不暴露磁盘路径。

API 不在请求线程内执行 Word/PPT 渲染、OCR、模型规划或长文档转换。

### 8.2 Worker 进程

Worker 循环：

1. 在短事务中原子领取最早的 `queued` 任务。
2. 写入租约、启动时间和 `running` 状态。
3. 载入并校验当前轮次 Job DAG，重新计算就绪、等待前驱和被阻塞 Job。
4. 按确定性拓扑顺序串行执行就绪 Job；每个 Job 完成验证和发布后才解锁后继。
5. 每个阶段写入持久事件，包括 `job.waiting`、`job.started`、`artifact.ready` 和 `job.blocked`。
6. 完成或失败后释放租约并聚合任务状态。
7. 若无任务，使用带抖动的短轮询等待，不忙循环。

SQLite 事务使用 `BEGIN IMMEDIATE` 保护队列原子性。Worker 只存在一个实例，因此不引入分布式锁。

### 8.3 租约与崩溃恢复

Worker 定期写入任务心跳。启动时，任何 `running`、`waiting_dependency`、`validating` 或 `repairing` 且租约过期的任务都转为 `interrupted`，其正在执行的 Job 同样转为 `interrupted`。Scheduler 重新计算依赖事实并保留已发布结果：前驱已成功且产物有效的后继记录为可重新发起，必要前驱永久失败或产物不可用的后继转为 `blocked`；中断轮次不会自动续跑。用户必须明确选择原件或最新有效已发布工作副本/结果后重新发起，未验证 staging 文件和最后事件只保留用于诊断，不自动发布或复用。

### 8.4 事件传输

1. Worker 和 API 只将事件写入 `execution_events`，不依赖内存队列保证持久性。
2. API 在进程内维护一个共享事件读取器，每 250ms 从 SQLite 读取新增事件并广播给 SSE 订阅者。
3. 新 SSE 连接先回放 `after_event_id` 之后的事件，再订阅实时事件。
4. 事件 ID 使用全局单调递增整数；客户端使用 `Last-Event-ID` 或 `after_event_id` 续传。
5. 前端首次订阅使用游标 0；续传只使用同一任务事件流返回的游标。游标无法归属当前任务时返回 `EVENT_CURSOR_INVALID`，前端清空游标并重新同步任务详情。
6. SSE 每 15 秒发送心跳，连接断开不改变任务状态。
7. 普通进度事件按状态变化写入，重复心跳不写入高噪声事件。

### 8.5 文件与产物事务

1. 上传文件先写入 staging，校验和哈希通过后才创建任务。
2. 创建任务时把 staging 文件移动到 `data/tasks/{task_id}/input`，数据库记录相对路径。
3. 每个 Job 将输入复制或链接为只读输入视图，所有工具输出新副本；依赖输入记录源 artifact ID 与哈希快照。
4. 新产物先写入 `work/{turn_id}/{job_id}/attempt-{n}/staged`。
5. 验证通过后移动到 `artifacts` 并使用服务端 UUID 命名；中间产物同样登记 artifact 和 source lineage，不做匿名临时文件。
6. 数据库发布成功后才对下载接口可用；后继 Job 只能绑定已发布 artifact ID。
7. 启动时清理无数据库引用的 staging、staged 和临时预览文件，但不得删除已登记 artifact、验证证据或依赖链。

### 8.6 本地访问安全

1. 默认绑定 `127.0.0.1`，拒绝非 `localhost` 或 `127.0.0.1` 的 Host。
2. 生产构建同源提供前端和 API，不使用宽泛 CORS。
3. 页面首次从同源加载时，API 设置随机 `HttpOnly`、`SameSite=Strict` 的本地会话 Cookie。
4. 状态变更请求同时验证 `Origin`、本地会话 Cookie，并要求前端携带 `X-Doc-Agent-Request: 1`；不满足时返回 403。
5. 设置 CSP、`X-Content-Type-Options: nosniff` 和禁止 iframe 嵌入的响应头。
6. 下载和预览接口只接受产物或结果组 UUID，服务端解析已注册相对路径，不接受路径参数。
7. OOXML 解析限制压缩后大小、解压总量、文件条目数、XML 深度和外部实体。

## 9. API 设计

### 9.1 通用约定

- Base URL：`/api/v1`
- 数据格式：JSON；上传和下载使用文件流
- 时间：UTC ISO 8601
- ID：不可预测 UUID 字符串
- 分页：游标分页，不使用无上限全量返回
- 幂等：创建任务与新增轮次支持 `Idempotency-Key`
- 成功创建排队任务：`202 Accepted`
- 可同步完成的查询和状态变更：`200` 或 `204`
- 错误：稳定 `code`、可读 `message`、`details`、`request_id`

### 9.2 契约生成

FastAPI 与 Pydantic 是 HTTP 请求、响应和 SSE 事件的唯一契约源。构建流程执行：

1. 导出 `/api/v1/openapi.json`。
2. 使用 `openapi-typescript` 生成前端类型。
3. SSE 事件通过 Pydantic 判别联合生成 TypeScript discriminated union。
4. CI 检查生成文件与后端模型是否存在差异。

前端不得手写第二套 API 字段或状态枚举。生成文件可以提交，但其内容必须完全由后端契约派生。

### 9.3 端点

| 方法 | 路径 | 用途 | 主要响应 |
|---|---|---|---|
| `POST` | `/uploads` | 上传一个文件并执行预检 | `201 UploadRecord` |
| `GET` | `/uploads/{upload_id}` | 查询上传和预检状态 | `200 UploadRecord` |
| `DELETE` | `/uploads/{upload_id}` | 删除未消费的暂存文件 | `204` |
| `POST` | `/tasks` | 创建任务和首轮指令 | `202 TaskDetail` |
| `GET` | `/tasks` | 查询任务列表 | `200 CursorPage<TaskSummary>` |
| `GET` | `/tasks/{task_id}` | 获取任务、轮次、Job DAG、文件角色和最近事件 | `200 TaskDetail` |
| `POST` | `/tasks/{task_id}/turns` | 基于用户选定的工作副本或已发布结果发起新轮次 | `202 TaskDetail` |
| `GET` | `/tasks/{task_id}/events` | SSE 任务事件流 | `text/event-stream` |
| `POST` | `/tasks/{task_id}/clarifications/{clarification_id}/answer` | 提交澄清回答 | `202 TaskDetail` |
| `POST` | `/tasks/{task_id}/clarifications/{clarification_id}/cancel` | 取消需要澄清的轮次 | `200 TaskDetail` |
| `GET` | `/tasks/{task_id}/jobs/{job_id}` | 获取 Job、依赖、输入血缘、验证和产物 | `200 JobDetail` |
| `POST` | `/uploads/{upload_id}/template-inspection` | 启动模板标记解析与映射诊断 | `202 TemplateInspection` |
| `GET` | `/template-inspections/{inspection_id}` | 获取模板清单、诊断和映射候选 | `200 TemplateInspection` |
| `GET` | `/capabilities/conversions` | 获取版本化转换矩阵、保真级别和限制 | `200 ConversionMatrix` |
| `GET` | `/artifacts/{artifact_id}/download` | 下载单个结果或派生文件 | 文件流 |
| `GET` | `/artifacts/{artifact_id}/preview` | 获取预览元数据和缩略图索引 | `200 PreviewManifest` |
| `GET` | `/artifacts/{artifact_id}/preview/pages/{page}` | 获取单页大图 | 图片流或表格数据 |
| `GET` | `/result-groups/{result_group_id}/download` | 将多文件逻辑结果集打包下载 | ZIP 文件流 |
| `GET` | `/tasks/{task_id}/archive` | 下载所有允许交付结果 | ZIP 文件流 |
| `DELETE` | `/tasks/{task_id}` | 硬删除一个任务及其数据 | `202 DeleteOperation` |
| `DELETE` | `/tasks` | 硬删除所有任务及数据 | `202 DeleteOperation` |
| `GET` | `/health` | 健康检查与依赖状态 | `200 HealthStatus` |

### 9.4 上传

上传请求使用 `multipart/form-data`，每请求一个文件。文件名仅用于显示，不作为磁盘路径。

`UploadRecord` 至少包含：

```json
{
  "upload_id": "uuid",
  "original_name": "报告.docx",
  "format": "docx",
  "size_bytes": 123456,
  "sha256": "...",
  "status": "validated",
  "preflight": {
    "page_count": 12,
    "row_count": null,
    "slide_count": null,
    "text_encoding": null,
    "image": null,
    "template_candidate": true,
    "warnings": []
  },
  "expires_at": "2026-11-15T00:00:00Z"
}
```

深度预检由受控子进程执行，包括 Office 页面渲染或规模探测、CSV 方言和文本编码检测、图片像素和 Alpha 检查、模板标记浅层扫描；超时或无法验证的文件不得被用于创建任务。`text_encoding` 至少包含 `value`、`confidence`、`source` 和 `requires_confirmation`。`image` 至少包含逻辑/原始宽高、格式、方向、色彩模式和 `has_alpha`。`expires_at` 只适用于尚未绑定任务的 staging 上传；任务创建后的原件、轮次、模板诊断、中间产物和结果不自动过期。

预检阈值由服务端配置常量执行，不交给模型判断：每个任务 0 至 10 个上传文件、单文件 50 MB、Word/PPT 200 页或幻灯片、PDF 200 页、XLSX/CSV 10 万数据行、MD/TXT 2 MB、单图 4,000 万像素且最大边长 20,000 像素、单输出文件 200 MB、单轮 20 个 Job、依赖边深度 3。任何阈值变更都必须同步需求、API 能力说明和测试夹具。

### 9.5 创建任务

```json
{
  "upload_ids": [],
  "instruction": "从零生成一份包含执行摘要、指标表和风险清单的季度经营报告 DOCX，再转换为 PDF。",
  "output_hints": [
    {"format": "docx", "label": "季度经营报告"},
    {"format": "pdf", "label": "季度经营报告打印版"}
  ]
}
```

约束：

- `upload_ids` 为 0 至 10 个且全部已通过预检；0 个仅允许用于可以从用户指令独立满足的从零生成任务。
- 指令长度为 1 至 8000 个字符。
- `output_hints` 可选，只作为结构化提示；Agent 最终计划必须通过转换矩阵、Job 数量和依赖深度校验。
- 相同 `Idempotency-Key` 在 24 小时内返回同一任务。
- 任务创建成功后 upload 记录被标记为 consumed，不能在另一任务复用。

`TaskDetail.jobs` 至少返回 `job_id`、`job_type`、`status`、`depends_on`、`input_refs`、`target_format`、`dependency_state`、`result_artifact_id`、`result_group_id`、`result_artifact_ids`、`warnings` 和 `blocked_reason`。单文件结果使用 `result_artifact_id`；多文件逻辑结果集使用 `result_group_id` 和有序的 `result_artifact_ids`。任务详情必须能恢复完整 DAG，而不仅是线性事件列表。

新增轮次请求：

```json
{
  "instruction": "基于选中的第一季度结果继续修改正文行距。",
  "base_refs": [
    {"kind": "artifact", "id": "uuid"},
    {"kind": "uploaded_file", "id": "uuid"}
  ]
}
```

`base_refs` 可引用同一任务中的原件或已发布产物，不允许跨任务或引用 staged/deleted 产物。修改和转换轮次必须至少声明一个有效基准；纯读取追问可以不声明，仅继承任务对话上下文。界面默认选中最新有效基准，但提交前允许用户改选，并在任务详情中记录本次选择。

### 9.6 澄清

```json
{
  "answer": "修改第 2 个工作表的销售额列，按部门汇总金额。"
}
```

回答写入原澄清记录，并恢复同一轮次。取消澄清会将轮次标记为 `cancelled`，不产生文件修改。

### 9.7 SSE 事件

事件格式：

```text
id: 1042
event: job.status
data: {"seq":1042,"type":"job.status","task_id":"...","turn_id":"...","job_id":"...","timestamp":"...","data":{}}
```

核心事件类型：

| 事件 | 含义 |
|---|---|
| `task.queued` | 任务进入队列 |
| `task.started` | Worker 开始执行 |
| `plan.created` | Job DAG 计划建立 |
| `clarification.required` | 任务等待用户补充信息 |
| `job.waiting` | Job 等待一个或多个前驱 |
| `job.status` | Job 类型、状态和依赖状态变化 |
| `job.blocked` | 必要前驱失败或产物不可用，Job 被阻塞 |
| `template.diagnosed` | 模板诊断和映射摘要已生成 |
| `conversion.started` | 转换对、源产物哈希和目标格式已确定 |
| `conversion.finished` | 转换和转换后验证结束 |
| `tool.started` | 工具调用开始 |
| `tool.finished` | 工具成功、警告或失败 |
| `validation.finished` | 验证结果写入 |
| `artifact.ready` | 可预览或下载产物发布 |
| `turn.finished` | 当前轮次结束 |
| `task.finished` | 任务聚合状态结束 |
| `heartbeat` | 连接保活 |

事件 `data` 不得包含 API 密钥、完整文档文本、绝对路径、原始模型响应或内部提示词。

### 9.8 预览与下载响应

- 下载响应设置 `Content-Disposition`、准确的 `Content-Type`、`Content-Length` 和 `ETag`。
- 多文件逻辑结果集通过结果组下载接口返回 ZIP；ZIP 内的 `manifest.json` 固化文件顺序、显示名称、页号、来源和验证状态。
- 预览元数据返回产物 ID、页数或工作表摘要、缩略图索引、警告和内容哈希。
- CSV 预览返回表头、游标、列类型和危险公式标记；MD/TXT 返回清洗后的块和源码定位；图片返回受控缩略图、尺寸、方向和 OCR 区域。
- 页面图片设置基于产物哈希的长期缓存键；产物删除后缓存 URL 不得继续返回旧内容。
- Excel 页面接口返回结构化只读表格分页，不返回可执行 HTML。
- 服务端只根据 artifact 或 result group UUID 解析相对路径，任何文件名参数都只用于显示。

### 9.9 错误结构

```json
{
  "code": "PAGE_LIMIT_EXCEEDED",
  "message": "PDF 超过 200 页限制",
  "details": {
    "actual": 231,
    "limit": 200
  },
  "request_id": "uuid"
}
```

稳定错误码至少包括：

- `UNSUPPORTED_FILE_TYPE`
- `FILE_TOO_LARGE`
- `FILE_COUNT_EXCEEDED`
- `ENCRYPTED_FILE`
- `MACRO_FILE_REJECTED`
- `MALFORMED_FILE`
- `PAGE_LIMIT_EXCEEDED`
- `ROW_LIMIT_EXCEEDED`
- `TEXT_FILE_TOO_LARGE`
- `TEXT_ENCODING_UNCERTAIN`
- `INVALID_TEXT_ENCODING`
- `CSV_DIALECT_UNCERTAIN`
- `IMAGE_PIXEL_LIMIT_EXCEEDED`
- `IMAGE_DIMENSION_LIMIT_EXCEEDED`
- `IMAGE_DECODE_FAILED`
- `UNSUPPORTED_CONVERSION`
- `CONVERSION_VALIDATION_FAILED`
- `JOB_LIMIT_EXCEEDED`
- `JOB_DEPENDENCY_DEPTH_EXCEEDED`
- `JOB_DEPENDENCY_CYCLE`
- `JOB_INPUT_UNAVAILABLE`
- `TEMPLATE_DIAGNOSTIC_BLOCKED`
- `TEMPLATE_MAPPING_REQUIRED`
- `GENERATION_SPEC_INVALID`
- `QUEUE_FULL`
- `MODEL_UNAVAILABLE`
- `MODEL_OUTPUT_INVALID`
- `TOOL_TIMEOUT`
- `TOOL_FAILED`
- `VALIDATION_FAILED`
- `PATH_FORBIDDEN`
- `TASK_NOT_READY`
- `ARTIFACT_NOT_AVAILABLE`
- `RESULT_GROUP_UNAVAILABLE`
- `EVENT_CURSOR_INVALID`
- `IDEMPOTENCY_CONFLICT`
- `UPLOAD_NOT_FOUND`
- `UPLOAD_ALREADY_CONSUMED`

## 10. 数据库设计

### 10.1 关系概览

```text
tasks
  1--N task_turns
  1--N uploaded_files
  1--N jobs
  1--N result_groups
  1--N artifacts
  1--N execution_events

task_turns
  1--N messages
  1--N jobs
  1--N clarifications

jobs
  N--N jobs via job_dependencies
  N--N uploads/artifacts via job_inputs
  1--N tool_invocations
  1--N validation_results
  0..1--1 result_groups
  1--N artifacts

uploads
  1--N template_inspections

artifacts
  1--0..1 document_snapshots
  document_snapshots 1--N content_chunks

uploaded_files
  1--0..1 document_snapshots
```

### 10.2 `tasks`

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | TEXT PK | UUID |
| `title` | TEXT | 从首条指令生成的可读标题 |
| `status` | TEXT | queued/running/waiting_dependency/validating/repairing/awaiting_clarification/succeeded/partial_success/warning/failed/interrupted/deleting |
| `current_turn_id` | TEXT NULL | 当前有效轮次 |
| `aggregate_json` | JSON | 成功、警告、失败数量和风险摘要 |
| `lease_owner` | TEXT NULL | Worker ID |
| `lease_expires_at` | DATETIME NULL | Worker 租约 |
| `created_at` | DATETIME | 创建时间 |
| `updated_at` | DATETIME | 更新时间 |
| `started_at` | DATETIME NULL | 开始执行 |
| `finished_at` | DATETIME NULL | 最终状态时间 |

索引：`status, updated_at`、`created_at`。

### 10.3 `task_turns`

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | TEXT PK | UUID |
| `task_id` | TEXT FK | 所属任务 |
| `sequence` | INTEGER | 任务内轮次序号 |
| `instruction` | TEXT | 用户原始指令 |
| `task_kinds` | JSON | read/edit/convert/image_compose/template_generate/generate_from_scratch 的组合 |
| `status` | TEXT | queued/planning/awaiting_clarification/running/waiting_dependency/validating/repairing/succeeded/partial_success/warning/failed/interrupted/cancelled |
| `constraints_json` | JSON | 结构化约束和假设 |
| `plan_json` | JSON NULL | 版本化 Job DAG、文件角色、转换矩阵和生成规格引用 |
| `error_json` | JSON NULL | 失败信息 |
| `created_at` | DATETIME | 创建时间 |
| `started_at` | DATETIME NULL | 开始执行 |
| `finished_at` | DATETIME NULL | 结束时间 |

唯一索引：`task_id, sequence`。

### 10.4 `messages`

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | TEXT PK | UUID |
| `task_id` | TEXT FK | 任务 |
| `turn_id` | TEXT FK | 轮次 |
| `role` | TEXT | user/assistant/system_notice |
| `content` | TEXT | 用户可见文本 |
| `metadata_json` | JSON | 引用、澄清卡等结构化元数据 |
| `created_at` | DATETIME | 创建时间 |

### 10.5 `uploads` 与 `uploaded_files`

暂存上传记录和任务输入文件分开：

| 表 | 关键字段 |
|---|---|
| `uploads` | `id`, `original_name`, `stored_name`, `sha256`, `format`, `size_bytes`, `status`, `preflight_json`, `expires_at`, `created_at` |
| `uploaded_files` | `id`, `task_id`, `upload_id`, `original_name`, `stored_name`, `sha256`, `format`, `size_bytes`, `preflight_json`, `created_at` |

`uploaded_files` 只描述只读原件，不作为修改目标。工作副本和结果写入 `artifacts`。

### 10.6 `jobs`

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | TEXT PK | UUID |
| `task_id` | TEXT FK | 所属任务 |
| `turn_id` | TEXT FK | 所属轮次 |
| `plan_index` | INTEGER | DAG 内稳定顺序 |
| `job_type` | TEXT | read/edit/convert/template_generate/generate_from_scratch/image_compose |
| `goal` | TEXT | Job 级可读目标 |
| `status` | TEXT | planned/waiting_dependency/analyzing/profiling_template/converting/generating/modifying/validating/repairing/succeeded/warning/failed/blocked/interrupted |
| `dependency_state` | TEXT | ready/waiting/blocked；由 Scheduler 根据依赖计算并持久化 |
| `artifact_slot` | TEXT NULL | 交付型 Job 在轮次内唯一的目标产物槽；纯读取 Job 可为空 |
| `target_format` | TEXT NULL | 直接目标格式；读取 Job 可为空 |
| `execution_spec_json` | JSON | 转换对、模板映射、GenerationSpec 或编辑工具规格 |
| `repair_count` | INTEGER | 已修复轮次 |
| `attempt_count` | INTEGER | 执行尝试次数 |
| `model_call_count` | INTEGER | 模型调用预算使用量 |
| `tool_call_count` | INTEGER | 工具调用预算使用量 |
| `current_artifact_id` | TEXT NULL | 当前工作副本或中间产物 |
| `result_artifact_id` | TEXT NULL | 单文件最终可交付产物 |
| `result_group_id` | TEXT NULL | 多文件有序逻辑结果集 ID |
| `warning_codes_json` | JSON | 本 Job 及继承警告 |
| `error_json` | JSON NULL | 失败或阻塞原因和建议 |
| `started_at` | DATETIME NULL | 开始时间 |
| `created_at` | DATETIME | 创建时间 |
| `finished_at` | DATETIME NULL | 结束时间 |

部分唯一索引：`turn_id, artifact_slot`，仅约束非空 `artifact_slot`；查询索引：`task_id, plan_index`、`status, dependency_state`、`result_group_id`。

### 10.7 `job_inputs`

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | TEXT PK | UUID |
| `job_id` | TEXT FK | 消费输入的 Job |
| `input_kind` | TEXT | upload/artifact |
| `input_id` | TEXT | upload ID 或 artifact ID |
| `role` | TEXT | source/conversion_input/template/data_source/image/reference |
| `ordinal` | INTEGER | 同一 Job 内的输入顺序，图片合成必须稳定 |
| `frozen_sha256` | TEXT | 计划创建时冻结的输入哈希 |
| `metadata_json` | JSON | 文件角色、映射选择和提取范围 |

唯一索引：`job_id, input_kind, input_id`。执行前重新核对输入存在、状态和哈希；不一致时 Job 被阻塞。

### 10.8 `job_dependencies` 与 `job_attempts`

| 表 | 关键字段 |
|---|---|
| `job_dependencies` | `job_id`, `depends_on_job_id`, `required_status`, `created_at`；主键为 Job 对 |
| `job_attempts` | `id`, `job_id`, `attempt_no`, `status`, `model_call_count`, `tool_call_count`, `error_json`, `started_at`, `finished_at` |

`job_dependencies` 在图写入时完成环和深度校验。`job_attempts` 记录每次执行或修复尝试，不能覆盖已发布产物。`required_status` MVP 固定为 `published_success_or_warning`。

### 10.9 `template_inspections`

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | TEXT PK | UUID |
| `uploaded_file_id` | TEXT FK | 模板原件 |
| `format` | TEXT | docx/xlsx/pptx |
| `engine_version` | INTEGER | 标记解析器版本 |
| `status` | TEXT | queued/succeeded/warning/blocked/failed |
| `manifest_json` | JSON | 标记、重复区、图片占位、可选区块和结构定位 |
| `diagnostics_json` | JSON | 稳定诊断码、位置、严重度和建议 |
| `mapping_json` | JSON NULL | 字段到数据源/选择器的候选或确认映射 |
| `created_at` | DATETIME | 创建时间 |
| `finished_at` | DATETIME NULL | 完成时间 |

JSON 中不保存完整模板正文，只保存完成任务所需的标记和定位摘要。模板原件按任务隔离并由 `uploaded_files` 引用。

### 10.10 `result_groups` 与 `artifacts`

`result_groups` 表示一个 Job 的多文件有序逻辑结果集，例如 PDF 页面图片。单文件结果不要求创建结果组。

#### `result_groups`

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | TEXT PK | UUID |
| `task_id` | TEXT FK | 所属任务 |
| `turn_id` | TEXT FK | 所属轮次 |
| `job_id` | TEXT FK UNIQUE | 产生该结果组的 Job |
| `target_format` | TEXT | png/jpeg/webp 等统一目标格式 |
| `label` | TEXT | 用户可读结果组名称 |
| `manifest_json` | JSON | 文件顺序、显示名称、页号、来源和转换元数据 |
| `state` | TEXT | staged/published/failed/deleted |
| `created_at` | DATETIME | 创建时间 |
| `published_at` | DATETIME NULL | 发布时间 |

索引：`task_id, state`。结果组只能包含同一任务、同一 Job、同一目标格式的已发布产物。

#### `artifacts`

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | TEXT PK | UUID |
| `task_id` | TEXT FK | 任务 |
| `turn_id` | TEXT FK | 轮次 |
| `job_id` | TEXT FK NULL | 产生该产物的 Job |
| `kind` | TEXT | working/intermediate/result/preview/page_image/export |
| `format` | TEXT | docx/xlsx/pptx/pdf/png/jpeg/webp/csv/md/txt/zip |
| `relative_path` | TEXT | 任务工作区内相对路径 |
| `sha256` | TEXT | 内容哈希 |
| `size_bytes` | INTEGER | 文件大小 |
| `state` | TEXT | staged/published/failed/deleted |
| `is_latest_working` | INTEGER | 是否为当前工作副本 |
| `result_group_id` | TEXT NULL | 所属多文件逻辑结果集 FK |
| `metadata_json` | JSON | 页面数、文件名、源 artifact IDs、转换对、生成规格哈希、编码和预览索引 |
| `created_at` | DATETIME | 创建时间 |
| `published_at` | DATETIME NULL | 发布时间 |

索引：`task_id, kind, state`、`job_id, created_at`、`result_group_id`。

只读任务可以只产生 `messages` 和 `validation_results`，不强制生成 artifact。编辑、转换、模板生成、从零生成和图片合成 Job 必须至少发布一个符合 `artifact_slot` 的 result artifact。单文件结果直接绑定 `result_artifact_id`；PDF 拆页等多文件结果使用同一 `result_group_id` 表达有序逻辑结果集，下载接口生成带 `manifest.json` 的 ZIP。

### 10.11 `document_snapshots`

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | TEXT PK | UUID |
| `artifact_id` | TEXT NULL UNIQUE FK | 对应已发布产物；与 `uploaded_file_id` 二选一 |
| `uploaded_file_id` | TEXT NULL UNIQUE FK | 对应只读原件；与 `artifact_id` 二选一 |
| `format` | TEXT | docx/xlsx/pptx/pdf/csv/md/txt/png/jpeg/webp |
| `schema_version` | INTEGER | 快照版本 |
| `content_hash` | TEXT | 来源内容哈希 |
| `snapshot_path` | TEXT | 快照 JSON 的相对路径 |
| `metadata_json` | JSON | 目录、页数、工作表、幻灯片等摘要 |
| `created_at` | DATETIME | 创建时间 |

`artifact_id` 与 `uploaded_file_id` 必须恰好一个非空。上传原件快照用于纯读取 Job；产物快照用于编辑、转换和结果验证。快照不产生额外可下载产物。

### 10.12 `content_chunks`

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | TEXT PK | UUID |
| `snapshot_id` | TEXT FK | 文档快照 |
| `ordinal` | INTEGER | 阅读顺序 |
| `block_id` | TEXT | 快照块 ID |
| `text` | TEXT | 原始规范化文本 |
| `search_text` | TEXT | 用于 FTS 的文本 |
| `locator_json` | JSON | 页码、工作表、段落或形状定位 |
| `token_estimate` | INTEGER | 上下文估算 |

`content_chunks_fts` 使用 FTS5 外部内容表，启用 `trigram` tokenizer，以提高中英文子串检索能力。检索结果必须回到 `content_chunks` 获取原始文本和定位。

当前环境的 Python SQLite 3.45.1 已启用 FTS5 和 trigram tokenizer。由于 trigram 查询短于 3 个字符时无法稳定命中，检索层对 0 至 2 个字符的查询回退到参数化 `LIKE`，并将搜索限制在当前任务的快照内。

### 10.13 `clarifications`

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | TEXT PK | UUID |
| `task_id` | TEXT FK | 任务 |
| `turn_id` | TEXT FK | 轮次 |
| `question` | TEXT | 聚焦问题 |
| `suggested_answers_json` | JSON | 2 至 3 个互斥选项，每项包含 label、value、rationale；恰有一项 recommended=true |
| `answer` | TEXT NULL | 用户自由输入 |
| `status` | TEXT | pending/answered/cancelled |
| `created_at` | DATETIME | 创建时间 |
| `answered_at` | DATETIME NULL | 回答时间 |

### 10.14 `execution_events`

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | INTEGER PK AUTOINCREMENT | SSE 事件 ID |
| `task_id` | TEXT FK | 任务 |
| `turn_id` | TEXT FK NULL | 轮次 |
| `job_id` | TEXT FK NULL | Job |
| `type` | TEXT | 事件类型 |
| `severity` | TEXT | info/success/warning/error |
| `message` | TEXT | 用户可读摘要 |
| `payload_json` | JSON | 结构化事件数据，已脱敏 |
| `created_at` | DATETIME | 时间 |

索引：`task_id, id`。

### 10.15 `tool_invocations`

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | TEXT PK | UUID |
| `task_id` | TEXT FK | 任务 |
| `turn_id` | TEXT FK | 轮次 |
| `job_id` | TEXT FK | Job |
| `job_attempt_id` | TEXT FK | 执行尝试 |
| `tool_name` | TEXT | 工具名 |
| `tool_version` | INTEGER | 工具版本 |
| `attempt` | INTEGER | 当前 Job 内调用序号 |
| `request_json` | JSON | 已脱敏参数 |
| `result_json` | JSON | 结构化结果 |
| `status` | TEXT | running/succeeded/warning/failed |
| `duration_ms` | INTEGER | 耗时 |
| `created_at` | DATETIME | 创建时间 |

### 10.16 `validation_results`

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | TEXT PK | UUID |
| `task_id` | TEXT FK | 任务 |
| `turn_id` | TEXT FK | 轮次 |
| `job_id` | TEXT FK | Job |
| `job_attempt_id` | TEXT FK | 被验证的尝试 |
| `artifact_id` | TEXT NULL FK | 被验证产物；纯读取 Job 可为空 |
| `validator` | TEXT | 验证器名称 |
| `status` | TEXT | passed/warning/failed |
| `severity` | TEXT | info/warning/error |
| `summary` | TEXT | 用户可读摘要 |
| `evidence_json` | JSON | 断言、定位、观测值和建议 |
| `created_at` | DATETIME | 创建时间 |

纯读取 Job 的验证结果通过 `job_id`、来源快照和 `evidence_json` 记录回答或提取结论，`artifact_id` 为空，不创建伪造产物。

### 10.17 `model_invocations`

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | TEXT PK | UUID |
| `task_id` | TEXT FK | 任务 |
| `turn_id` | TEXT FK | 轮次 |
| `job_id` | TEXT FK NULL | Job |
| `job_attempt_id` | TEXT FK NULL | 执行尝试 |
| `role` | TEXT | plan/template_map/generate/vision/validate |
| `provider` | TEXT | 适配器名称 |
| `model` | TEXT | 模型名 |
| `status` | TEXT | succeeded/failed |
| `prompt_tokens` | INTEGER NULL | 输入用量 |
| `output_tokens` | INTEGER NULL | 输出用量 |
| `latency_ms` | INTEGER | 调用耗时 |
| `error_code` | TEXT NULL | 错误码 |
| `created_at` | DATETIME | 创建时间 |

不保存完整提示词或完整模型响应；需要审计时只保存摘要、Schema 版本和哈希。

### 10.18 `idempotency_keys`

| 字段 | 类型 | 说明 |
|---|---|---|
| `key_hash` | TEXT PK | `Idempotency-Key` 的哈希，不保存原始密钥 |
| `scope` | TEXT | create_task/task_turn |
| `request_hash` | TEXT | 规范化请求体哈希 |
| `response_resource_id` | TEXT | 已创建任务或轮次 ID |
| `created_at` | DATETIME | 创建时间 |
| `expires_at` | DATETIME | 24 小时后的过期时间 |

相同作用域和 Key 重放时，请求体哈希必须一致；不一致返回 `IDEMPOTENCY_CONFLICT`。

### 10.19 SQLite 运行配置

每个连接必须启用：

```sql
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 5000;
PRAGMA synchronous = NORMAL;
```

写事务必须短，不在事务内等待模型或运行 Office COM。所有 schema 变更通过 Alembic，启动时检查迁移版本。业务外键默认 `ON DELETE CASCADE`，文件系统删除由任务删除协调器单独保证。

## 11. Model Gateway

### 11.1 接口

```text
understand(context, schema) -> validated Intent
plan_dag(intent, capabilities, schema) -> validated JobDag
map_template(manifest, data_profiles, schema) -> TemplateMapping
generate_spec(context, output_schema) -> GenerationSpec
vision(images_or_regions, prompt, output_schema) -> VisionObservation
```

网关负责：

1. 选择当前角色对应的文本模型或视觉模型。
2. 注入供应商请求格式，不把供应商细节泄露给业务层。
3. 校验结构化输出和工具参数。
4. 记录调用数量、耗时和 token 用量。
5. 对 429、5xx 和网络错误执行受预算约束的短暂重试。
6. 对内容政策拒绝、上下文超限或 Schema 失败返回稳定错误码。

### 11.2 配置

建议环境变量：

```text
DOC_AGENT_DATA_DIR
DOC_AGENT_DB_PATH
MODEL_BASE_URL
MODEL_API_KEY
MODEL_TEXT_NAME
MODEL_VISION_NAME
MODEL_REQUEST_TIMEOUT_SECONDS
DOC_AGENT_MAX_MODEL_CALLS_PER_JOB
DOC_AGENT_MAX_TOOL_CALLS_PER_JOB
DOC_AGENT_TASK_TIMEOUT_SECONDS
OFFICE_RENDER_TIMEOUT_SECONDS
LOG_LEVEL
```

密钥只从环境或本机受限配置文件读取，不写入前端、数据库、事件和普通日志。

### 11.3 兼容策略

默认使用 OpenAI 兼容的聊天完成接口和结构化 JSON Schema。若供应商不支持原生工具调用，规划器仍只返回经过校验的计划对象，由本地 Orchestrator 执行注册工具；不使用供应商特有工具协议作为内部业务协议。

## 12. 前端设计

### 12.1 路由

| 路由 | 页面 |
|---|---|
| `/` | 重定向到最近任务或空白工作台 |
| `/tasks` | 任务工作台，默认创建/选择任务 |
| `/tasks/:taskId` | 当前任务三栏工作台 |
| `/privacy` | 外部 AI 数据处理说明 |

不设置登录页、用户设置页或管理后台。

### 12.2 三栏布局

```text
+----------------------+---------------------------+-----------------------------+
| Task Sidebar         | Conversation & Timeline   | Document & Validation       |
| 248 px               | min 420 px                | min 380 px / flexible       |
+----------------------+---------------------------+-----------------------------+
```

#### 左栏

- 产品标识、新建任务按钮
- 进行中任务和历史任务筛选
- 任务标题、格式摘要、状态和更新时间
- 删除任务入口
- 窄屏下转为 App Drawer

#### 中栏

- 当前输入 Dock，展示原文件、格式、大小、预检状态和角色标签：源文件、模板、数据源、参考图片、待转换文件
- 对话消息
- Agent 计划卡，展示任务类型、目标格式、转换对和生成方式
- Job DAG 执行时间线，展示前驱/后继、等待前驱、被阻塞和成功发布
- 工具步骤与验证摘要
- 模板诊断与字段映射摘要
- 歧义澄清卡
- 固定底部指令输入和提交按钮

中栏是用户控制和解释任务的主要区域，不显示原始思维链。

#### 右栏

- Word/PPT/PDF：页面缩略图、页码导航和大图预览
- Excel/CSV：工作表或数据表切换、分页、统计摘要和公式注入标记
- MD/TXT：安全文本块预览、标题导航和源码位置
- 图片：缩略图、尺寸、方向、Alpha、OCR 区域和转换说明
- 原稿/结果查看切换
- Job 依赖、输入来源、转换链和产物血缘
- 验证状态、转换保真、警告和定位
- 单 Job 下载、逻辑结果集下载包、中间产物下载、批量下载和预览刷新

右栏不实现并排差异高亮；MVP 只提供结果预览和规范的原稿查看。

### 12.3 视觉令牌

| Token | 值 | 用途 |
|---|---|---|
| `color.nav` | `#14233A` | 左栏导航背景 |
| `color.primary` | `#2457D6` | 主按钮、选中、链接 |
| `color.canvas` | `#F8FAFC` | 页面背景 |
| `color.surface` | `#FFFFFF` | 对话和预览面板 |
| `color.text` | `#1F2D42` | 主文本 |
| `color.textMuted` | `#6D7C91` | 次要信息 |
| `color.border` | `#DFE5ED` | 分隔线和输入边框 |
| `color.success` | `#18704A` | 验证通过 |
| `color.warning` | `#A35F12` | 警告和修复 |
| `color.danger` | `#C23B3B` | 失败和删除 |
| `radius.sm` | `4px` | 标签和紧凑控件 |
| `radius.md` | `8px` | 面板、卡片、弹层 |
| `space.unit` | `4px` | 间距基准 |

字体使用 `"Microsoft YaHei UI", "Segoe UI", sans-serif`。字号和行高保持稳定，不使用随视口缩放的字体，不使用负字距。

### 12.4 组件映射

| 区域 | 主要组件 |
|---|---|
| 应用外壳 | Ant Design `Layout`、自定义三栏 grid |
| 任务列表 | `List`、`Badge`、`Dropdown`、`Empty` |
| 上传 | `Upload.Dragger`、自定义 `FileDock` |
| 文件角色 | `FileRoleBadge`、角色选择和角色依据 Popover |
| 对话 | 自定义消息组件、`Avatar`、`Typography` |
| 时间线 | Ant Design `Timeline` 的 DAG 定制封装 `JobDagTimeline` |
| 澄清 | 自定义 `ClarificationCard`，含建议按钮和自由输入 |
| 模板诊断 | `TemplateDiagnosticPanel`、字段映射表、缺少数据提示 |
| 转换摘要 | `ConversionSummary`，显示 source→target、保真和损失项 |
| 状态 | `Tag`、`Alert`、`Progress` |
| 文档预览 | 自定义 `PageViewer`、`ThumbnailRail` |
| 表格预览 | Ant Design `Table` 的 CSV/XLSX 只读封装 |
| 文本/图片预览 | 自定义安全文本块渲染器、图片查看器和 OCR region overlay |
| 下载与删除 | `Button`、`Popconfirm`、`Modal` |
| 工具图标 | `@ant-design/icons`，每个图标按钮必须有 Tooltip 或可访问名称 |

卡片只用于重复任务项、澄清卡、文件项和模态内容。页面主体使用完整面板，不在一层卡片中嵌套另一层卡片。

### 12.5 前端状态

TanStack Query 管理：

- 任务列表和任务详情
- 上传和预检记录
- 轮次、Job DAG、文件角色、模板映射、产物、来源血缘和验证结果
- 预览元数据和页面 URL
- 健康检查状态

Zustand 管理：

- 当前选中任务和文件
- 面板大小、滚动位置和折叠状态
- 当前预览页码和原稿/结果视图
- 输入框草稿和建议澄清选择

SSE 事件处理：

1. 按事件 ID 去重。
2. 更新对应任务、Job、依赖状态和产物的 Query 缓存。
3. 将展示事件追加到当前轮次时间线。
4. `task.finished` 到达时刷新任务详情、产物和预览。
5. 连接中断时显示非阻塞状态并自动重连。
6. 事件到达顺序异常时重新拉取任务详情，不盲目重排。

### 12.6 交互流程

#### 上传与创建任务

1. 用户拖入 0 至 10 个文件；从零生成允许不选文件。
2. 每个文件独立显示上传、解析和预检状态。
3. 成功后显示候选角色和依据；模板文件显示浅层模板标记诊断状态。
4. 失败文件不能被选中提交，用户可以移除。
5. 用户输入指令后创建任务，前端进入 `/tasks/{taskId}`。
6. 清晰任务自动开始，不展示“确认计划”步骤；无法确定角色、编码、转换对或模板映射时进入澄清。

#### 等待澄清

1. 中栏显示一个 `ClarificationCard`。
2. 卡片提供 2 至 3 个互斥建议答案、一个推荐标识和对应原因，并保留自由输入。
3. 提交后按钮进入等待状态，任务恢复后自动替换为执行时间线。
4. 用户可以取消当前轮次，不修改文件。

#### 执行与验证

1. 以 Job DAG 展示状态，不把所有 Job 混成一个进度条；等待前驱、执行和验证时间分开。
2. 显示用户可理解的工具步骤，例如“解析模板标记”“执行 DOCX→PDF”“应用 Word 样式”“重算工作簿”“渲染页面”。
3. 每个 Job 显示输入来源、输出格式和父子关系；后继不能在前驱发布前显示为执行中。
4. 修复轮次明确显示第 1/2 或 2/2 轮。
5. 验证状态同时有文字、图标和颜色。
6. 失败或被阻塞项可展开查看阶段、原因、必要前驱、定位和建议。

#### 结果与下载

1. 每个成功 Job 的产物出现在结果区，展示预览、转换来源、验证摘要和依赖位置。
2. 生成后再转换时，同时提供中间产物和最终产物的下载入口，并显示父子关系。
3. 警告产物允许下载，但警告在下载按钮附近持续可见。
4. 部分成功任务可下载成功产物和批量 ZIP；被阻塞 Job 不显示伪造下载按钮。
5. 批量 ZIP 只包含允许交付的产物，并附带 `manifest.json` 说明 Job、依赖、转换对、文件状态、警告和验证摘要。
6. 多文件逻辑结果集先提供结果组摘要和顺序，再通过独立 ZIP 下载；单文件仍使用产物直接下载，不额外套一层压缩包。
7. 用户继续修改时，界面突出显示本次选中的原件或已发布结果，并允许在提交前改选；未选中有效基准的修改类请求不能提交。

### 12.7 响应式规则

| 宽度 | 行为 |
|---|---|
| `>= 1440px` | 左栏 248px，中栏 44%，右栏占剩余空间 |
| `1280px - 1439px` | 左栏 232px，中栏最小 420px，右栏可收缩 |
| `960px - 1279px` | 隐藏右栏为底部抽屉，左栏保留 |
| `< 960px` | 左栏转为抽屉，中央单栏；预览和任务历史均通过抽屉访问 |

所有面板必须独立滚动，固定输入区不得覆盖对话或结果。按钮、状态标签和文件名的长度必须受容器约束，不产生不可控横向撑开。

## 13. 错误与恢复

### 13.1 Job 级失败与依赖失败

一个 Job 失败时：

1. 保存失败阶段、错误码、可读原因、建议、输入哈希和最后工具调用。
2. 不发布该 Job 的 staged 产物，也不让任何后继引用。
3. 直接依赖该 Job 的后继转为 `blocked`，无关分支继续执行。
4. 任务完成后按 Job 终态聚合为 `partial_success`、`warning` 或 `failed`；被阻塞数量和依赖链进入摘要。

### 13.2 模型失败

- 瞬时错误在预算内重试。
- Schema 错误最多触发一次重新格式化，不重复执行工具。
- 上下文超限时缩减到结构目录和更小片段，再继续预算内调用。
- 内容政策拒绝或持续不可用时，Job 失败并说明依赖原因；确定性转换不因模型不可用而被错误标记为失败，除非该转换本身依赖模型 OCR。

### 13.3 Office COM 失败

- 记录应用、文件类型、操作和超时。
- 终止对应子进程并清理临时锁文件。
- 不把上一次成功预览当作本次产物预览。
- 可在不重复已经成功的内容修改的前提下重试一次渲染。

### 13.4 Worker 中断

- Worker 启动时扫描过期租约。
- 未完成任务标记为 `interrupted`。
- 保留已发布历史产物和原文件。
- 新轮次可以从最新已发布工作副本或原件重新开始，不自动复用未验证 staged 文件。

### 13.5 删除失败

删除任务时先进入 `deleting`，再幂等删除数据库和文件。若文件暂时被 Office 占用，任务保持 `deleting` 并返回可重试状态；数据库记录不能在文件仍可访问时提前消失。

### 13.6 转换、模板与生成失败

- 转换器不支持源文件实际结构或验证失败时，Job 失败并保留转换对、工具版本、源哈希和验证证据。
- 模板存在阻止级诊断时，Job 在执行生成前失败或进入澄清；不得输出含未解析标记的文件。
- 从零生成 Schema 无效、缺少目标结构或来源不足时，停止在规划阶段；文件构建失败时不把部分产物发布为成功。
- 前驱警告可以继续转换，但转换结果继承警告；前驱失败、被删除或哈希变化时后继立即阻塞。
- 一个生成或转换 Job 失败不删除其他分支的已发布产物，批量下载清单明确排除失败和被阻塞分支。

## 14. 安全与隐私

### 14.1 本地边界

- 应用只为本机单用户运行。
- 不启用宽泛 CORS、远程访问或未授权文件读取。
- 除模型请求外，不主动访问文档中的外部链接或远程资源。

### 14.2 文件安全

- 扩展名白名单与现代 Office MIME/文件头双重校验。
- OOXML 压缩包执行条目数、解压总量、路径穿越和 XML 外部实体检查。
- 拒绝宏格式、加密文档、损坏文档和无法解析文档。
- 深度文档解析在 Worker 中执行；上传深度预检只能由 API 启动的隔离子进程完成，API 本身只负责暂存、浅层校验和状态协调。
- 所有工具路径由服务端映射，拒绝绝对路径、`..`、符号链接逃逸和跨任务 ID。
- 文本解码禁止静默替换非法字节；CSV 方言、编码和表头不确定时进入澄清，不把错列数据交给统计工具。
- CSV/XLSX 中的公式只作为数据或受控公式规格处理。由不可信内容生成公式形态的值时默认安全转义并记录警告，服务端从不计算公式。
- 图片在隔离子进程中按像素、边长、帧数、内存和 CPU 预算解码；超限或探测结果不一致时拒绝上传。
- 模板标记解析不得执行表达式、宏、脚本或外部关系；模板诊断必须检查重复、未闭合、危险关系和不可安全重复的结构。

### 14.3 数据最小化

- 模型调用只以文件、页面或内容块为单位发送必要内容。
- 图片只发送相关页面或区域。
- 任务删除清理原文件、模板诊断、Job DAG、中间产物、结果、快照、内容索引、页面图片、OCR 缓存、工具记录、模型用量记录和事件。
- 日志只记录 ID、事件类型、状态、耗时和脱敏摘要。

### 14.4 前端安全

- 所有下载和预览 URL 使用产物或结果组 UUID，并在服务端校验任务归属和发布状态。
- 不把本地路径渲染到 DOM。
- Markdown 内容只允许白名单格式，禁用内联脚本和外部资源。
- 用户文档内容展示时进行转义。
- CSV/XLSX 值始终作为文本单元格渲染，不把不可信值变成可点击公式、链接或 HTML。
- 图片 OCR 区域和文本摘要使用结构数据渲染，不执行文档中的 HTML 或命令。
- 不在浏览器持久化模型密钥或完整文档正文。

## 15. 测试设计

### 15.1 后端测试

| 层级 | 内容 |
|---|---|
| 单元测试 | 状态机、DAG 环/深度/就绪判定、预算、歧义门禁、路径守卫、Schema、状态聚合、错误映射 |
| 契约测试 | Pydantic 模型、OpenAPI、SSE 判别联合、Job/结果组 DTO、模板诊断、转换矩阵、工具参数和响应 |
| Repository 测试 | 事务、租约、幂等、Job 领取、依赖哈希、结果组顺序、产物血缘、级联删除、迁移 |
| 文本/表格测试 | 编码候选、CSV 方言与引号/多行字段、统计、公式注入、MD AST、TXT 定位 |
| 图片测试 | 格式探测、EXIF 方向、Alpha、像素上限、透明转 JPEG、图片合成顺序 |
| 文档工具测试 | DOCX/XLSX/PPTX 的读取、修改、定位和保留对象；PDF 的只读解析、提取、定位和警告 |
| 转换测试 | 每个注册转换对至少一个成功夹具和矩阵外拒绝夹具；验证保真、页数、编码和源哈希 |
| 模板测试 | DOCX/XLSX/PPTX 四类标记、跨 run 标记、重复行、图片占位、可选区块和诊断码 |
| 生成测试 | 无来源与多来源 GenerationSpec、六种直接目标格式、PDF 依赖转换和多 Job 隔离 |
| 验证器测试 | 文件重开、编码、表格、样式断言、公式复算、图表引用、页面渲染、未验证和继承警告 |
| 集成测试 | 真实 API、SQLite、Worker、DAG Scheduler、SSE、转换链、结果组 ZIP 清单和固定模型适配器 |
| Office 测试 | Windows 本机或 Windows CI 执行 COM 渲染、重算和目录更新 |

### 15.2 文档夹具

夹具必须覆盖：

- 中英文正文和标题
- 多节页眉页脚、目录、表格、公式和图文环绕
- Excel 公式、多个工作表、图表、缺失值和重复值
- PPT 多版式、标题正文、表格、演讲者备注、SmartArt 和动画保留
- 电子 PDF、扫描 PDF、跨页表格和低质量扫描页
- UTF-8/UTF-8 BOM/UTF-16LE/BOM/GB18030 文本、低置信度编码和非法字节
- 含逗号、双引号、多行字段、空表头、公式注入和不确定分隔符的 CSV
- Markdown 标题/列表/代码块/恶意 HTML，TXT 多章节和混合换行
- 带 EXIF 方向、Alpha、超大像素、损坏流和多种格式的图片
- DOCX/XLSX/PPTX 模板的字段、可选区、重复区、图片和各类诊断
- 无来源生成规格、多来源生成规格、超出目标结构预算的生成计划
- 支持矩阵的每个转换对、透明转 JPEG、低置信度 OCR 表格和矩阵外拒绝
- 恶意提示文本、超长路径、损坏压缩包和外链
- 多 Job DAG 中的独立成功、半成功分支、警告传播、前驱失败阻塞和无关分支继续

所有夹具使用固定哈希和预期定位器，测试不得依赖当前时间或真实网络。

### 15.3 前端测试

- Vitest 测试 Token、状态映射、Query 缓存更新和错误展示。
- Testing Library 测试上传角色、2 至 3 项澄清选项与推荐原因、DAG 时间线、等待前驱、模板映射、部分成功和删除确认。
- Playwright 测试创建任务、SSE 重连、CSV/MD/TXT/图片预览、依赖链、单 Job/中间产物/批量下载。
- Playwright 在 1280px、1440px、960px 和 375px 宽度截图。
- 视觉验证检查文字不溢出、面板不重叠、固定输入区不遮挡内容。

### 15.4 质量门槛

- Python：`ruff`、`pyright`、`pytest`
- TypeScript：`tsc --noEmit`、ESLint、Vitest
- 浏览器：Playwright
- 数据库：Alembic upgrade 从头迁移成功
- 接口：OpenAPI 生成后无未提交差异
- Office：Windows 本机 smoke test 通过
- 安全：路径穿越、恶意提示、宏文件、非法 Origin、CSV 公式注入、Markdown XSS、图片解码炸弹和模板外部关系测试通过

## 16. 性能与可靠性实现

### 16.1 性能目标

| 场景 | 目标 |
|---|---|
| 提交任务后的首次反馈 | 2 秒内返回任务接收或排队状态 |
| 常规单 Job 编辑或读取任务 | 3 分钟内完成 |
| 接近上限的单 Job 大任务 | 10 分钟内完成 |
| 长任务状态更新 | 至少每 5 秒一次；无新阶段时使用心跳保持连接 |
| Job DAG 等待与执行时间 | 分别可见；前驱等待不伪装成工具执行耗时 |

排队时间单独记录。外部模型、OCR 或 Office 渲染异常导致的超时必须体现在用户可见状态中。

### 16.2 性能措施

1. 上传请求流式写盘，避免一次读入内存。
2. 文档工具按页或数据块处理，避免整份大文档复制到模型上下文。
3. 就绪 Job 按确定性拓扑顺序串行执行，Office COM 资源独占。
4. SSE 只推送状态变化和必要进度，不记录高频无意义日志。
5. 任务列表、事件和 Excel 数据使用游标分页。
6. 缩略图、大图和内容快照按产物哈希缓存。
7. 前端只加载可见页面和当前任务数据。

### 16.3 可靠性措施

1. 文件写入使用 staging 和原子移动。
2. 产物发布必须同时满足文件验证和数据库发布。
3. Worker 使用租约和心跳，异常后标记中断。
4. API 与 Worker 不共享可变内存状态，SQLite 是事实源。
5. 事件写入失败不能静默丢失；任务需要降级为可见错误。
6. 同一任务不能同时被两个 Worker 领取。
7. Job DAG、输入哈希、尝试和产物发布在事务边界内保持一致；恢复后重新计算就绪与阻塞。
8. 每次上下文只加载当前 Job 所需输入和依赖产物，避免持有整张 DAG 的全部文件内容。

## 17. 运行与配置

### 17.1 开发运行

```text
uv sync
pnpm install
uv run alembic upgrade head
uv run uvicorn app.api.main:app --host 127.0.0.1 --port 8000 --reload
uv run python -m app.worker.main
pnpm --dir frontend dev
```

开发期 API 和 Worker 可分别观察日志，Vite 使用本地代理访问 `/api/v1`。

### 17.2 交付运行

启动器按以下顺序执行：

1. 校验 Python 环境和 Office 组件。
2. 检查数据目录、配置和数据库迁移。
3. 启动单 Worker 进程。
4. 启动 FastAPI，托管前端构建产物。
5. 打开或提示 `http://127.0.0.1:{port}`。
6. 退出时先停止 Worker，再停止 API，并清理超时 Office 子进程。

只使用一个用户可见入口，不要求用户手动打开多个终端。

### 17.3 数据目录

```text
data/
  app.db
  app.db-wal
  app.db-shm
  tasks/
    {task_id}/
      input/
      work/
        {turn_id}/
          {job_id}/
            attempt-{n}/
              input-view/
              staged/
      artifacts/
        result-groups/
          {result_group_id}/
      previews/
      snapshots/
      template-inspections/
  staging/
  logs/
```

数据库存相对路径，运行时以 `DOC_AGENT_DATA_DIR` 解析。启动时检查解析后的路径仍位于数据根目录内。

## 18. 可观测性

### 18.1 日志

后端使用结构化 JSON 日志，核心字段：

```text
timestamp
level
event
request_id
task_id
turn_id
job_id
job_type
dependency_depth
source_job_ids
artifact_id
tool
phase
duration_ms
error_code
```

日志不得包含完整文档正文、完整提示词、API 密钥、Cookie 值或文件绝对路径。

### 18.2 指标

MVP 至少记录：

- 任务创建数、成功数、部分成功数、失败数和中断数
- 各文档工具耗时与失败率
- 模型调用次数、token 用量和错误率
- 验证通过、警告和失败数量
- 每阶段排队、等待前驱、执行和验证耗时
- Job DAG 数量、深度、被阻塞数量和前驱失败传播数
- 转换对使用量、转换器版本、失败率和保真警告数
- 模板诊断阻止级/警告级数量与生成失败率
- 图片像素拒绝、OCR 置信度和图片转换次数
- SSE 重连次数
- COM 超时和清理次数

### 18.3 用户可见诊断

用户看到的诊断包括：

- 失败阶段
- 受影响 Job、输入文件和区域
- 可读原因
- 必要前驱、被阻塞后继和是否已发布其他分支
- 建议的下一步

不要求用户查看开发者日志。

## 19. 需求追踪

| 需求范围 | 设计落点 |
|---|---|
| 上传、格式和规模预检 | 8.1、9.3、9.4、14.2 |
| Agent 理解、歧义与工具选择 | 5.1 至 5.9、7 |
| 文件角色、任务类型与 Job DAG | 5.1 至 5.4、5.9、8.2、10.6 至 10.8 |
| 多轮与多 Job 独立/依赖处理 | 5.9、8.2、9.5、10.6 至 10.10 |
| 单文件与逻辑结果集交付 | 9.3、9.5、9.8、10.10、12.6 |
| CSV、Markdown、TXT 处理 | 6.6、7.2、9.4、14.2、15 |
| 图片读取、转换与合成 | 6.7、7.2、9.8、14.2、15 |
| 格式转换矩阵 | 6.8、7.2、9.3、9.9、15 |
| 模板诊断与生成 | 6.9、9.3、10.9、12.4、15 |
| 从零生成 | 5.2 至 5.4、6.10、7.2、10.6、15 |
| Word 处理 | 6.2、6.11、7.2 |
| Excel 处理 | 6.3、6.11、7.2 |
| PPT 处理 | 6.4、6.11、7.2 |
| PDF 读取 | 6.5、7.2 |
| 综合验证和 2 轮修复 | 5.8、10.16、15 |
| 预览和下载 | 6.12、9.8、12.2、12.6 |
| 本地持久化与删除 | 8.5、10、13.5、17.3 |
| SSE 时间线、DAG 和用户友好诊断 | 8.4、9.7、12.4、12.6、18.3 |
| 隐私、文本/图片/模板安全与路径隔离 | 5.7、8.6、13、14 |
| 性能、DAG 恢复与依赖一致性 | 5.5、5.9、8.3、16 |

## 20. 设计约束与后续边界

### 20.1 MVP 必须遵守

1. 不引入多用户认证、远程数据库或云端对象存储。
2. 不引入自由代码执行或模型生成的任意脚本。
3. 不引入跨任务向量库或长期知识库。
4. 不把 Office COM 放进 API 进程。
5. 不让前端直接访问文件系统。
6. 不执行转换矩阵外的格式重建或隐式替换。
7. 不修改、合并或重建既有 PDF；PDF 只能由注册转换生成。
8. 不执行模板表达式、宏、脚本或外部关系。
9. 不提供图片编辑、抠图或独立 AI 生图。
10. 不承诺 Word/PPT 像素级一致。
11. 不把未验证的 staged 文件发布为下载结果。

### 20.2 允许后续扩展但不预先实现

1. 将单 Worker 扩展为任务队列和多个受控 Worker。
2. 将 SQLite 迁移到 PostgreSQL。
3. 添加任务内临时向量检索。
4. 扩展 PDF→Office、Office 跨家族和更多高保真转换。
5. 添加上下文相关模板表达式、批量数据绑定和文档包生成。
6. 添加 PDF 编辑、合并、拆分和表单填写。
7. 添加受控图片编辑和独立图像生成。
8. 添加多用户、权限和远程存储。
9. 添加 Word 审阅与修订痕迹。
10. 添加 PPT 动画、SmartArt 和母版编辑。

## 21. 设计完成标准

当以下条件满足时，架构设计可进入实施计划阶段：

1. API、SSE 事件和错误结构无歧义。
2. 数据库表能表达任务、轮次、Job DAG、输入血缘、模板诊断、中间产物、快照、事件和验证。
3. 每种文档、文本、表格和图片格式的读、改、转换、生成、渲染和验证责任明确。
4. 前端三栏交互、视觉令牌、状态和响应式规则明确。
5. 测试夹具和端到端验收路径明确。
6. 转换矩阵、模板语法、生成规格、依赖传播、安全边界、执行预算、恢复策略和本地运行方式明确。
7. `Requirements.md` 中的每条核心验收场景都能映射到设计组件和测试层。
