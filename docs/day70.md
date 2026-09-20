# Day 70 学习笔记

日期：2026-09-20

项目：`ai-job-agent`

主题：CI/CD、镜像仓库、单机服务器部署和公网访问

## 1. Day 70 完成了什么

第 10 周最后一天，把前 69 天的能力串成完整发布链路：

```text
本地提交代码
  ->
GitHub Actions 自动测试
  ->
GitHub Actions 构建镜像
  ->
推送镜像到 GHCR
  ->
服务器拉取镜像
  ->
Docker Compose 启动
  ->
Nginx 暴露公网
```

最终交付：

```text
CI workflow
  ->
Release Images workflow
  ->
Deploy workflow
  ->
docker-compose.2gb.yml
  ->
服务器反向代理
```

## 2. Day 70 改了哪些文件

| 文件 | 变化 | 作用 |
|---|---|---|
| `.github/workflows/ci.yml` | 新增/修改 | 自动 lint、test、build |
| `.github/workflows/release.yml` | 新增 | 构建并推送镜像 |
| `.github/workflows/deploy.yml` | 新增 | SSH 自动部署 |
| `Dockerfile` | 修改 | 使用清华 PyPI 源 |
| `frontend/Dockerfile` | 修改 | 使用 pnpm 和淘宝 npm 源 |
| `docker-compose.2gb.yml` | 修改 | 服务器只 pull 镜像，不本地构建 |
| `tests/test_ci_config.py` | 修改 | 检查 CI/CD 配置 |
| `tests/test_docker_config.py` | 修改 | 适配 pnpm 构建 |
| `tests/test_docker_production.py` | 修改 | 适配新 Dockerfile |
| `docs/day70.md` | 新增 | 当前文档 |

## 3. 完整 CI/CD 到部署流程图

```mermaid
flowchart TD
    A[本地提交代码] --> B[git push origin master]
    B --> C[GitHub 触发 CI]
    B --> D[GitHub 触发 Release Images]
    C --> E[backend lint 和 test]
    C --> F[frontend lint、test、build]
    C --> G[docker compose config 和 build]
    D --> H[构建 backend 镜像]
    D --> I[构建 frontend 镜像]
    H --> J[推送到 GHCR]
    I --> J
    J --> K[服务器 docker login]
    K --> L[docker compose pull]
    L --> M[docker compose up -d]
    M --> N[Nginx 反向代理]
    N --> O[公网访问]
```

### 3.1 本地到 GitHub

```text
git add
  ->
git commit
  ->
git push
```

### 3.2 GitHub Actions 到镜像仓库

```text
push 事件
  ->
workflow 启动
  ->
job 执行
  ->
docker build
  ->
docker push
```

### 3.3 镜像仓库到服务器

```text
服务器 docker login
  ->
docker compose pull
  ->
拉取 backend/frontend 镜像
  ->
docker compose up -d
  ->
容器运行
```

### 3.4 服务器到公网

```text
公网请求
  ->
Nginx 80/443
  ->
反向代理到 frontend:5173
  ->
前端页面
```

API 请求：

```text
公网请求 /jd/parse
  ->
Nginx
  ->
backend:8000
  ->
FastAPI
```

## 4. CI/CD 基础概念

### 4.1 CI

CI 是 Continuous Integration，持续集成。

它的工作是：

```text
每次代码提交后
  ->
自动运行 lint
  ->
自动运行测试
  ->
自动构建
```

目标：

```text
尽早发现代码错误
```

### 4.2 CD

CD 是 Continuous Delivery 或 Continuous Deployment。

常见含义：

```text
代码通过测试后
  ->
自动发布到环境
```

本项目现在使用：

```text
GitHub Actions 构建镜像
  ->
推送镜像
  ->
服务器手动或 SSH 部署
```

### 4.3 Workflow

Workflow 是 GitHub Actions 中的一套自动化流程。

对应文件：

```text
.github/workflows/ci.yml
.github/workflows/release.yml
.github/workflows/deploy.yml
```

### 4.4 Job

Job 是 Workflow 中的一个执行单元。

例如 CI workflow 中有：

```text
backend
frontend
docker
```

### 4.5 Step

Step 是 Job 中的具体步骤。

例如：

```yaml
- name: Install backend dependencies
  run: uv sync --frozen --all-groups
```

