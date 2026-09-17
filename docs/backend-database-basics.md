# 后端生产基础：数据库、Docker 与部署

日期：2026-09-17

目标：补齐 AI Agent 后端工程师需要的数据库、容器和部署基础知识。

## 0. 为什么需要理解数据库和部署

前端通常关心：

```text
页面怎么渲染
  ->
状态怎么管理
  ->
接口怎么调用
```

后端生产服务还要关心：

```text
数据存在哪里
  ->
服务重启后数据还在吗
  ->
多个用户同时访问怎么办
  ->
怎么部署到服务器
  ->
服务挂了怎么恢复
```

本文围绕数据库、Docker 和实际部署流程展开。

## 1. 内存数据与持久化

### 1.1 内存数据

Python 变量保存在内存中。

例如：

```python
sessions = {}
```

特点：

- 读写很快。
- 服务重启后消失。
- 多个进程无法共享。

### 1.2 持久化数据

数据库把数据写入磁盘。

特点：

- 读写比内存慢。
- 服务重启后仍然存在。
- 多个进程可以共享。

### 1.3 类比

```text
内存：
草稿纸上的内容。

数据库：
写进正式文档并保存到硬盘。
```

生产系统中，会话、用户、订单、任务状态都需要持久化。

## 2. 关系型数据库

### 2.1 关系型数据库是什么

关系型数据库把数据组织成表格。

本项目使用的 PostgreSQL 就是关系型数据库。

### 2.2 表、行、列

```text
表：一个实体集合
行：一条记录
列：记录的一个属性
```

例如 `chat_messages`：

```text
id       session_id    role        content
1        s1            user        你好
2        s1            assistant   你好，有什么可以帮你
```

### 2.3 主键

主键是唯一标识一行数据的字段。

```sql
id BIGSERIAL PRIMARY KEY
```

每插入一行，`id` 自动增加。

作用：

- 准确找到某一行。
- 建立表之间的关系。
- 避免重复数据。

### 2.4 外键

外键用来连接两张表。

当前项目暂时没有外键，但生产系统通常会有：

```text
users 表
  ->
sessions 表
  ->
messages 表
```

例如：

```text
sessions.user_id 引用 users.id
messages.session_id 引用 sessions.id
```

## 3. SQL 基础

### 3.1 查询

```sql
SELECT role, content
FROM chat_messages
WHERE session_id = $1
ORDER BY id ASC;
```

含义：

- `SELECT`：选择哪些列。
- `FROM`：从哪张表。
- `WHERE`：过滤条件。
- `ORDER BY`：排序。

### 3.2 插入

```sql
INSERT INTO chat_messages
    (session_id, role, content)
VALUES ($1, 'user', $2);
```

`$1`、`$2` 是参数占位符。

使用参数而不是字符串拼接，可以防止 SQL 注入。

### 3.3 更新

```sql
UPDATE chat_messages
SET content = $1
WHERE id = $2;
```

### 3.4 删除

```sql
DELETE FROM chat_messages
WHERE session_id = $1;
```

## 4. 事务

### 4.1 为什么需要事务

假设一次问答要写两条消息：

```text
user: 你好
assistant: 你好
```

如果第一句成功，第二句失败，就会出现半条对话。

事务保证：

```text
两条都成功，修改生效
任意一条失败，全部撤销
```

### 4.2 commit

`commit` 表示提交事务，让修改永久生效。

### 4.3 rollback

`rollback` 表示回滚事务，撤销当前事务中的修改。

### 4.4 类比

```text
转账：

从 A 扣 100 元。
给 B 加 100 元。

两步必须一起成功。

如果给 B 加钱失败，A 的扣款也要撤销。
```

### 4.5 本项目的事务

```python
async with self._pool.connection() as conn:
    try:
        await insert_user_message()
        await insert_assistant_message()
        await conn.commit()
    except Exception:
        await conn.rollback()
        raise
```

## 5. 索引

### 5.1 什么是索引

索引像书的目录。

没有索引时，数据库可能要从第一行找到最后一行。

有索引后，数据库可以更快定位数据。

### 5.2 本项目索引

```sql
CREATE INDEX idx_chat_messages_session_id
ON chat_messages (session_id, id);
```

因为经常执行：

```sql
WHERE session_id = ?
ORDER BY id ASC
```

索引能提升这类查询。

### 5.3 索引不是越多越好

索引会占用磁盘空间，还会降低写入速度。

应该根据真实查询需求建立索引。

## 6. 数据库连接池

### 6.1 为什么不能每个请求都新建连接

每次新建数据库连接都要：

```text
建立 TCP 连接
  ->
数据库认证
  ->
执行 SQL
  ->
关闭连接
```

