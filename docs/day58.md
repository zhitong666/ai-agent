# Day 58 学习笔记

日期：2026-09-17

项目：`ai-job-agent`

主题：PostgreSQL、数据库事务、迁移和 Docker 部署

## 1. Day 58 做了什么

Day 57 解决了：

```text
请求等待 LLM 时不要让事件循环阻塞
```

但聊天记忆仍然保存在：

```text
app/memory.py
  ->
SessionStore
  ->
Python 内存字典
```

这种做法的优点是简单，缺点是：

- 服务重启后记忆丢失。
- 多进程部署时，每个进程有自己的记忆。
- 用户下一次请求可能被分配到不同进程。
- 内存长期增长，没有持久化和查询能力。

Day 58 增加：

```text
PostgreSQL
  ->
异步连接池
  ->
聊天消息表
  ->
事务写入
  ->
数据库迁移
  ->
数据库健康检查
  ->
Docker Compose PostgreSQL 服务
```

## 2. Day 58 改了哪些文件

| 文件 | 变化 | 作用 |
|---|---|---|
| `app/postgres.py` | 新增 | 创建 PostgreSQL 异步连接池 |
| `app/postgres_session_store.py` | 新增 | 持久化聊天会话消息 |
| `app/db_cli.py` | 新增 | 数据库迁移和连接检查 |
| `migrations/001_initial.sql` | 新增 | 定义 `chat_messages` 表 |
| `app/async_agent.py` | 修改 | 支持从 PostgreSQL 读取和保存历史 |
| `app/main.py` | 修改 | 启动连接池，增加 `/health/db` |
| `docker-compose.yml` | 修改 | 增加 PostgreSQL 服务 |
| `Dockerfile` | 修改 | 复制迁移目录 |
| `tests/test_postgres_backend.py` | 新增 | 测试读取、事务和真实数据库集成 |
| `.env.example` | 修改 | 增加 `DATABASE_URL` |

## 3. 当前改动和项目架构的关系

Day 57 之前：

```text
FastAPI
  ->
async_agent
  ->
内存 SessionStore
```

Day 58 之后：

```text
FastAPI
  ->
async_agent
  ->
PostgresSessionStore
  ->
AsyncConnectionPool
  ->
PostgreSQL
```

```mermaid
flowchart LR
    A[客户端] --> B[FastAPI]
    B --> C[async_agent]
    C --> D[PostgresSessionStore]
    D --> E[AsyncConnectionPool]
    E --> F[PostgreSQL]
    F --> G[chat_messages 表]
    G --> H[持久化聊天历史]
```

## 4. Day 58 项目闭环实际流程

### 4.1 服务启动流程

```mermaid
flowchart TD
    A[uvicorn 启动 FastAPI] --> B[lifespan 开始]
    B --> C[创建 AsyncOpenAI]
    B --> D[创建 LLM Semaphore]
    B --> E[创建 PostgreSQL 连接池]
    E --> F[创建 PostgresSessionStore]
    C --> G[app.state.async_client]
    D --> H[app.state.llm_semaphore]
    E --> I[app.state.postgres_pool]
    F --> J[app.state.session_store]
    G --> K[等待请求]
    H --> K
    I --> K
    J --> K
```

### 4.2 `/chat` 非流式请求流程

```mermaid
flowchart TD
    A[POST /chat] --> B[校验 ChatRequest]
    B --> C[answer_question_async]
    C --> D[从 PostgresSessionStore 读取历史]
    D --> E[从 RAG 线程池检索]
    E --> F[构造 Prompt]
    F --> G[调用 AsyncOpenAI]
    G --> H[生成回复]
    H --> I[事务写入用户消息和助手消息]
    I --> J[返回 ChatResponse]
```

### 4.3 `/chat/stream` 流式请求流程

