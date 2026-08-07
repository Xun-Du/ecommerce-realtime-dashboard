# 电商增长实验与营销归因平台

基于 Supabase Postgres、FastAPI、Streamlit 与 Plotly 的电商增长实验与营销归因 Demo。当前完成 M4.1：可初始化的数据底座、14 天历史模拟数据、持续事件模拟器、核心指标/漏斗/实验评估 API，以及带统一导航壳层的经营看板。数据层已开始向 M5/M6 演进，初始化命令会按版本迁移到新的兼容 schema。

当前应用包含 Home、Monitor、Attribution、Funnel 和 Experiments 五个可用模块；Customers、Creatives、Integrations 保持规划状态。M5 归因页支持首次触达、末次触达和线性归因，并可查看渠道、活动及订单触点路径示例。

## 前置条件

- macOS、Linux 或 Windows 上可用的 [uv](https://docs.astral.sh/uv/)
- Python 3.12（由 uv 管理）
- 已创建 Supabase 项目，并可取得项目 URL、Postgres 连接串和 `service_role` 密钥

Docker 与 Supabase CLI 均为可选工具，M0 不依赖它们。

## 本地启动

1. 安装并固定 Python 3.12：

   ```bash
   uv python install 3.12
   ```

2. 安装锁定依赖：

   ```bash
   uv sync
   ```

3. 创建本机配置文件，并填写真实 Supabase 信息：

   ```bash
   cp .env.example .env
   ```

   `DATABASE_URL` 应从 Supabase Dashboard → **Connect** → **Session Pooler** 复制完整连接串；将开头的 `postgresql://` 改成 `postgresql+psycopg://`，并保留 `?sslmode=require`。不要使用 `db.<项目引用>.supabase.co:5432` 的 Direct connection：它通常依赖 IPv6，在部分网络中无法解析或连接。`SUPABASE_SERVICE_ROLE_KEY` 只能用于后端和模拟器，绝不能提交到 Git、传给前端或写入 Streamlit Cloud 的公开代码。

4. 在一个终端启动 API：

   ```bash
   .venv/bin/run-api
   ```

   访问 `http://localhost:8000/health`，预期响应为：

   ```json
   {"status":"ok","database":"connected"}
   ```

   如果 Supabase 不可连接，接口返回 HTTP 503 与 `database_unavailable`；响应不会包含数据库连接串或密钥。

   M2 API 文档可在 `http://localhost:8000/docs` 查看。所有分析时间均须传入带时区的 ISO 8601 字符串，且按 UTC 左闭右开区间 `[start_time, end_time)` 计算。例如：

   ```bash
   curl -G 'http://localhost:8000/api/metrics' \
     --data-urlencode 'start_time=2026-07-30T00:00:00+00:00' \
     --data-urlencode 'end_time=2026-07-31T00:00:00+00:00' \
     --data-urlencode 'granularity=hour' \
     --data-urlencode 'experiment_group=A'

   curl -G 'http://localhost:8000/api/funnel' \
     --data-urlencode 'start_time=2026-07-30T00:00:00+00:00' \
     --data-urlencode 'end_time=2026-07-31T00:00:00+00:00'

   curl -G 'http://localhost:8000/api/experiment' \
     --data-urlencode 'start_time=2026-07-30T00:00:00+00:00' \
     --data-urlencode 'end_time=2026-07-31T00:00:00+00:00'
   ```

   `/api/metrics` 返回 DAU、GMV、订单数、购买转化率、AOV 与小时/天趋势；`/api/funnel` 返回 click、add_to_cart、buy 各步去重人数、转化/流失率和数据质量标记；`/api/experiment` 比较 A/B 两组的购买转化率、GMV、AOV、加购率和订单数，并返回 uplift、双侧双比例 z 检验的 p-value 与业务结论。金额为数值，比例为 `0~1` 小数；零分母的比例和 AOV 均返回 `null`。非法窗口、粒度或实验组返回 422。

   M5 归因接口示例：

   ```bash
   curl -G 'http://localhost:8000/api/attribution' \
     --data-urlencode 'start_time=2026-07-30T00:00:00+00:00' \
     --data-urlencode 'end_time=2026-07-31T00:00:00+00:00' \
     --data-urlencode 'model=linear'
   ```

   归因仅计算窗口内购买，并向前回溯 30 天的点击触点；首次触达、末次触达和线性模型均保证订单 GMV 不丢失。没有有效触点的订单显式归入 `unknown`。归因是规则化的贡献分配，不代表因果增量。

   实验主指标是购买转化率（购买去重用户数／点击去重用户数），默认最小样本量为每组 100 名点击用户。任一组不足时仅建议继续观察；样本充足时，`p-value < 0.05` 且 B 组更高表示“显著优于”，更低表示“显著低于”，其余为“无显著差异”。p-value 只衡量随机波动的证据，最终业务判断仍应结合 uplift、GMV、样本量与策略风险。

5. 在另一个终端启动看板：

   ```bash
   .venv/bin/run-dashboard
   ```

   打开 `http://localhost:8501`。应用默认进入 Home，左侧导航可切换 Home、Monitor、Funnel 和 Experiments；顶部筛选会跨模块保留。Attribution、Customers、Creatives、Integrations 当前显示规划状态。自动刷新默认关闭，开启后每 30 秒刷新数据区域；“立即刷新”会绕过短期缓存重新请求 API。

   概览与漏斗会应用实验组筛选；实验决策始终比较完整的 A/B 两组，避免单组筛选误导结论。API 超时、不可用或响应异常时，对应模块会显示可读错误，其他模块仍可继续使用。Streamlit 只读取 `API_BASE_URL`，不会访问数据库或使用 Supabase 服务端密钥。

## 标准命令

```bash
.venv/bin/lint
.venv/bin/test
.venv/bin/run-api
.venv/bin/run-dashboard
.venv/bin/init-db
.venv/bin/seed-data
.venv/bin/run-simulator
```

也可先执行 `source .venv/bin/activate`，再省略 `.venv/bin/` 前缀。当前项目目录名含有 `:`，而本机 uv 0.12.0 的 `uv run` 无法处理该路径；因此请使用上面的虚拟环境命令。

## M1 数据库与模拟数据

所有以下命令都读取 `.env` 中的 `DATABASE_URL`，并直接操作该 Supabase Postgres 数据库；不会通过 Streamlit 前端访问数据库。

1. 初始化表、索引与默认实验配置：

   ```bash
   .venv/bin/init-db
   ```

   此命令可安全重复执行。它会按文件名顺序应用 `sql/001_initial_schema.sql`、`sql/002_data_model_evolution.sql` 等迁移，并写入/回填默认实验 `homepage_checkout_v1`、变体、分组和新事实字段。

2. 写入默认 14 天历史数据：

   ```bash
   .venv/bin/seed-data
   ```

   默认生成 10,000 名用户、五类渠道（organic、search、social、affiliate、email）及 A/B 实验事件。固定随机种子、窗口结束时间和参数时，生成结果可复现；可使用 `--days`、`--users`、`--seed`、`--b-uplift` 与 `--end-at` 调整。例如：

   ```bash
   .venv/bin/python scripts/seed_data.py --days 14 --users 10000 --seed 20260731 --b-uplift 0.20 --end-at 2026-07-31T00:00:00+00:00
   ```

3. 仅在需要重新生成 Demo 数据时重置：

   ```bash
   .venv/bin/python scripts/seed_data.py --reset
   ```

   `--reset` 会删除 `events`、`users`、`experiment_assignments` 与 `experiment_results` 的全部记录后重新创建默认配置和种子数据。该项目约定此 Supabase 实例只存放本 Demo 数据；若数据库包含其他重要数据，不要执行此命令。

4. 持续写入新会话：

   ```bash
   .venv/bin/run-simulator
   ```

   模拟器按 `SIMULATOR_INTERVAL_SECONDS`（默认 60 秒）写入一批约 5 名用户的完整漏斗会话，避免实时流量淹没 14 天历史趋势。按 `Ctrl+C` 可优雅停止；单批写入失败会回滚并在下一轮重试。数据均为模拟数据，不代表真实业务、订单或支付结果。

## 配置说明

所有配置均可由同名系统环境变量覆盖 `.env`：

| 变量 | 说明 |
| --- | --- |
| `DATABASE_URL` | Supabase Postgres SQLAlchemy/psycopg 连接串 |
| `SUPABASE_URL` | Supabase 项目 URL |
| `SUPABASE_SERVICE_ROLE_KEY` | 仅后端与模拟器可用的服务端密钥 |
| `API_BASE_URL` | Streamlit 调用 API 的基础地址 |
| `STREAMLIT_SERVER_PORT` | Streamlit 本地监听端口 |
| `SIMULATOR_INTERVAL_SECONDS` | M1 模拟器批次间隔（正整数秒） |

配置缺失或格式错误会在相关服务启动时显示明确错误，且不会输出密钥内容。`.env`、虚拟环境、缓存和 Streamlit secrets 已由 `.gitignore` 排除。

对于 IPv4 网络，推荐使用 Supabase **Session Pooler** 的 `pooler.supabase.com:5432` 地址；用户名通常为 `postgres.<项目引用>`，而不是 Direct connection 的 `postgres`。请完整复制 Connect 页面提供的 URI，避免手工拼接或泄露数据库密码。

## 验证与部署边界

执行 `.venv/bin/lint` 与 `.venv/bin/test` 验证代码质量和 API/配置契约。M1 的 `/health` 同时检查 API 进程与 Supabase 数据库连通性。数据库集成验收应在可访问 Supabase 的网络环境中执行上述初始化、种子和模拟器命令。

Render 与 Streamlit Community Cloud 的服务创建、Secrets 注入和部署配置属于 M6。届时仅在 Render 注入数据库和 Supabase 服务端密钥；Streamlit Community Cloud 仅保存后端公开地址。
