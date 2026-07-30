# 实时电商 A/B 测试与归因分析看板：工程开发计划

> **依据**：`实时电商AB测试与归因分析看板_PRD.docx`（V1.0，2026-07-29）  
> **当前状态**：仅完成 PRD 与其生成脚本；尚未初始化应用代码、数据库、依赖、测试或部署配置。  
> **MVP 技术路线**：Supabase Postgres + FastAPI + Streamlit + Plotly；以“模拟事件流 + 短间隔轮询”实现准实时 Demo。

---

## 1. 总览与交付策略

### 1.1 最终交付物

项目完成后应提供一个可复现、可访问的端到端 Demo：

1. 数据模拟器持续向 Postgres 写入 `click`、`add_to_cart`、`buy` 行为事件。
2. FastAPI 基于统一指标口径向前端提供健康检查、经营指标、漏斗、归因、实验评估和配置接口。
3. Streamlit 看板通过顶部筛选器联动展示概览、诊断与决策信息。
4. README 说明本地启动、环境变量、初始化、运行测试和部署流程。
5. 自动化测试覆盖核心指标口径、实验结论规则、API 基本契约和关键异常场景。
6. 后端可部署到 Render，前端可部署到 Streamlit Community Cloud；不把密钥写入仓库。

### 1.2 分层架构

```text
数据模拟器 ──写入──> Supabase Postgres
                         │
                         ▼
                    FastAPI 服务
                         │
                         ▼
                 Streamlit + Plotly 看板
                         │
                    用户筛选 / 刷新
```

### 1.3 实施原则

- **先 P0、后 P1**：先完成指标、漏斗与 A/B 实验闭环，再实现归因和配置。
- **口径先行**：聚合逻辑只在后端服务层定义，前端不重复计算业务指标。
- **可重复运行**：初始化、造数和启动命令必须可重复执行；避免仅依赖手工操作。
- **Demo 真实感**：数据应具备合理时间分布、渠道分布和组间效果，但必须在 README 中标明为模拟数据。
- **边界清晰**：第一版不实现真实支付、广告平台回传、登录权限、多租户和秒级流处理。

### 1.4 推荐迭代顺序与里程碑

| 里程碑 | 阶段 | 可演示能力 | 是否可独立验收 |
| --- | --- | --- | --- |
| M0 | 0. 项目准备 | 项目骨架、环境可启动 | 是 |
| M1 | 1. 数据底座 | 可查询的历史数据与持续事件流 | 是 |
| M2 | 2. 指标 API | 概览与漏斗接口 | 是 |
| M3 | 3. 实验评估 | A/B 统计结论和决策建议 | 是 |
| M4 | 4. P0 看板 | 可交互的完整 P0 Demo | 是，**首个 MVP** |
| M5 | 5. P1 能力 | 归因、策略配置、预警 | 是 |
| M6 | 6. 质量与部署 | 测试、文档、云端访问 | 是，**最终交付** |

---

## 2. 阶段 0：项目准备（M0）

### 2.1 目标

建立稳定、一致、可协作的开发基础，使任何开发者能按 README 在本地启动数据库连接、后端、前端和模拟器。

### 2.2 外部账户与服务准备

| 服务 | 用途 | 需要完成的准备 | 备注 |
| --- | --- | --- | --- |
| Supabase | 托管 Postgres，开发/生产数据源 | 注册项目；创建项目；保存 Project URL、数据库连接串和服务端密钥 | 免费套餐足够支撑 Demo |
| GitHub | 源码托管和部署关联 | 创建私有或公开仓库；配置 `.gitignore` | 不提交 `.env` 或密钥 |
| Render | 部署 FastAPI | 使用 GitHub 登录；后续创建 Web Service | 初期无需配置 |
| Streamlit Community Cloud | 部署前端看板 | 使用 GitHub 登录 | 初期无需配置 |

> Supabase 的 `service_role` 密钥只能被后端和数据模拟器使用；Streamlit 前端只能持有后端公开地址，不能保存任何数据库管理员凭据。

