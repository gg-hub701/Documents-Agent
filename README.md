# 多格式文档处理与办公 Agent

本项目是一个本地优先、单用户的多格式文档处理与办公 Agent。目标是让用户通过自然语言和最多 10 个文档输入，完成文档读取、编辑、转换、模板生成与从零生成，并获得可预览、可验证、可下载的新文件。

当前仓库处于 MVP 分阶段实现中：

- 已完成 FastAPI、React/Vite、SQLite、Alembic 和 OpenAPI 基础。
- 已完成本地配置、数据目录守卫、健康检查、结构化 JSON 日志、上传 API 和任务 API。
- Worker、Agent 规划、文档处理、格式转换、模板、生成和完整前端工作台仍在后续任务中实现。

产品需求、技术设计和任务拆分分别以 [Requirements.md](Requirements.md)、[Design.md](Design.md) 和 [tasks.md](tasks.md) 为准。

任务执行状态统一维护在 [docs/task-tracking.md](docs/task-tracking.md)。该跟踪表以 [tasks.md](tasks.md) 为任务基线，按前置依赖展示待评审、进行中、待开始和阻塞任务；状态变化同步更新跟踪表，交付物与验收口径仍以 `tasks.md` 为准。

## 技术栈

- Python 3.11
- `uv`
- FastAPI、Pydantic 2、SQLAlchemy 2、Alembic
- SQLite WAL
- React、TypeScript、Vite、pnpm
- Pytest、Ruff、Pyright

## 环境要求

- Windows 10/11
- Python 3.11.x
- `uv`
- Node.js 20 或更新版本
- pnpm 11 或兼容版本
- Microsoft Office，用于后续 Word、Excel、PowerPoint 的渲染和重算能力

SQLite 随 Python 提供。Office 是后续文档渲染能力的外部依赖，当前健康检查只做本机安装探测，不会在 API 进程启动 COM。

## 目录结构

```text
backend/
  app/
    api/                 HTTP、Pydantic 契约、错误处理和路由
    application/         应用服务与用例编排
    infrastructure/
      db/                SQLAlchemy、Alembic 连接与模型
      office/            Office 依赖探测和后续 COM 适配
      uploads/           上传暂存与静默校验
    worker/              后台 Worker，后续阶段实现
  migrations/            Alembic 迁移
  tests/                 后端自动化测试
frontend/                React/Vite 前端
scripts/                 OpenAPI 等开发脚本
data/                    本地运行数据，不提交数据库和用户文件
docs/                    设计规格与实施记录
```

## 环境变量

从 `.env.example` 获取可配置项。常用变量如下：

| 变量 | 默认值 | 说明 |
|---|---:|---|
| `DOC_AGENT_DATA_DIR` | `./data` | 本地数据根目录 |
| `DOC_AGENT_DB_PATH` | `app.db` | 数据库相对路径，必须位于数据根目录内 |
| `DOC_AGENT_API_HOST` | `127.0.0.1` | API 监听地址 |
| `DOC_AGENT_API_PORT` | `8000` | API 监听端口 |
| `LOG_LEVEL` | `INFO` | `DEBUG`、`INFO`、`WARNING`、`ERROR` 或 `CRITICAL` |
| `MODEL_REQUEST_TIMEOUT_SECONDS` | `60` | 外部模型请求超时 |
| `DOC_AGENT_MAX_MODEL_CALLS_PER_JOB` | `12` | 单 Job 模型调用上限 |
| `DOC_AGENT_MAX_TOOL_CALLS_PER_JOB` | `30` | 单 Job 工具调用上限 |
| `DOC_AGENT_TASK_TIMEOUT_SECONDS` | `900` | 单任务硬超时 |
| `OFFICE_RENDER_TIMEOUT_SECONDS` | `120` | Office 渲染超时 |
| `UPLOAD_STAGING_TTL_HOURS` | `24` | 未消费上传的暂存有效期 |
| `SSE_HEARTBEAT_SECONDS` | `15` | SSE 连接心跳间隔 |

模型地址、模型名称和 API Key 在接入真实模型适配器时通过本机环境或受限配置提供。任何密钥都不得写入源码、数据库、事件、前端响应或普通日志。

## 安装与初始化

在仓库根目录执行：

```powershell
uv sync
pnpm --dir frontend install
uv run alembic upgrade head
```

应用启动时会校验数据库迁移版本。数据库未迁移或版本落后时 API 会拒绝启动，不会自动修改数据库。

## 本地开发

启动 API：

```powershell
uv run uvicorn app.api.main:app --host 127.0.0.1 --port 8000 --reload
```

启动前端：

```powershell
pnpm --dir frontend dev
```

常用地址：

- 健康检查：`http://127.0.0.1:8000/health`
- OpenAPI：`http://127.0.0.1:8000/api/v1/openapi.json`
- Swagger：`http://127.0.0.1:8000/docs`