### 4.6 Runner

Runner 是真正执行 Job 的机器。

本项目使用：

```text
ubuntu-latest
```

这是 GitHub 提供的临时虚拟机。

### 4.7 Secret

Secret 是 GitHub 保存的敏感信息。

例如：

```text
DEPLOY_HOST
DEPLOY_USER
DEPLOY_SSH_KEY
```

Secret 不会显示在代码和普通日志中。

### 4.8 Environment

Environment 是部署环境：

```text
staging
production
```

可以给不同环境设置不同 Secret 和审批规则。

## 5. 镜像仓库概念

### 5.1 镜像仓库是什么

镜像仓库用于保存 Docker 镜像。

类似：

```text
代码仓库保存代码
镜像仓库保存镜像
```

### 5.2 常见镜像仓库

| 仓库 | 使用场景 |
|---|---|
| Docker Hub | 公共镜像 |
| GitHub Container Registry | GitHub 项目 |
| Alibaba Cloud ACR | 阿里云项目 |
| AWS ECR | AWS 项目 |
| Harbor | 公司自建 |

### 5.3 本项目 GHCR 地址

```text
ghcr.io/zhitong666/ai-agent-backend:latest
ghcr.io/zhitong666/ai-agent-frontend:latest
```

拆解：

```text
ghcr.io = registry
zhitong666 = namespace
ai-agent-backend = image name
latest = tag
```

## 6. Docker Compose 在部署中的角色

服务器上的 Compose 文件：

```yaml
services:
  backend:
    image: ghcr.io/zhitong666/ai-agent-backend:latest
```

含义：

```text
服务器只需要知道镜像地址
不需要知道如何构建镜像
```

启动：

```bash
docker compose pull
docker compose up -d
```

## 7. 本期报错分类整理

### 7.1 CI 测试断言过时

#### 现象

例如：

```text
test_frontend_dockerfile_builds_react
AssertionError: assert 'npm run build'
```

```text
test_dockerfile_pins_uv_and_skips_dev_dependencies
AssertionError
```

```text
test_ci_workflow_builds_docker_images
AssertionError
```

#### 原因

代码和 workflow 已经改变，但测试仍然检查旧内容。

例如：

```text
npm run build
```

改成了：

```text
pnpm build
```

#### 解决

更新测试断言，让测试匹配当前实现。

例如：

```python
assert "pnpm build" in dockerfile
```

以及：

```python
assert "docker compose -f docker-compose.2gb.yml build backend frontend" in ci_workflow
```

#### 原理

测试是代码行为的“合同”。代码改变时，合同也要同步更新，否则测试就失去意义。

### 7.2 Docker Hub 或公共镜像源连接超时

#### 现象

```text
python:3.12.9-slim failed to copy
read tcp ... connection timed out
```

```text
node:22-alpine TLS handshake timeout
```

```text
daocloud image mirror TLS handshake timeout
```

#### 原因

国内服务器直接访问 Docker Hub 不稳定。

公共镜像加速器也可能不可靠。

#### 解决

最终方案：

```text
不在服务器构建镜像
  ->
GitHub Actions 构建镜像
  ->
推送到 GHCR 或 ACR
  ->
服务器只拉取镜像
```

临时方案：

```bash
mkdir -p /etc/docker
vim /etc/docker/daemon.json
```

```json
{
  "registry-mirrors": [
    "https://docker.m.daocloud.io"
  ]
}
```

#### 原理

Docker 镜像构建依赖基础镜像。服务器到 Docker Hub 的网络链路可能很差，因此生产环境通常由 CI 环境构建，再通过镜像仓库传输。

### 7.3 npm 和 pip 依赖源慢

#### 现象

```text
RUN npm install 卡住很久
```

#### 原因

npm 官方源和 PyPI 官方源在国内访问慢。

#### 解决

前端 Dockerfile：

```dockerfile
RUN npm install -g pnpm@9 \
    --registry=https://registry.npmmirror.com \
    --no-audit \
    --no-fund

RUN pnpm config set registry https://registry.npmmirror.com
```

后端 Dockerfile：

```dockerfile
RUN pip install \
    --index-url https://pypi.tuna.tsinghua.edu.cn/simple \
    --trusted-host pypi.tuna.tsinghua.edu.cn \
    "uv==${UV_VERSION}"
```