### 2.3 本机软件与依赖安装

| 类别 | 建议版本/工具 | 安装目的 | 验证命令 |
| --- | --- | --- | --- |
| Python | 3.11 或 3.12 | 运行后端、前端、脚本和测试 | `python3 --version` |
| 包管理器 | `uv`（推荐）或 `pip` + `venv` | 锁定、安装 Python 依赖 | `uv --version` |
| Git | 当前稳定版 | 版本管理与云部署关联 | `git --version` |
| Docker Desktop | 当前稳定版，可选 | 本地 Postgres/容器化验证 | `docker --version` |
| Supabase CLI | 当前稳定版，可选 | 本地 Supabase、迁移与数据库管理 | `supabase --version` |
| 编辑器 | VS Code / PyCharm 等 | 开发与调试 | 非强制 |

推荐 macOS 安装方式（若尚未安装 Homebrew，先按照其官网说明安装）：

```bash
brew install python@3.12 uv git
brew install --cask docker
brew install supabase/tap/supabase
```

Python 运行时依赖应写入 `pyproject.toml`，不依赖某台机器的全局安装。第一版推荐依赖如下：

| 包 | 作用 |
| --- | --- |
| `fastapi` | 后端 HTTP API |
| `uvicorn[standard]` | 本地与生产 ASGI 服务 |
| `sqlalchemy` | 数据模型、查询与事务管理 |
| `psycopg[binary]` | PostgreSQL 驱动 |
| `pydantic-settings` | `.env` 环境配置校验 |
| `streamlit` | 交互式 Web 看板 |
| `plotly` | 趋势、漏斗、柱状图 |
| `pandas` | API 响应转表格和展示层处理 |
| `scipy` | 双比例 z 检验；如自行实现则可不引入 |
| `httpx` | 前端请求 API、接口测试 |
| `pytest` | 单元与 API 测试 |
| `pytest-asyncio` | 异步接口测试支持 |
| `ruff` | 格式与静态检查 |

开发依赖还应包含 `pytest-cov`（覆盖率报告）与 `pre-commit`（可选，用于提交前检查）。依赖版本在首次实现时固定到兼容范围，并由锁文件保证团队一致性。

### 2.4 项目目录与配置

建议初始化为单仓库 Python 项目：

```text
.
├── backend/
│   ├── app/
│   │   ├── api/              # FastAPI 路由
│   │   ├── core/             # 配置、数据库连接、日志
│   │   ├── models/           # ORM 模型
│   │   ├── schemas/          # Pydantic 请求/响应模型
│   │   └── services/         # 指标、漏斗、归因、实验计算
│   └── tests/
├── frontend/
│   ├── app.py                # Streamlit 入口
│   ├── api_client.py         # 后端请求封装
│   └── components/           # 卡片、图表和页面区块
├── scripts/
│   ├── init_db.py            # 建表和初始配置
│   ├── seed_data.py          # 可重复的历史数据初始化
│   └── simulate_events.py    # 持续事件模拟器
├── sql/                      # 建表、索引、迁移 SQL
├── docs/                     # 架构、数据字典、演示说明
├── .env.example
├── pyproject.toml
├── README.md
└── program_schedule.md
```

` .env.example`（文件开头不得包含空格）至少定义：

```dotenv
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/postgres
SUPABASE_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_SERVICE_ROLE_KEY=replace_me
API_BASE_URL=http://localhost:8000
STREAMLIT_SERVER_PORT=8501
SIMULATOR_INTERVAL_SECONDS=5
```

实际 `.env` 必须加入 `.gitignore`；生产环境变量通过 Render 和 Streamlit Cloud 的 Secret 配置页面注入。

### 2.5 本阶段任务清单

1. 初始化 Git 仓库、Python 虚拟环境和 `pyproject.toml`；添加 `.gitignore`、`.env.example`、README 基础结构。
2. 建立上述目录；添加空的 Python 包、最小 FastAPI 入口和最小 Streamlit 入口。
3. 实现统一配置对象：启动时校验数据库 URL、API 地址和模拟器间隔；缺失配置应输出明确报错。
4. 配置 Ruff 与 Pytest，提供 `lint`、`test`、`run-api`、`run-dashboard`、`run-simulator` 的标准命令。
5. 添加 `/health` 占位接口，返回服务存活状态；数据库检查可在阶段 1 接入。