```mermaid
flowchart TD
    A[POST /chat/stream] --> B[校验 ChatRequest]
    B --> C[stream_answer_question_async]
    C --> D[读取 PostgreSQL 历史]
    D --> E[RAG 检索]
    E --> F[AsyncOpenAI stream=True]
    F --> G[async for 读取 token]
    G --> H[yield SSE chunk]
    H --> I{模型是否继续生成}
    I -->|是| G
    I -->|否| J[拼接完整回复]
    J --> K[事务写入用户消息和助手消息]
    K --> L[yield SSE done]
```

### 4.4 数据库迁移流程

```mermaid
flowchart TD
    A[python -m app.db_cli migrate] --> B[创建连接池]
    B --> C[创建 schema_migrations 表]
    C --> D[扫描 migrations 目录]
    D --> E{迁移是否已执行}
    E -->|已执行| F[跳过]
    E -->|未执行| G[按顺序执行 SQL]
    G --> H[记录迁移版本]
    H --> I[commit]
    G -->|失败| J[rollback]
    J --> K[抛出错误]
    F --> L[完成]
    I --> L
```

### 4.5 数据库健康检查流程

```mermaid
flowchart TD
    A[GET /health/db] --> B[从连接池获取连接]
    B --> C{能获取连接吗}
    C -->|否| D[返回 503]
    C -->|是| E[执行 SELECT 1]
    E --> F{查询成功吗}
    F -->|否| D
    F -->|是| G[返回 status ok]
```

## 5. 核心概念解释

### 5.1 为什么需要持久化

内存数据的特点是：

```text
服务进程还在：数据在
服务进程重启：数据消失
```

生产系统不能因为重启就丢失用户聊天历史。

数据库把数据写到磁盘，即使服务重启，数据仍然存在。

### 5.2 PostgreSQL

PostgreSQL 是一个关系型数据库。

它把数据组织成：

```text
数据库 Database
  ->
表 Table
  ->
行 Row
  ->
列 Column
```

本项目创建：

```text
数据库：ai_job_agent
  ->
表：chat_messages
  ->
行：一条 user 消息或一条 assistant 消息
```

### 5.3 表、主键和索引

`chat_messages` 表：

```sql
CREATE TABLE chat_messages (
    id BIGSERIAL PRIMARY KEY,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

解释：

- `id`：主键，唯一标识一行。
- `session_id`：标识会话。
- `role`：`user` 或 `assistant`。
- `content`：消息内容。
- `created_at`：创建时间。

索引：

```sql
CREATE INDEX idx_chat_messages_session_id
ON chat_messages (session_id, id);
```

作用：

- 快速找到某个会话的所有消息。
- 按消息顺序读取。

### 5.4 SQL

SQL 是操作关系型数据库的语言。

读取历史：

```sql
SELECT role, content
FROM chat_messages
WHERE session_id = $1
ORDER BY id ASC;
```

写入用户消息：

```sql
INSERT INTO chat_messages
    (session_id, role, content)
VALUES ($1, 'user', $2);
```

### 5.5 事务

事务是一组必须一起成功或一起失败的操作。

本项目 `append_turn()` 写入两条消息：

```text
INSERT user 消息
INSERT assistant 消息
```

如果第二句失败，第一句也不能保留，否则数据库里会出现：

```text
只有用户问题，没有助手回答
```

事务控制：

```text
commit：提交，让修改永久生效
rollback：回滚，撤销本次事务中所有修改
```

### 5.6 连接池

每次请求都新建数据库连接会很慢：

```text
建立 TCP 连接
  ->
数据库认证
  ->
执行 SQL
  ->
关闭连接
```

连接池提前创建一些连接，请求用完后再归还：

```mermaid
flowchart LR
    A[请求 1] --> B[连接池]
    C[请求 2] --> B
    D[请求 3] --> B
    B --> E[连接 1]
    B --> F[连接 2]
    B --> G[连接 3]
    E --> H[PostgreSQL]
    F --> H
    G --> H