### 7.4 frontend job 使用了根目录 Dockerfile

#### 现象

frontend job 出现：

```text
COPY pyproject.toml uv.lock
COPY app /app/app
COPY migrations /app/migrations
COPY data/knowledge_base.json
```

#### 原因

`release.yml` 中 frontend job 写成了：

```yaml
context: ./frontend
file: Dockerfile
```

这里的 `file: Dockerfile` 指向了根目录 Dockerfile，而不是 `frontend/Dockerfile`。

#### 解决

改成：

```yaml
context: ./frontend
file: frontend/Dockerfile
```

#### 原理

`context` 是构建上下文。

`file` 是 Dockerfile 路径。

两者必须匹配。

### 7.5 服务器 pull 时 backend/frontend 被跳过

#### 现象

```text
frontend Skipped - No image to be pulled
backend Skipped - No image to be pulled
```

然后：

```text
docker compose up -d
```

又去本地构建，导致 Docker Hub 超时。

#### 原因

服务器上的 Compose 文件仍然写 `build`，没有改成 `image`。

#### 解决

把：

```yaml
build:
  context: .
  dockerfile: Dockerfile
```

改成：

```yaml
image: ghcr.io/zhitong666/ai-agent-backend:latest
```

前端同理：

```yaml
image: ghcr.io/zhitong666/ai-agent-frontend:latest
```

#### 原理

服务器部署应该使用已经构建好的镜像，而不是再次构建。

### 7.6 PostgreSQL 密码中的特殊字符

#### 现象

数据库 DSN 可能出现解析错误。

#### 原因

如果密码包含：

```text
@
:
/
%
```

会破坏 DSN：

```text
postgresql://user:password@host:5432/db
```

#### 解决

避免使用 URL 特殊字符，或进行 URL 编码。

例如：

```text
Sunzhitong@0702
```

应写成：

```text
Sunzhitong%400702
```

推荐直接使用不含特殊字符的密码。

## 8. 实际生产 CI/CD 和部署方案对比

### 8.1 方案一：单机服务器手动部署

```mermaid
flowchart LR
    A[本地构建] --> B[上传到服务器]
    B --> C[服务器 Docker Compose 启动]
    C --> D[Nginx 暴露]
```

特点：

```text
简单
适合个人项目
不适合团队协作和频繁发布
```

### 8.2 方案二：单机服务器 + Docker Compose + Shell 脚本

```mermaid
flowchart LR
    A[服务器 git pull] --> B[docker compose pull]
    B --> C[docker compose up -d]
    C --> D[健康检查]
```

特点：

```text
比手动部署规范
适合单机项目
仍缺少自动测试和镜像构建
```

### 8.3 方案三：CI + 镜像仓库 + 单机服务器

```mermaid
flowchart LR
    A[git push] --> B[GitHub Actions CI]
    B --> C[构建镜像]
    C --> D[推送 GHCR/ACR]
    D --> E[服务器 docker compose pull]
    E --> F[服务器 up -d]
```

这是本项目当前使用的方案。

优点：

```text
自动化程度较高
服务器不需要构建
镜像可重复使用
适合个人和小团队
```

缺点：

```text
仍是单机
没有自动扩缩容
部署依赖服务器 SSH 或手动 pull
```

### 8.4 方案四：CI/CD + SSH 自动部署

```mermaid
flowchart LR
    A[git push] --> B[CI 测试]
    B --> C[构建镜像并推送]
    C --> D[SSH 登录服务器]
    D --> E[docker compose pull]
    E --> F[docker compose up -d]
```

适合：

```text
单机服务器
希望 push 后自动部署
```

### 8.5 方案五：Kubernetes 部署

```mermaid
flowchart LR
    A[git push] --> B[CI 测试]
    B --> C[构建镜像并推送]
    C --> D[Kubernetes Deployment]
    D --> E[Service]
    E --> F[Ingress]
```

优点：

```text
支持多副本
自动恢复
滚动发布
水平扩展
适合多服务、多节点
```

缺点：

```text
复杂度高
学习成本高
资源消耗大
对个人项目过重
```

### 8.6 方案六：GitOps + ArgoCD/Flux

```mermaid
flowchart LR
    A[修改 Git 配置仓库] --> B[GitOps Controller 监听变化]
    B --> C[自动同步 Kubernetes]
    C --> D[滚动更新]
```