### 2.6 验收标准

- `uv sync`（或等价命令）可安装全部依赖。
- 后端能在 `http://localhost:8000` 启动，`GET /health` 返回 200。
- 前端能在 `http://localhost:8501` 启动并显示“后端未连接/待接入”的明确状态。
- 新开发者仅使用 README 和 `.env.example` 能完成环境配置，不需要阅读源代码猜测命令。

---

## 3. 阶段 1：数据底座与事件模拟（M1）

### 3.1 目标

建立支撑 P0/P1 的最小数据模型，并生成具有合理商业逻辑的历史事件和持续新增事件。

### 3.2 数据模型

| 表 | 核心字段 | 约束与索引 | 使用方 |
| --- | --- | --- | --- |
| `events` | `event_id`、`user_id`、`session_id`、`event_type`、`experiment_group`、`channel`、`product_id`、`order_value`、`created_at` | `event_id` 主键；`event_type` 限定 click/add_to_cart/buy；索引 `created_at`、`experiment_group + created_at`、`user_id + created_at` | 指标、漏斗、归因、实验 |
| `users` | `user_id`、`first_seen_at`、`acquisition_channel`、`country`、`device_type` | `user_id` 主键；`first_seen_at` 索引 | 后续人群下钻、渠道扩展 |
| `experiment_config` | `experiment_id`、`traffic_split_a`、`traffic_split_b`、`conversion_alert_threshold`、`gmv_alert_threshold`、`updated_at` | 单个 MVP 默认实验唯一；比例和为 1；阈值非负 | 配置与预警 |

第一版采用单实验固定标识，例如 `homepage_checkout_v1`。`experiment_group` 仅允许 `A`（对照组）、`B`（实验组）和可选 `NULL`（非实验流量）；所有实验分析默认忽略非实验流量。

### 3.3 数据生成策略

1. **历史种子数据**：一次性生成最近 7 天或 14 天的数据，让首开页面即有趋势图和足够样本量。
2. **用户与会话**：为同一用户生成多个会话和事件，避免每个事件都是唯一用户，保证 DAU 去重逻辑可验证。
3. **漏斗顺序**：正常路径必须先 `click`、再 `add_to_cart`、最后 `buy`；同一会话下的时间戳递增。
4. **渠道分布**：至少生成 organic、search、social、affiliate、email 五类渠道，并设定不同转化倾向。
5. **实验效果**：B 组的购买转化率应高于 A 组且提升幅度可配置，使默认时间窗口可稳定演示“显著优于”。
6. **金额分布**：仅 `buy` 事件拥有大于 0 的 `order_value`；使用合理的正态或对数正态近似分布，并避免负金额。
7. **持续模拟**：按 `SIMULATOR_INTERVAL_SECONDS` 生成一批新会话；每批次使用数据库事务写入，写入失败应记录错误且下轮继续尝试。
8. **可复现性**：种子脚本允许传入随机种子、时间范围、用户数量和 B 组提升幅度；默认参数写入 README。

### 3.4 任务清单

1. 在 `sql/` 编写可重复运行的建表和索引脚本；建立 ORM 映射或统一数据访问层。
2. 在 `scripts/init_db.py` 写入默认实验配置；重复执行时通过唯一标识更新而不是新增重复实验。
3. 在 `scripts/seed_data.py` 生成历史用户、会话与事件；输出写入数量、各事件类型数量、A/B 样本数和总体转化率。
4. 在 `scripts/simulate_events.py` 实现持续写入；支持优雅中断，不产生半批次数据。
5. 为数据生成器编写确定性测试：事件类型有效、购买事件金额有效、漏斗顺序有效、流量分配接近配置。
6. 在 README 记录数据库初始化、造数、运行模拟器与清理/重建开发数据的安全流程。