高并发时这会非常慢。

### 6.2 连接池

连接池预先维护一组连接：

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

请求完成后，连接不会关闭，而是归还连接池。

### 6.3 min_size 和 max_size

```text
min_size：
连接池最少保持几个连接。

max_size：
连接池最多允许几个连接。
```

设置太小，请求会等待。

设置太大，数据库压力过大。

## 7. 数据库迁移

### 7.1 什么是迁移

迁移是数据库结构的版本管理。

开发过程中，表结构会变化：

```text
增加字段
  ->
删除字段
  ->
增加索引
  ->
修改类型
```

迁移文件记录这些变化。

### 7.2 本项目迁移流程

```mermaid
flowchart TD
    A[读取 migrations 目录] --> B[按文件名排序]
    B --> C{版本是否已执行}
    C -->|是| D[跳过]
    C -->|否| E[执行 SQL]
    E --> F[记录版本到 schema_migrations]
    F --> G[commit]
    E -->|失败| H[rollback]
    H --> I[抛出错误]
    D --> J[完成]
    G --> J
```

### 7.3 迁移工具

本项目先使用简单的 `app/db_cli.py`。

生产项目通常使用：

- Alembic。
- Flyway。
- Liquibase。
- Prisma Migrate。

## 8. Docker 基础

### 8.1 镜像和容器

镜像：

```text
打包好的应用和运行环境
```

容器：

```text
镜像运行起来后的实例
```

类比：

```text
镜像：
一个菜谱模板。

容器：
根据模板实际做出来的一桌菜。
```

### 8.2 Dockerfile

Dockerfile 描述如何构建镜像。

本项目 Dockerfile：

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY app ./app
COPY migrations ./migrations
COPY data ./data
RUN pip install --no-cache-dir uv \
    && uv sync --frozen --no-dev --no-install-project