适合：

```text
Kubernetes 环境
团队协作
需要审计和回滚
```

### 8.7 方案七：云平台托管

```text
阿里云 SAE
AWS ECS
腾讯云弹性容器
```

优点：

```text
无需管理服务器
自动扩缩容
平台提供日志、监控
```

缺点：

```text
有平台绑定
成本可能更高
定制能力有限
```

## 9. 方案横向对比

| 方案 | 部署方式 | 自动化 | 扩展性 | 复杂度 | 适合场景 |
|---|---:|---:|---:|---:|---|
| 手动部署 | 本地 build + scp | 低 | 低 | 低 | 个人学习 |
| Shell + Compose | 服务器 pull + up | 中 | 低 | 低 | 单机项目 |
| CI + Registry | GitHub 构建，服务器 pull | 中高 | 低 | 中 | 个人/小团队单机 |
| CI/CD + SSH | GitHub 构建，SSH 部署 | 高 | 低 | 中 | 单机自动发布 |
| Kubernetes | Registry + K8s | 高 | 高 | 高 | 多节点、高可用 |
| GitOps | Git 配置驱动 | 高 | 高 | 高 | K8s 团队协作 |
| 云托管 | 平台部署 | 高 | 高 | 中低 | 快速上线、无运维 |

## 10. 专业名词解释

### 10.1 GitOps

用 Git 仓库保存部署配置。

部署系统监听 Git 变化，并自动同步到环境。

### 10.2 Registry

镜像仓库。

### 10.3 Image Tag

镜像标签。

例如：

```text
latest
v1.0.0
abc123
```

生产环境不建议长期使用 `latest`。

### 10.4 Immutable Image

不可变镜像。

同一个 tag 的镜像内容不应变化。

生产推荐使用 commit SHA 或版本号。

### 10.5 Rolling Update

滚动更新。

一个一个替换实例，避免全部同时停机。

### 10.6 Blue-Green Deployment

蓝绿部署。

同时准备两套环境，切换流量。

### 10.7 Canary Deployment

金丝雀发布。

先让少量用户访问新版本，再逐步扩大。

### 10.8 SSH Deploy

通过 SSH 登录服务器执行部署命令。

### 10.9 Environment

部署环境：

```text
development
test
staging
production
```

## 11. 本项目当前部署方式

当前采用：

```text
CI
  +
Release Images
  +
单机 Docker Compose
  +
Nginx
```

这是：

```text
单机服务器 + CI + 镜像仓库
```

适合当前 2 核 2GB 个人服务器。

未来如果需要：

```text
多副本
自动恢复
滚动发布
多节点
```

再升级到 Kubernetes 或云托管平台。

## 12. 部署验证清单

- [ ] GitHub CI 通过
- [ ] Release Images 通过
- [ ] GHCR 中存在 backend 和 frontend 镜像
- [ ] 服务器已登录 GHCR 或 ACR
- [ ] 服务器 Compose 使用 image 而不是 build
- [ ] `docker compose pull` 能拉到镜像
- [ ] `docker compose up -d` 成功
- [ ] `docker compose ps` 显示 healthy
- [ ] 本地 `/health` 正常
- [ ] 前端 `curl -I 127.0.0.1:5173` 返回 200
- [ ] Nginx 配置正确
- [ ] 公网 IP 或域名可以访问
- [ ] 80/443 已开放
- [ ] 数据库、Redis、后端端口未暴露公网

## 13. 下一步

Day 70 完成后，第 10 周生产化闭环已经完成。

后续可以继续：

```text
接入真实域名和 HTTPS
配置数据库备份
配置日志告警
配置镜像版本 tag
配置自动 SSH 部署
尝试阿里云 ACR
尝试 Kubernetes 或云托管


```

## 14. 当前发布方案完整操作流程

### 14.1 本地提交前检查

```bash
cd /Users/zhitong/Desktop/AI-Agent
git status
```

检查：

```text
是否有未提交文件
是否意外包含 .env
是否包含本不该提交的数据文件
```

运行测试：

```bash
uv run ruff check .
uv run pytest -q
```

只有：

```text
ruff 无错误
pytest 全通过
```

才能提交。

### 14.2 提交并推送

```bash
git add -A
git status
git commit -m "feat: describe your change"
git push origin master
```

检查：