### 3.5 验收标准

- 数据库表、主键、检查约束和索引创建成功。
- 种子数据可重复执行且不会破坏表结构；默认范围内已有非空的 A/B 样本和渠道数据。
- 模拟器运行 5 分钟后，`events` 数量增加，且新增数据仍满足正常漏斗关系。
- 按天聚合时，默认窗口内的 `click ≥ add_to_cart ≥ buy`；若特意注入异常数据，应能被后续服务识别。

---

## 4. 阶段 2：核心指标与漏斗 API（M2）

### 4.1 目标

将 PRD 已定义的业务口径封装为稳定、可测试的 FastAPI 服务。前端只消费 API 响应，不直接访问数据库。

### 4.2 公共 API 约定

- 所有时间使用 ISO 8601 带时区字符串；默认时区为 UTC，并在 README 明确展示层时区策略。
- `start_time` 与 `end_time` 为左闭右开区间 `[start_time, end_time)`，避免相邻窗口重复计数。
- 日期范围非法、`start_time >= end_time`、不支持的粒度或实验组应返回 HTTP 422。
- 发生数据库故障时返回 HTTP 503 与机器可读的错误码，服务端日志保留根因，不向客户端泄露连接凭据。
- 所有金额均返回数值型；比例以 `0~1` 小数表示，前端统一格式化为百分比。

### 4.3 接口与实现方案

| 接口 | 参数 | 关键响应字段 | 实现重点 |
| --- | --- | --- | --- |
| `GET /health` | 无 | `status`、`database` | 检查 API 存活和数据库连通性 |
| `GET /api/metrics` | `start_time`、`end_time`、`granularity`（hour/day）、可选 `experiment_group` | `dau`、`gmv`、`purchase_conversion_rate`、`aov`、`trends` | 统一聚合，按小时/天返回趋势点 |
| `GET /api/funnel` | `start_time`、`end_time`、可选 `experiment_group` | 各步骤去重人数、相邻转化率、累计转化率、`has_data_quality_issue` | 漏斗人数、除零处理、异常标记 |

核心口径必须与 PRD 一致：

- **DAU**：窗口内发生任意事件的去重 `user_id` 数。
- **GMV**：窗口内所有 `buy` 事件的 `order_value` 总和；不处理退款、税费和取消订单。
- **订单数**：窗口内 `buy` 事件数；假设一条 `buy` 事件对应一笔订单。
- **购买转化率**：购买去重用户数 / 点击去重用户数；点击人数为 0 时返回 `null`，不返回 0。
- **AOV**：GMV / 订单数；订单数为 0 时返回 `null`。
- **漏斗人数**：各步骤分别基于窗口内去重 `user_id` 计算；若下游人数高于上游人数，置 `has_data_quality_issue=true`，但保留原始数值便于诊断。

### 4.4 任务清单

1. 定义 Pydantic 查询参数与响应模型，生成 OpenAPI 文档并稳定字段命名。
2. 实现数据库会话、依赖注入、请求校验、结构化日志和统一异常响应。
3. 在服务层实现指标与趋势聚合函数；路由层只负责参数解析和响应序列化。
4. 实现漏斗计算、相邻转化率和累计转化率；明确 `null`、空数据和质量异常的返回方式。
5. 为高频查询使用参数化 SQL/SQLAlchemy；禁止拼接用户输入构造 SQL。
6. 给常用筛选组合补充数据库索引，并通过历史种子数据验证接口响应时间。
7. 编写单元测试、接口测试和空窗口/零分母/异常漏斗数据测试。

### 4.5 验收标准

- `/docs` 可查看三个接口的请求与响应模型。
- `/api/metrics` 与手工 SQL 聚合结果一致；不同 `granularity` 和实验组筛选返回正确数据。
- `/api/funnel` 在正常数据下返回递减漏斗；异常数据下返回质量标记而非静默掩盖。
- 所有输入校验和空数据场景都有明确、可预测的响应。

---