上传接口：

- `POST /api/v1/uploads`
- `GET /api/v1/uploads/{upload_id}`
- `DELETE /api/v1/uploads/{upload_id}`

任务接口：

- `POST /api/v1/tasks`
- `GET /api/v1/tasks`
- `GET /api/v1/tasks/{task_id}`
- `POST /api/v1/tasks/{task_id}/turns`
- `GET /api/v1/tasks/{task_id}/events`

任务事件流使用 SSE，支持 `after_event_id` 或 `Last-Event-ID` 续传。事件先持久化到 `execution_events`，再进行回放和实时广播；心跳不会写入数据库。

当前支持的输入格式为 DOCX、XLSX、PPTX、PDF、CSV、MD、TXT、PNG、JPEG 和 WebP。单文件上限为 50 MB，MD/TXT 上限为 2 MB；宏文件和旧版 Office 格式会被拒绝。

## 数据目录

默认运行数据保存在 `data/`，其中数据库、WAL 文件、staging 文件、任务文件、预览、快照和日志不得提交到 Git。

```text
data/
  app.db
  logs/
  staging/
  tasks/
```

所有文件操作必须通过服务端路径守卫映射，不接受客户端提供的绝对路径或 `..` 路径。运行服务默认只绑定回环地址。

## 质量命令

合并前至少运行：

```powershell
uv run ruff check .
uv run pyright backend app
uv run pytest backend/tests
uv run alembic check
pnpm --dir frontend typecheck
pnpm --dir frontend build
uv run python -m scripts.contracts.generate_frontend_contracts --check
```

接口契约以 FastAPI/Pydantic 为唯一来源。修改 DTO、错误码、事件或路由后，必须执行：

```powershell
uv run python -m scripts.contracts.generate_frontend_contracts
```

该命令重新导出 `backend/openapi.json`，生成 `frontend/src/lib/api/schema.d.ts` 和 SSE 判别联合 `frontend/src/lib/api/events.generated.ts`。提交前用 `--check` 验证生成文件没有漂移。

## 开发规范

### 分层与边界

- API 层只负责 HTTP 协议、参数校验、响应映射和异常转换。
- 应用层编排用例，不直接依赖前端或供应商 SDK。
- 基础设施层实现数据库、文件系统、模型和 Office 适配。
- 模型只能选择受控工具，不能生成或执行任意代码。
- 原始文件不可变，所有修改和转换必须生成新文件。
- 未验证的 staged 文件不得发布为可下载产物。

### 类型与测试

- Python 代码遵循 Ruff 和严格 Pyright 检查。
- 新行为必须先写失败测试，再写最小实现并完成重构。
- 测试必须使用固定样例或临时数据目录，不依赖真实网络。
- 文件路径、SQLite 外键、迁移差异、JSON 日志和敏感信息脱敏属于必测边界。
- 测试不得通过修改固定验收样例来制造成功结果。

### 安全与日志

- 日志使用结构化 JSON，可携带 `request_id`、`task_id`、`turn_id` 和 `job_id`。
- 不记录完整文档正文、完整提示词、API Key、Cookie、Authorization 或绝对路径。
- 所有文档内容均视为不可信输入，不得将其中的指令当作系统或用户指令执行。
- 外部 AI 服务不可用时，不得生成伪造结果或宣称任务成功。

## Git 与 GitHub Flow

`master` 是稳定分支，不允许直接向 `master` 推送实现提交。

分支命名统一为：

```text
<type>/<task-id>-<task-name>
```

示例：

```text
feat/t11-upload-api
fix/t13-task-pagination
docs/project-readme
```

规则：

- `type` 使用 `feat`、`fix`、`docs`、`refactor`、`test`、`chore` 之一。
- 分支名必须包含 `tasks.md` 中的任务 ID 和简短任务名。
- 分支名不包含角色编号或个人姓名。
- 从最新 `master` 创建分支。
- 每个任务保持独立、可测试的提交，提交信息使用 `type: summary`。
- 每次任务状态变化、任务完成或 PR 合并后，必须同步更新 `docs/task-tracking.md` 的状态、统计和直接后继可用性。
- 推送分支后创建面向 `master` 的 Pull Request。
- PR 通过评审和检查后再合并，合并后同步 `master`，再从最新 `master` 创建下一分支。

推荐提交示例：

```text
feat: add upload API
fix: reject mismatched upload MIME types
docs: document local environment and Git workflow
```

## 当前已知边界

- Worker、Agent DAG、文档工具和格式转换尚未实现。
- 前端目前是最小 Vite 基础，不是完整三栏工作台。
- Office 状态探测不代表所有渲染操作已经可用。
- PDF 仅作为只读输入或后续注册转换结果，不支持编辑。

完整 MVP 边界和不在范围内的能力见 [Requirements.md](Requirements.md) 与 [Design.md](Design.md)。