```text
git push 无报错
```

### 14.3 查看 GitHub Actions

打开：

```text
https://github.com/zhitong666/ai-agent/actions
```

确认：

```text
CI 成功
Release Images 成功
```

如果有失败：

```text
进入对应 run
查看失败 job
查看失败 step
修复后重新 push
```

### 14.4 确认镜像已经推送

打开：

```text
https://github.com/zhitong666/ai-agent/pkgs/container/ai-agent-backend
https://github.com/zhitong666/ai-agent/pkgs/container/ai-agent-frontend
```

确认：

```text
能看到 latest 和当前 commit SHA tag
```

本地获取当前完整 SHA：

```bash
git rev-parse HEAD
```

也可以获取短 SHA：

```bash
git rev-parse --short HEAD
```

当前 release workflow 会同时推送：

```text
ghcr.io/zhitong666/ai-agent-backend:<github.sha>
ghcr.io/zhitong666/ai-agent-backend:latest
```

和：

```text
ghcr.io/zhitong666/ai-agent-frontend:<github.sha>
ghcr.io/zhitong666/ai-agent-frontend:latest
```

部署时优先使用 `<github.sha>`，不要只依赖 `latest`。

### 14.5 登录服务器

```bash
ssh root@你的公网IP
```

进入项目目录：

```bash
cd /opt/apps/ai-job-agent
```

### 14.6 登录镜像仓库

#### 14.6.1 GHCR：

```bash
docker login ghcr.io -u zhitong666
```

输入 Personal Access Token。

#### 14.6.2 阿里云 ACR：

```bash
docker login --username=你的阿里云账号 registry.cn-hangzhou.aliyuncs.com
```

### 14.7 拉取最新代码

```bash
git pull --ff-only
```

检查：

```text
没有 merge conflict
```

### 14.8 设置本次发布镜像 tag

**在服务器 `.env` 中增加或更新：**

```dotenv
IMAGE_TAG=本次发布的完整 SHA
```

例如：

```dotenv
IMAGE_TAG=2725a08f9f0c91d8b8ec1e5d2aa54f707f0b7a2c
```

`docker-compose.2gb.yml` 中镜像应写成：

```yaml
  backend:
    image: ghcr.io/zhitong666/ai-agent-backend:${IMAGE_TAG:-latest}
```

```yaml
  frontend:
    image: ghcr.io/zhitong666/ai-agent-frontend:${IMAGE_TAG:-latest}
```

这样每次发布都有唯一版本，便于回滚。

### 14.9 校验 Compose

```bash
docker compose -f docker-compose.2gb.yml config -q
```

检查：

```text
没有输出错误
```

### 14.10 拉取指定版本镜像

```bash
docker compose -f docker-compose.2gb.yml pull
```

检查：

```text
backend Pulled
frontend Pulled
```

如果出现：

```text
Skipped - No image to be pulled
```

说明 Compose 中仍使用 `build`，需要改成 `image`。

### 14.11 启动指定版本服务

```bash
docker compose -f docker-compose.2gb.yml up -d
```

### 14.12 检查容器状态

```bash
docker compose -f docker-compose.2gb.yml ps
```

期望：

```text
postgres Up (healthy)
redis Up (healthy)
backend Up (healthy)
frontend Up
```

如果出现：

```text
Restarting
unhealthy
Exited
```

查看日志：

```bash
docker compose -f docker-compose.2gb.yml logs --tail=100 backend
docker compose -f docker-compose.2gb.yml logs --tail=100 frontend
```