## 5. 阶段 3：A/B 实验评估与决策接口（M3）

### 5.1 目标

实现 PRD 最核心的决策能力：把 A/B 组的行为数据转为统计结果与可执行的业务结论。

### 5.2 接口

`GET /api/experiment?start_time=...&end_time=...`

接口至少返回：

```json
{
  "experiment_id": "homepage_checkout_v1",
  "primary_metric": "purchase_conversion_rate",
  "minimum_sample_size": 100,
  "groups": {
    "A": {"click_users": 0, "purchase_users": 0, "conversion_rate": null, "gmv": 0, "aov": null, "add_to_cart_rate": null, "order_count": 0},
    "B": {"click_users": 0, "purchase_users": 0, "conversion_rate": null, "gmv": 0, "aov": null, "add_to_cart_rate": null, "order_count": 0}
  },
  "uplift": null,
  "p_value": null,
  "decision": {"code": "insufficient_sample", "message": "样本量不足，建议继续观察。"}
}
```

数值示例中的 0 仅表示结构，不代表零样本时的最终业务含义；零分母相关比率、uplift 与 p-value 应返回 `null`。

### 5.3 统计与业务规则

1. 主指标为购买转化率：`buy 去重用户 / click 去重用户`。
2. A 为对照组，B 为实验组；两组样本量均以点击去重用户数衡量。
3. 最小样本阈值作为应用配置常量（MVP 默认 100，可后续配置化）。任一组不足阈值时，不执行确定性上线判断。
4. 当两组样本充足且分母有效时，使用双比例 z 检验计算双侧 `p_value`。
5. `uplift = (conversion_rate_B - conversion_rate_A) / conversion_rate_A`；A 组转化率为 0 时返回 `null`。
6. 决策优先级固定：样本不足 → 显著优于（`p < 0.05` 且 B>A）→ 显著低于（`p < 0.05` 且 B<A）→ 无显著差异。
7. 决策信息同时包括机器代码、中文展示文案和供页面显示的提示等级；GMV、AOV、加购率、订单数仅为辅助指标，不改变上述主规则。

### 5.4 任务清单

1. 抽取每组的点击、加购、购买去重用户数、GMV 和订单数，复用阶段 2 的口径函数。
2. 实现统计检验函数并单独测试，不把统计代码嵌在路由层。
3. 实现业务结论映射，确保每个结论都可解释且对应 PRD 文案。
4. 为正向、负向、无显著差异、样本不足、零点击、A 组零转化等场景建立固定测试数据。
5. 在 API 文档与 README 中说明 p-value 的含义和限制：不能单独代表业务收益或自动上线结论。

### 5.5 验收标准

- B 组转化率显著高于 A 组时，返回正 uplift、低于 0.05 的 p-value 和“显著优于”结论。
- B 组显著低于 A 组时，返回负向结论。
- 样本不足时不输出“可上线”；零分母不产生 NaN、Infinity 或 500 错误。
- 响应中同时包含主指标、辅助指标、统计结果和业务可读结论。

---

## 6. 阶段 4：P0 Streamlit 看板（M4）

### 6.1 目标

交付完整的首个可演示 MVP，让用户可以按“经营是否健康 → 哪里发生变化 → 实验是否应上线”的顺序完成分析。

### 6.2 页面与数据流

```text
顶部筛选器（时间、粒度、实验组、自动刷新）
    ├── 概览区：指标卡 + GMV/转化率趋势      ← /api/metrics
    ├── 诊断区：整体或分组漏斗               ← /api/funnel
    └── 决策区：A/B 对比、uplift、p-value、结论 ← /api/experiment
```

### 6.3 页面功能清单

