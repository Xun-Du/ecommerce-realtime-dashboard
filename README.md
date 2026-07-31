# 实时电商 A/B 测试与归因分析看板

基于 Supabase Postgres、FastAPI、Streamlit 与 Plotly 的实时电商 A/B 测试与归因分析 Demo。当前完成 M1：可初始化的数据底座、14 天历史模拟数据与持续事件模拟器；指标 API 与完整看板将在后续里程碑加入。

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

5. 在另一个终端启动看板：

   ```bash
   .venv/bin/run-dashboard
   ```

   打开 `http://localhost:8501`，页面会展示“后端未连接／待接入”。

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

   此命令可安全重复执行。它创建 `users`、`events`、`experiment_config` 三张表，并以 UPSERT 写入默认实验 `homepage_checkout_v1`。

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

   `--reset` 会删除 `events`、`users` 与 `experiment_config` 的全部记录后重新创建默认配置和种子数据。该项目约定此 Supabase 实例只存放本 Demo 数据；若数据库包含其他重要数据，不要执行此命令。

4. 持续写入新会话：

   ```bash
   .venv/bin/run-simulator
   ```

   模拟器按 `SIMULATOR_INTERVAL_SECONDS`（默认 5 秒）写入一批约 100 名用户的完整漏斗会话。按 `Ctrl+C` 可优雅停止；单批写入失败会回滚并在下一轮重试。数据均为模拟数据，不代表真实业务、订单或支付结果。

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