```

本项目：

```python
AsyncConnectionPool(
    conninfo=dsn,
    min_size=1,
    max_size=10,
)
```

- `min_size`：最少保持几个连接。
- `max_size`：最多允许几个连接。

### 5.7 迁移

迁移是数据库结构的版本管理。

当前使用 `migrations/001_initial.sql`。

`schema_migrations` 表记录：

```text
哪个版本已经执行过
```

这样重复执行迁移时不会重复创建表。

### 5.8 Docker

Docker 把应用和运行环境打包成容器。

Day 58 使用 Docker 启动 PostgreSQL：

```bash
docker compose up -d postgres
```

好处：

- 不需要手动安装 PostgreSQL。
- 不同项目可以使用不同数据库版本。
- 数据库数据可以挂载到本地目录。
- 团队成员使用相同环境。

### 5.9 healthcheck

`docker-compose.yml` 中：

```yaml
healthcheck:
  test: ["CMD-SHELL", "pg_isready -U ai_agent -d ai_job_agent"]
  interval: 5s
  timeout: 5s
  retries: 10
```

作用：

- 定期检查 PostgreSQL 是否准备好。
- backend 等 PostgreSQL 健康后再启动。

### 5.10 DATABASE_URL

```text
postgresql://ai_agent:ai_agent@localhost:5432/ai_job_agent
```

拆解：

```text
postgresql://
ai_agent
:
ai_agent
@
localhost
:
5432
/
ai_job_agent
```

分别表示：

```text
协议
用户名
冒号
密码
@
主机
冒号
端口
/
数据库名
```

Docker 内部后端连接 PostgreSQL 时：

```text
主机使用 postgres
```

而不是：

```text
localhost
```

因为容器之间通过 Docker 网络互相访问。

## 6. 每个改动在业务中负责什么

### 6.1 app/postgres.py

负责：

- 读取 `DATABASE_URL`。
- 创建异步连接池。
- 控制连接池大小。
- 打开连接池。

### 6.2 app/postgres_session_store.py

负责：

- 读取某个会话的历史消息。
- 按顺序返回消息。
- 用事务保存一轮问答。
- 失败时回滚。

### 6.3 app/db_cli.py

负责：

- 执行迁移。
- 检查数据库连接。
- 记录已经执行的迁移版本。

### 6.4 migrations/001_initial.sql

负责：

- 定义 `chat_messages` 表。
- 建立 `session_id + id` 索引。

### 6.5 app/async_agent.py

负责：

- 兼容旧内存 SessionStore。
- 支持新的 PostgresSessionStore。
- 读取历史并传给模型。
- 保存本轮问答。

### 6.6 app/main.py

负责：

- 在 lifespan 中创建 PostgreSQL 连接池。
- 创建 PostgresSessionStore。
- 将 session store 传给聊天接口。
- 提供 `/health/db`。

## 7. 实际生产对标方案

| Day 58 的做法 | 生产中的常见方案 |
|---|---|
| 手写 SQL | SQLAlchemy、Prisma、Drizzle |
| `schema_migrations` | Alembic、Flyway、Liquibase |
| `AsyncConnectionPool` | SQLAlchemy Engine、PGBouncer |
| 聊天消息表 | 会话消息表、分表、归档 |
| 手动 commit/rollback | Unit of Work、事务装饰器 |
| Docker PostgreSQL | RDS、Cloud SQL、Aurora |
| `/health/db` | Kubernetes readiness probe |
| 环境变量 DATABASE_URL | Secret Manager、Vault、KMS |

生产系统还会：

- 使用 ORM 减少手写 SQL。
- 给消息表增加租户 ID。
- 对旧消息做归档和 TTL。
- 使用 PGBouncer 减少数据库连接压力。
- 给慢查询加监控和告警。
- 对数据库做定期备份和恢复演练。
- 使用读写分离和主从复制。

## 8. Day 58 开发中遇到的报错及原因

### 8.1 Ruff I001

原因：

import 顺序或空行不符合 isort。

解决：

```bash
.venv/bin/ruff check --fix ...
```

### 8.2 Ruff SIM117

原因：

嵌套 `async with` 可以合并成一个 `async with`。

解决：

```python
async with pool.connection() as conn, conn.cursor() as cur:
    ...