1. **顶部筛选区**：默认最近 24 小时；支持时间范围、小时/天粒度、实验组（全部/A/B）和自动刷新开关。归因模型选择器留给阶段 5。
2. **概览区**：展示 DAU、GMV、购买转化率、AOV 四张指标卡；当后台阈值接入前，卡片可先显示正常/数据不足状态。
3. **趋势区**：使用 Plotly 展示 GMV 趋势与购买转化率趋势；空数据要显示业务友好的空状态。
4. **漏斗诊断区**：展示 click、add_to_cart、buy 的人数、转化率和流失；若 `has_data_quality_issue` 为真，显示数据质量提示。
5. **实验决策区**：左右对照展示 A/B 主辅助指标，突出 uplift、p-value 和中文结论；样本不足时禁止以成功色暗示可上线。
6. **刷新与失败处理**：API 请求有超时；请求失败时显示错误摘要和重试入口，不让单个模块的失败导致全页崩溃。

### 6.4 实现方案

- `frontend/api_client.py` 封装所有 HTTP 调用、超时、错误映射和响应模型校验。
- 使用 `st.session_state` 保持筛选条件；所有区域从同一份筛选状态构建 API 参数。
- 使用 `st.cache_data` 对相同的短时间窗口请求设置有限 TTL；自动刷新时显式失效缓存，避免展示陈旧数据。
- 组件按“筛选、指标卡、趋势、漏斗、实验结果”拆分，`app.py` 只负责页面编排。
- 前端数值格式化统一处理：金额使用货币格式、比例转换百分比、`null` 显示为 `—`。

### 6.5 验收标准

- 首次进入默认展示最近 24 小时的非空数据。
- 改变时间范围、粒度或实验组后，概览、趋势和漏斗同时联动；实验评估保持 A/B 全量比较，不受单组筛选误导。
- API 失败、空数据、异常漏斗、样本不足都具有清晰页面反馈。
- 在常见桌面浏览器尺寸下无横向遮挡、图表标题和单位清晰。

---

## 7. 阶段 5：P1 归因、策略配置与预警（M5）

### 7.1 归因分析

新增 `GET /api/attribution?start_time=...&end_time=...&model=first_touch|last_touch`。

| 模型 | 计算规则 | 适用业务解释 |
| --- | --- | --- |
| 首次触达 `first_touch` | 对窗口内产生购买的用户，取其窗口内最早行为事件的 `channel` 归因 | 衡量渠道拉新/首次影响 |
| 最后触达 `last_touch` | 对窗口内产生购买的用户，取购买事件发生前最近一次非 `buy` 行为的 `channel` 归因 | 衡量临门促转化贡献 |

实现要求：

1. 响应按渠道返回订单数、GMV、GMV 占比；分母为同一模型下的总 GMV。
2. 没有有效触点的订单归入 `unknown`，避免因丢弃数据使占比不完整。
3. 同一订单/购买事件只能归属于一个渠道；接口须返回模型标识和时间范围。
4. 前端新增模型切换器、渠道排行表和 GMV/订单贡献图，切换时保留当前时间范围。
5. 为“多触点”“仅 buy 事件”“无购买事件”“渠道占比和为 1”编写测试。

### 7.2 策略配置与预警

新增 `GET /api/config` 和 `POST /api/config`。

1. `GET` 返回单个 MVP 实验的当前分流比例、GMV 阈值、转化率阈值和更新时间。
2. `POST` 接收完整配置；服务端验证 A/B 分流均在 `(0, 1)`，且二者之和为 1；所有阈值必须非负。
3. 配置更新使用事务，并返回更新后的配置；暂不实现身份认证，但 README 必须标注该接口仅用于 Demo，生产环境必须加鉴权和审计。
4. 概览 API 或前端同时获得当前阈值，并依据“GMV 低于阈值”“购买转化率低于阈值”展示预警状态；不把阈值写死在前端。
5. 前端提供简洁配置表单、保存反馈和无效输入提示；保存成功后刷新受影响的概览卡片。

### 7.3 验收标准

- 切换归因模型后，渠道排行可发生合理变化，GMV 占比总和约为 100%。
- 更新阈值后重新请求概览，预警状态按新阈值变化。
- 非法比例、负阈值或数据库写入失败不会留下部分更新的配置。

---

## 8. 阶段 6：测试、文档与部署（M6）

### 8.1 自动化测试