EXPOSE 8000
CMD [".venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

解释：

- `FROM`：基础镜像。
- `WORKDIR`：容器内工作目录。
- `COPY`：把本地文件复制到镜像。
- `RUN`：构建镜像时执行命令。
- `EXPOSE`：声明服务端口。
- `CMD`：容器启动时执行命令。

### 8.3 容器和虚拟机的区别

```text
虚拟机：
模拟完整操作系统，启动慢，资源占用大。

容器：
共享宿主机内核，启动快，资源占用小。
```

前端类比：

```text
虚拟机：
每台电脑都装一个完整系统。

容器：
多个项目共享同一个 Node.js 和浏览器运行时，但各自有隔离环境。
```

## 9. Docker Compose

### 9.1 为什么需要 Compose

一个项目可能有多个服务：

```text
PostgreSQL
  ->
Qdrant
  ->
Backend
  ->
Frontend
```

Docker Compose 用一个 YAML 文件描述这些服务。

### 9.2 本项目 docker-compose.yml

```yaml
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: ai_agent
      POSTGRES_PASSWORD: ai_agent
      POSTGRES_DB: ai_job_agent
    ports:
      - "5432:5432"
    volumes:
      - ./data/postgres:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ai_agent -d ai_job_agent"]
      interval: 5s
      timeout: 5s
      retries: 10
```

解释：

- `image`：使用哪个镜像。
- `environment`：容器环境变量。
- `ports`：宿主机端口映射到容器端口。
- `volumes`：宿主机目录挂载到容器目录。
- `healthcheck`：健康检查。

### 9.3 ports

```text
宿主机 5432 -> 容器 5432
```

含义：

```text
访问本机 localhost:5432
  ->
转发到容器 5432
```

### 9.4 volumes

```text
宿主机 ./data/postgres
  ->
容器 /var/lib/postgresql/data
```

如果没有 volume：

```text
容器删除后，数据库数据也消失。
```

有 volume 后：

```text
数据保存在宿主机目录，容器重建后数据仍然存在。
```

### 9.5 depends_on

```yaml
backend:
  depends_on:
    postgres:
      condition: service_healthy
```

表示：

```text
PostgreSQL 健康后，再启动 backend。
```

### 9.6 服务启动流程图

```mermaid
flowchart TD
    A[docker compose up] --> B[创建网络]
    B --> C[启动 postgres]
    C --> D[healthcheck]
    D --> E{postgres 健康吗}
    E -->|否| D
    E -->|是| F[启动 backend]
    F --> G[backend 执行数据库迁移]
    G --> H[启动 uvicorn]
    H --> I[启动 frontend]
```

## 10. 常见 Docker 命令

### 10.1 启动服务

```bash
docker compose up -d postgres
```

`-d` 表示后台运行。

### 10.2 查看服务状态

```bash
docker compose ps
```

### 10.3 查看日志

```bash
docker compose logs postgres
docker compose logs backend
```

### 10.4 停止服务

```bash
docker compose down
```

### 10.5 停止并删除数据卷

```bash
docker compose down -v
```

注意：

```text
-v 会删除匿名卷，也可能影响数据。
```

## 11. 后端部署流程

### 11.1 本地开发

```bash
docker compose up -d postgres
.venv/bin/python -m app.db_cli migrate
.venv/bin/uvicorn app.main:app --reload
```

### 11.2 容器化部署

```bash
docker compose build backend
docker compose up -d postgres backend
```

### 11.3 生产部署流程

```mermaid
flowchart LR
    A[开发完成] --> B[运行测试]
    B --> C[构建镜像]
    C --> D[推送到镜像仓库]
    D --> E[部署到服务器]
    E --> F[执行数据库迁移]
    F --> G[启动新容器]
    G --> H[健康检查]
    H --> I[切换流量]
    I --> J[监控日志和指标]
```

### 11.4 生产部署不只 Docker

Docker 解决应用打包和运行问题。

生产环境还需要：

- 负载均衡。
- 多副本。
- HTTPS。
- 域名。
- 日志收集。
- 监控告警。
- 自动扩缩容。
- 数据库备份。

## 12. 环境变量和密钥

### 12.1 环境变量

不同环境使用不同配置：

```text
本地：
DATABASE_URL=localhost

Docker：
DATABASE_URL=postgres

生产：
DATABASE_URL=生产数据库地址
```

不要把生产密码写死在代码里。

### 12.2 本地 .env

```text
DATABASE_URL=postgresql://ai_agent:ai_agent@localhost:5432/ai_job_agent
```

### 12.3 Docker environment

```yaml
environment:
  DATABASE_URL: postgresql://ai_agent:ai_agent@postgres:5432/ai_job_agent
```

### 12.4 生产 Secret

生产环境应使用：

- Vault。
- KMS。
- AWS Secrets Manager。
- GCP Secret Manager。
- GitHub Actions Secrets。

## 13. 健康检查

### 13.1 为什么需要健康检查

健康检查用于判断服务是否真正可用。

一个进程存在，不代表它能处理请求。

例如：

```text
数据库连接断开
  ->
服务还活着
  ->
但接口可能失败
```

### 13.2 本项目数据库健康检查

```python
@app.get("/health/db")
async def health_db():
    async with app.state.postgres_pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT 1")
            row = await cur.fetchone()

    return {"status": "ok"}
```

如果数据库不可用，返回 503。

### 13.3 两种健康检查

```text
liveness：
服务是否还活着。

readiness：
服务是否准备好接收流量。
```

数据库检查更接近 readiness。

## 14. 本项目 Day58 生产架构

```mermaid
flowchart LR
    A[客户端] --> B[FastAPI backend]
    B --> C[PostgresSessionStore]
    C --> D[AsyncConnectionPool]
    D --> E[PostgreSQL]
    E --> F[chat_messages]
    B --> G[AsyncOpenAI]
    G --> H[DeepSeek]
    B --> I[RAG Retriever]
```

Docker Compose 中：

```text
postgres 容器
  ->
backend 容器
  ->
frontend 容器
```

## 15. 常见问题

### 15.1 connection refused on localhost:5432

原因：

PostgreSQL 没有启动。

解决：

```bash
docker compose up -d postgres
docker compose ps postgres
```

### 15.2 PoolTimeout

原因：

连接池拿不到连接。

可能：

- 数据库不可用。
- 连接池 max_size 太小。
- 数据库连接被占满。

### 15.3 端口被占用

原因：

本机已经有一个服务占用 5432。

解决：

- 修改宿主机端口。
- 停止旧服务。
- 使用容器网络连接。

### 15.4 容器重启后数据消失

原因：

没有配置 volume。

解决：

```yaml
volumes:
  - ./data/postgres:/var/lib/postgresql/data
```

### 15.5 容器内 localhost 不对

Docker 容器之间访问时：

```text
不能用 localhost。
```

应该使用服务名：

```text
postgres
```

例如：

```text
postgresql://ai_agent:ai_agent@postgres:5432/ai_job_agent
```

## 16. 当前与生产的差距

| 当前项目 | 生产项目 |
|---|---|
| Docker Compose 单机 | Kubernetes、云平台多实例 |
| 环境变量保存密码 | Secret Manager |
| 手写迁移脚本 | Alembic/Flyway |
| 单 PostgreSQL | 主从、备份、读写分离 |
| 本地日志 | 集中式日志和监控 |
| 单容器 backend | 多副本 + 负载均衡 |

这些会在后续 Day59 到 Day63 逐步补齐。