### 14.13 检查接口

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/health/db
curl http://127.0.0.1:8000/health/redis
curl -I http://127.0.0.1:5173/
```

### 14.14 检查 Nginx

```bash
nginx -t
systemctl status nginx
```

重启 Nginx：

```bash
systemctl restart nginx
```

### 14.15 公网验证

```bash
curl -I http://你的公网IP/
curl http://你的公网IP/health
```

### 14.16 清理服务器垃圾资源

查看占用：

```bash
docker system df
docker image ls
docker ps -a
docker volume ls
docker builder du
```

清理构建缓存：

```bash
docker builder prune -f
```

清理悬空镜像：

```bash
docker image prune -f
```

清理未使用镜像：

```bash
docker image prune -a -f
```

清理停止容器：

```bash
docker container prune -f
```

检查 Volume：

```bash
docker volume ls
```

保留：

```text
postgres_data
redis_data
chroma_data
```

不要随意执行：

```bash
docker volume prune
docker compose down -v
docker system prune -a --volumes
```

因为这些会删除数据库或向量数据。

## 15. 五项后续操作必要性评估

### 15.1 接入真实域名和 HTTPS

必要性：

```text
中高
```

原因：

```text
面试演示时，使用 IP 也能访问
但域名 + HTTPS 更专业
浏览器不会显示“不安全”
```

建议：

```text
如果有域名和备案，建议做
如果只是快速演示，可以暂时用公网 IP
```

#### 完整步骤

1. 准备域名。

2. 在 DNS 服务商添加 A 记录：

```text
A  ai-agent  你的公网IP
```

3. 服务器安装 Caddy：

```bash
dnf install -y dnf-utils
yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
```

更简单可使用 Certbot + Nginx：

```bash
dnf install -y certbot python3-certbot-nginx
certbot --nginx -d ai-agent.example.com
```

4. 修改 Nginx：

```nginx
server {
    listen 80;
    server_name ai-agent.example.com;

    location / {
        proxy_pass http://127.0.0.1:5173;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

5. 检查并重启：

```bash
nginx -t
systemctl restart nginx
```

### 15.2 配置数据库备份

必要性：

```text
高
```

原因：

```text
数据库是核心资产
演示项目也可能需要回滚
```

建议：

```text
至少配置每天一次 PostgreSQL 备份
```

#### 完整步骤

创建备份目录：

```bash
mkdir -p /opt/backups/postgres
```

创建备份脚本：

```bash
vim /opt/backups/backup_postgres.sh
```

写入：

```bash
#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="/opt/backups/postgres"
DATE=$(date +%F_%H-%M-%S)

docker compose -f /opt/apps/ai-job-agent/docker-compose.2gb.yml \
  exec -T postgres \
  pg_dump -U ai_agent -d ai_job_agent \
  > "${BACKUP_DIR}/ai_job_agent_${DATE}.sql"

find "${BACKUP_DIR}" -name "*.sql" -mtime +7 -delete
```

授权：

```bash
chmod +x /opt/backups/backup_postgres.sh
```

设置每天凌晨 3 点备份：

```bash
crontab -e
```

增加：

```cron
0 3 * * * /opt/backups/backup_postgres.sh
```

### 15.2.1 验证数据库备份

#### 1. 检查脚本权限

```bash
ls -l /opt/backups/backup_postgres.sh
```

应看到：

```text
-rwxr-xr-x
```

如果不可执行：

```bash
chmod +x /opt/backups/backup_postgres.sh
```

#### 2. 手动执行一次备份

```bash
bash /opt/backups/backup_postgres.sh
```

#### 3. 检查备份文件是否生成

```bash
ls -lh /opt/backups/postgres
```

应看到类似：

```text
ai_job_agent_2026-09-20_03-00-01.sql
```

文件大小不能是 0。

#### 4. 检查 SQL 文件开头

```bash
head -20 /opt/backups/postgres/最新的备份文件.sql
```

通常应看到：

```text
--
-- PostgreSQL database dump
--
```

#### 5. 检查备份中是否有关键表

```bash
grep -n "CREATE TABLE" /opt/backups/postgres/最新的备份文件.sql | head -20
```

应看到：

```text
CREATE TABLE public.chat_messages
CREATE TABLE public.users
```

#### 6. 在临时数据库中做恢复验证

创建临时测试库：

```bash
docker compose -f /opt/apps/ai-job-agent/docker-compose.2gb.yml \
  exec -T postgres \
  psql -U ai_agent -c "DROP DATABASE IF EXISTS backup_test;"

docker compose -f /opt/apps/ai-job-agent/docker-compose.2gb.yml \
  exec -T postgres \
  psql -U ai_agent -c "CREATE DATABASE backup_test;"
```

导入备份：

```bash
docker compose -f /opt/apps/ai-job-agent/docker-compose.2gb.yml \
  exec -T postgres \
  psql -U ai_agent -d backup_test \
  < /opt/backups/postgres/最新的备份文件.sql
```

检查表：

```bash
docker compose -f /opt/apps/ai-job-agent/docker-compose.2gb.yml \
  exec -T postgres \
  psql -U ai_agent -d backup_test \
  -c "\dt"
```

验证完成后删除临时库：

```bash
docker compose -f /opt/apps/ai-job-agent/docker-compose.2gb.yml \
  exec -T postgres \
  psql -U ai_agent -c "DROP DATABASE backup_test;"
```

#### 7. 检查 cron 配置

```bash
crontab -l
```

应包含：

```cron
0 3 * * * /opt/backups/backup_postgres.sh
```

#### 8. 检查 cron 日志

```bash
grep CRON /var/log/cron | tail -20
```

如果看不到日志，确认 cron 服务：

```bash
systemctl status crond
systemctl enable crond
```









### 15.3 配置日志告警

必要性：

```text
低
```

原因：

```text
个人面试演示项目
不需要 7x24 告警
手动查看 docker logs 已足够
```

建议：

```text
暂不接入复杂告警系统
可以只配置一个简单的健康检查
```

#### 轻量方案

使用 cron 每分钟检查 `/health`：

```bash
vim /opt/backups/health_check.sh
```

写入：

```bash
#!/usr/bin/env bash

if ! curl -fsS http://127.0.0.1:8000/health >/dev/null; then
  echo "backend health check failed"
fi
```

设置 cron：

```cron
* * * * * /opt/backups/health_check.sh
```

如果后续需要，再接入 Prometheus + Grafana 或云监控。

### 15.4 配置镜像版本 tag

必要性：

```text
中高
```

原因：

```text
latest 会导致无法准确回滚
发布记录不清晰
```

建议：

```text
至少使用 commit SHA 作为 tag
```

#### 完整步骤

在 `release.yml` 中给镜像 tag 增加短 SHA：

```yaml
      - uses: docker/build-push-action@v6
        with:
          context: .
          file: Dockerfile
          push: true
          tags: |
            ghcr.io/zhitong666/ai-agent-backend:${{ github.sha }}
            ghcr.io/zhitong666/ai-agent-backend:latest
```

前端：

```yaml
          tags: |
            ghcr.io/zhitong666/ai-agent-frontend:${{ github.sha }}
            ghcr.io/zhitong666/ai-agent-frontend:latest
```

服务器 Compose 中可以指定：

```yaml
image: ghcr.io/zhitong666/ai-agent-backend:<commit-sha>
```

这样每次发布都可追踪，可回滚。

### 15.5 配置自动 SSH 部署

必要性：

```text
低到中
```

原因：

```text
个人项目可以手动 ssh 登录部署
自动部署会增加密钥和权限管理复杂度
```

建议：

```text
面试演示项目暂不必须
但如果想展示完整 CI/CD 能力，可以做
```

#### 完整步骤

1. 在服务器创建专用部署用户：

```bash
useradd -m deploy
```

2. 生成 SSH key：

```bash
ssh-keygen -t ed25519
```

3. 把公钥加入 GitHub Secrets：

```text
DEPLOY_SSH_KEY
DEPLOY_HOST
DEPLOY_USER
DEPLOY_PORT
```

4. 修改 `.github/workflows/deploy.yml`：

```yaml
      - name: Deploy over SSH
        uses: appleboy/ssh-action@v1.2.2
        with:
          host: ${{ secrets.DEPLOY_HOST }}
          username: ${{ secrets.DEPLOY_USER }}
          key: ${{ secrets.DEPLOY_SSH_KEY }}
          port: ${{ secrets.DEPLOY_PORT }}
          script: |
            cd /opt/apps/ai-job-agent
            git pull --ff-only
            docker compose -f docker-compose.2gb.yml pull
            docker compose -f docker-compose.2gb.yml up -d
            docker compose -f docker-compose.2gb.yml ps
```

5. 手动触发：

```bash
gh workflow run deploy.yml -f environment=production
```

## 16. 面试演示项目优先级建议

| 操作 | 优先级 | 是否建议现在做 |
|---|---:|---|
| 数据库备份 | 高 | 建议做 |
| 镜像版本 tag | 中高 | 建议做 |
| 域名和 HTTPS | 中高 | 有条件就做 |
| 自动 SSH 部署 | 中 | 可选 |
| 日志告警 | 低 | 暂缓 |

如果时间有限，优先做：

```text
数据库备份
镜像版本 tag
域名和 HTTPS
```

这三项最能体现生产意识。
```
