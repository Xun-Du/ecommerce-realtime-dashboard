# 实时电商 A/B 测试与归因分析看板

基于 Supabase Postgres、FastAPI、Streamlit 与 Plotly 的实时电商 A/B 测试与归因分析 Demo。当前完成 M0（项目准备与可启动骨架）；数据库建模、指标计算和事件模拟将在后续里程碑加入。

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

   `DATABASE_URL` 使用 Supabase 的 PostgreSQL 连接串，并保留 `postgresql+psycopg://` 驱动前缀；`SUPABASE_SERVICE_ROLE_KEY` 只能用于后端和模拟器，绝不能提交到 Git、传给前端或写入 Streamlit Cloud 的公开代码。

4. 在一个终端启动 API：

   ```bash
   .venv/bin/run-api
   ```

   访问 `http://localhost:8000/health`，预期响应为：

   ```json
   {"status":"ok","database":"not_checked"}
   ```

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
.venv/bin/run-simulator
```

也可先执行 `source .venv/bin/activate`，再省略 `.venv/bin/` 前缀。当前项目目录名含有 `:`，而本机 uv 0.12.0 的 `uv run` 无法处理该路径；因此请使用上面的虚拟环境命令。`run-simulator` 在 M0 会明确提示该能力将在 M1 实现。数据库初始化与历史数据脚本同样留待 M1。

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

## 验证与部署边界

执行 `.venv/bin/lint` 与 `.venv/bin/test` 验证代码质量和 API/配置契约。M0 的 `/health` 仅证明 API 进程存活；真实数据库连通性检查会在 M1 加入。

Render 与 Streamlit Community Cloud 的服务创建、Secrets 注入和部署配置属于 M6。届时仅在 Render 注入数据库和 Supabase 服务端密钥；Streamlit Community Cloud 仅保存后端公开地址。