```

### 8.3 Ruff F401

原因：

`collections.abc.Sequence` 导入了但没有使用。

解决：

删除该 import。

### 8.4 Ruff RUF059

原因：

测试中解包出的 `conn` 没有使用。

解决：

改成 `_conn`。

### 8.5 测试中 coroutine 不支持异步上下文管理器

错误：

```text
TypeError: 'coroutine' object does not support
the asynchronous context manager protocol
```

原因：

测试里把 `conn` 设置成 `AsyncMock()`。

这会让：

```python
conn.cursor()
```

返回协程，而不是一个支持 `async with` 的对象。

解决：

在测试中实现：

```python
class AsyncContextManager:
    async def __aenter__(self):
        ...

    async def __aexit__(self, exc_type, exc, tb):
        ...
```

### 8.6 PoolTimeout: couldn't get a connection after 30 seconds

原因：

PostgreSQL 没有启动，或者 `DATABASE_URL` 主机或端口不对。

常见提示：

```text
Connection refused
localhost:5432
```

解决：

```bash
docker compose up -d postgres
docker compose ps postgres
.venv/bin/python -m app.db_cli check
```

### 8.7 集成测试消息数量不对

原因：

固定使用同一个 `session_id`，多次运行后数据越来越多。

解决：

每次使用随机 session_id：

```python
session_id = f"integration-{uuid.uuid4().hex}"
```

### 8.8 全量测试中 State 没有 session_store

原因：

`/chat` 和 `/chat/stream` 现在读取：

```python
app.state.session_store
```

但测试没有执行 lifespan，所以 state 中没有这个属性。

解决：

在测试中补：

```python
app.state.session_store = MagicMock()
```

### 8.9 fake_stream 参数不匹配

原因：

`stream_answer_question_async` 新增了：

```text
session_store=None
```

旧测试 fake 函数没有这个参数。

解决：

```python
async def fake_stream(
    client,
    session_id,
    question,
    retriever=None,
    semaphore=None,
    session_store=None,
):
    ...
```

## 9. Day 58 检查清单

- [ ] 已添加 `psycopg[binary,pool]`
- [ ] `.env` 已配置 `DATABASE_URL`
- [ ] `app/postgres.py` 已新增
- [ ] `app/postgres_session_store.py` 已新增
- [ ] `app/db_cli.py` 已新增
- [ ] `migrations/001_initial.sql` 已新增
- [ ] `chat_messages` 表已建立
- [ ] 聊天历史从 PostgreSQL 读取
- [ ] 一轮问答使用事务保存
- [ ] `/health/db` 已实现
- [ ] Docker PostgreSQL 服务已增加
- [ ] 数据库迁移命令可执行
- [ ] `tests/test_postgres_backend.py` 已通过
- [ ] 全量测试已通过

## 10. 当前已知限制

### 10.1 Agent run memory 仍是 SQLite

`/agent/memory/*` 和 LangGraph checkpoint 仍使用 SQLite。

Day 58 先把高频聊天会话迁到 PostgreSQL，后续再逐步迁移复杂 Agent 状态。

### 10.2 迁移工具还比较简单

当前是手写迁移脚本。

生产项目通常会使用 Alembic 管理迁移依赖、回滚和冲突。

### 10.3 数据库密码仍是普通环境变量

当前密码直接写在 `.env` 或 `docker-compose.yml` 中。

生产环境应使用 Secret Manager、Vault 或云平台 Secret。

### 10.4 还没有消息归档和 TTL

聊天消息会一直增长。

生产环境需要归档、清理或分区策略。

## 11. 下一步

Day 59 进入 Redis：

```text
Redis
  ->
缓存
  ->
短期会话
  ->
限流
  ->
幂等
```