| 测试层级 | 覆盖对象 | 关键场景 |
| --- | --- | --- |
| 单元测试 | 指标、漏斗、归因、显著性与结论函数 | 去重、零分母、异常漏斗、四种实验结论、归因归属 |
| 数据脚本测试 | 种子和模拟生成逻辑 | 合法事件、金额、会话顺序、组别分配、可复现随机种子 |
| API 测试 | FastAPI 路由与响应契约 | 正常查询、参数校验、空数据、数据库不可用 |
| 前端冒烟测试 | Streamlit 页面与 API 客户端 | API 成功、超时、错误、`null` 指标显示 |
| 手工验收 | 完整用户路径 | 筛选联动、自动刷新、结论可读性、部署后可访问 |

最低质量门槛：`ruff check` 通过、`pytest` 全绿、核心计算服务达到可解释的测试覆盖（目标 80% 以上；以关键逻辑覆盖而非单纯行数为准）。

### 8.2 README 与工程文档

README 至少包含：项目背景与产品边界、架构图、技术栈、目录说明、前置安装、Supabase 配置、`.env` 配置、本地启动顺序、测试命令、常见故障、部署地址（部署后补充）和模拟数据免责声明。

补充 `docs/` 文档：

- `data_dictionary.md`：三张表、字段含义、类型、约束和指标血缘。
- `api_reference.md`：接口样例、参数、状态码和业务口径。
- `demo_script.md`：5 分钟作品集演示流程，从问题发现到实验决策。

### 8.3 部署方案

1. **Supabase**：执行建表/索引脚本；仅将数据库连接串和服务端密钥保存在 Render 的环境变量中。
2. **Render**：创建 Python Web Service，构建时安装锁定依赖，启动命令为 `uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT`；健康检查路径为 `/health`。
3. **Streamlit Community Cloud**：连接 GitHub 仓库，入口为 `frontend/app.py`；在 Secrets 中仅配置 `API_BASE_URL` 为 Render 后端地址。
4. **数据模拟器**：MVP 可先在本地或单独的 Render Background Worker 运行；若使用云端，必须提供重启策略、日志和可暂停开关。
5. **跨域**：FastAPI CORS 仅允许本地开发地址和实际 Streamlit 域名，禁止生产环境使用通配符来源。

### 8.4 最终验收清单

- 从空环境按 README 可完成数据库配置、初始化、造数、启动后端和启动前端。
- Render 健康检查通过；Streamlit Cloud 能访问后端且无浏览器跨域错误。
- P0 的概览、漏斗、实验评估均返回非空真实模拟数据并支持筛选。
- P1 的归因模型切换与配置更新可用，预警状态正确。
- 不存在泄露密钥的 `.env`、日志、代码或前端静态资源。
- 项目明确声明“准实时模拟 Demo”，不夸大为生产级实时流式平台。

---

## 9. 每阶段开始前的检查点

| 开始阶段 | 前置条件 | 不满足时的处理 |
| --- | --- | --- |
| 阶段 1 | 阶段 0 的 API、前端骨架和环境变量加载正常 | 先修复项目启动与配置问题 |
| 阶段 2 | 数据库已建表，种子数据能产生有效漏斗 | 先验证数据脚本和表约束 |
| 阶段 3 | 指标/漏斗计算已有单测且口径稳定 | 不在前端临时计算实验指标 |
| 阶段 4 | 三个 P0 API 的响应模型和异常语义已稳定 | 先补 API 契约测试 |
| 阶段 5 | P0 看板可演示，基本筛选体验通过 | 不让 P1 阻塞 MVP 展示 |
| 阶段 6 | 功能冻结，关键流程已手工走通 | 集中处理质量、文档与部署问题 |

## 10. 建议的首次实施切片

第一次实现建议只完成 **阶段 0**，并将其验收为下一次工作的起点：建立目录、Python 依赖、环境模板、最小 FastAPI `/health`、最小 Streamlit 首页、README 启动说明和基础测试配置。完成后再进入阶段 1，避免在没有工程基础时同时处理数据库、统计逻辑和 UI。
