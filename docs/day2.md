# Day 2 学习笔记

日期：2026-08-16

项目：`ai-job-agent`

目标：使用 FastAPI 和 Pydantic 创建两个本地 HTTP 接口，理解请求、响应、路由、请求体校验和接口测试。

## 1. 今天具体做了什么

Day 2 在本地启动了一个 HTTP 服务，并编写了两个接口。

接口分别是：

| 方法 | 路径 | 作用 |
|---|---|---|
| `GET` | `/health` | 健康检查，返回服务是否正常 |
| `POST` | `/jd/parse` | 接收一段 JD 文本，暂时返回固定的岗位结构化数据 |

服务端入口文件是 `app/main.py`，其中：

```python
app = FastAPI(title="AI Job Agent", version="0.1.0")
```

`app` 是整个应用的入口。随后使用装饰器把 Python 函数绑定到 HTTP 路由：

```python
@app.get("/health")
def health():
    return {"status": "ok"}
```

这里的含义是：当客户端向 `/health` 发起 `GET` 请求时，FastAPI 调用 `health()` 函数，并把这个函数的返回值转换为 JSON。

## 2. 本地服务、网络和运行框架

### 2.1 本地服务是怎么跑起来的

执行：

```bash
uv run uvicorn app.main:app --reload
```

这条命令拆开看：

- `app.main` 表示 Python 模块 `app/main.py`
- `:app` 表示这个模块里的 `app` 变量
- `uvicorn` 是 ASGI 服务器，负责接收网络请求并运行 FastAPI 应用

所以本地服务不是只靠 Python 标准库，而是用了：

- FastAPI，用来写接口和路由
- Uvicorn，用来真正监听端口和处理 HTTP 请求

FastAPI 负责“接口逻辑”，Uvicorn 负责“网络接收”。

### 2.2 访问地址的含义

```text
http://127.0.0.1:8000/health
```

| 部分 | 含义 |
|---|---|
| `http` | 使用的应用层协议 |
| `127.0.0.1` | 本机回环地址，只在本机可访问 |
| `8000` | 端口号，标识本机上的一个具体服务 |
| `/health` | 请求路径，服务根据它匹配路由 |

`127.0.0.1` 也叫 loopback address。客户端请求不会真正离开本机，而是直接回到本机服务。

### 2.3 一次请求发生了什么

以 `POST /jd/parse` 为例：

1. 客户端发送 HTTP POST 请求
2. Uvicorn 收到请求并转给 FastAPI
3. FastAPI 根据方法和路径匹配到 `parse_jd`
4. FastAPI 读取 JSON 请求体并校验
5. 函数返回 Python 对象
6. FastAPI 把对象序列化为 JSON
7. Uvicorn 把 HTTP 响应返回给客户端

请求包含：

- 方法：`POST`
- 路径：`/jd/parse`
- 请求头：例如 `Content-Type: application/json`
- 请求体：例如 `{"text":"某公司 JD"}`

响应包含：

- 状态码：例如 `200` 成功，`422` 参数校验失败
- 响应体：JSON 数据

## 3. FastAPI 路由和请求体校验

### 3.1 路由

FastAPI 通过装饰器定义路由：

```python
@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/jd/parse")
def parse_jd(request: ParseRequest):
    ...
```

路由由 HTTP 方法和路径组成。客户端请求必须同时匹配方法和路径，才会进入对应函数。

### 3.2 请求体校验

定义请求体模型：

```python
from pydantic import BaseModel, Field


class ParseRequest(BaseModel):
    text: str = Field(min_length=1)
```

然后在路由函数中作为参数：

```python
@app.post("/jd/parse")
def parse_jd(request: ParseRequest):
    ...
```

FastAPI 会自动：

- 读取请求体
- 尝试转换为 `ParseRequest`
- 校验 `text` 是不是字符串
- 校验 `text` 长度是否至少为 1
- 校验失败时返回 `422`
- 校验成功后把对象传入函数

这相当于在 Express 中手工写的请求解析和校验，被 FastAPI 自动完成了。

## 4. Pydantic BaseModel、Literal、Field

### 4.1 BaseModel

TypeScript 的 `interface` 只在编译期存在，运行时不校验。

```ts
interface Job {
  company: string
  title: string
}
```

Pydantic 的 `BaseModel` 会在运行时校验数据：

```python
from pydantic import BaseModel


class JobDescription(BaseModel):
    company: str
    title: str
```

如果传入：

```python
JobDescription(company=123, title="工程师")
```

运行时会报错，因为 `company` 需要字符串，而不是数字。

### 4.2 Literal

`Literal` 限制字段只能使用固定的值。

```python
from typing import Literal


class JobDescription(BaseModel):
    seniority: Literal["junior", "mid", "senior", "staff", "unknown"]
```

它接近 TypeScript 中的字符串字面量联合类型：

```ts
type Seniority = "junior" | "mid" | "senior" | "staff" | "unknown"
```

### 4.3 Field

`Field` 用来给字段添加额外规则和默认值：

```python
responsibilities: list[str] = Field(default_factory=list)
```

使用 `default_factory=list` 而不是 `default=[]` 的原因：

- 如果多个对象共享同一个默认列表，可能互相影响
- `default_factory=list` 每次创建新对象时都生成新的空列表

类似的 TypeScript 习惯是不要在默认参数里直接使用共享引用：

```ts
function createJob(items: string[] = []) {
  return { items }
}
```

虽然 TS 写法常见，但 Pydantic 用 `default_factory` 更安全。

## 5. response_model 的作用

路由可以声明返回模型：

```python
@app.post("/jd/parse", response_model=JobDescription)
def parse_jd(request: ParseRequest):
    return ...
```

`response_model` 的作用是：

1. 校验函数返回的数据是否符合 `JobDescription`
2. 自动把返回的 Python 对象序列化为 JSON
3. 控制响应中暴露哪些字段
4. 生成 OpenAPI 文档时展示返回结构

如果没有 `response_model`，FastAPI 会直接序列化返回值，但不会按模型严格校验输出结构。

## 6. TestClient 测试接口的方法

### 6.1 什么是 TestClient

```python
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
```

`TestClient` 可以模拟客户端请求，但不会真正占用端口。它相当于在测试进程内部发送请求，不需要先启动 Uvicorn。

如果做过 Node.js 后端测试，它类似 `supertest`：

```ts
const response = await request(app).get("/health")
```

### 6.2 测试 GET

```python
def test_health():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

### 6.3 测试 POST

```python
def test_parse_jd_returns_job_description():
    response = client.post(
        "/jd/parse",
        json={"text": "某公司 AI Agent 工程师 JD"},
    )

    assert response.status_code == 200
    assert response.json()["company"] == "示例公司"
```

### 6.4 测试参数校验失败

```python
def test_parse_jd_rejects_empty_text():
    response = client.post("/jd/parse", json={"text": ""})

    assert response.status_code == 422
```

这里的 `422` 来自请求体校验，不是业务代码主动返回的。

## 7. 今天遇到的报错和解决方式

### 7.1 uv: command not found

错误：

```text
zsh: command not found: uv
```

原因：

安装 `uv` 后，当前终端没有重新加载 `~/.zshrc`。

解决：

```bash
source ~/.zshrc
uv --version
```

如果还不行，检查 `uv` 是否在 `~/.local/bin`。

### 7.2 pytest 找不到 app 模块

错误：

```text
ModuleNotFoundError: No module named 'app'
```

原因：

pytest 没有把项目根目录加入导入路径。

解决：

在 `pyproject.toml` 中加入：

```toml
[tool.pytest.ini_options]
pythonpath = ["."]
```

### 7.3 pytest 找不到 app.day1

错误：

```text
ModuleNotFoundError: No module named 'app.day1'
```

原因：

`app/day1.py` 或 `app/__init__.py` 文件被删除，目录中只剩缓存。

解决：

恢复源文件后重新运行测试。

### 7.4 端口被占用或服务无法启动

如果启动服务时看到：

```text
error while attempting to bind on address ('127.0.0.1', 8000)
```

说明 `8000` 端口已经被其他程序使用。

解决：

```bash
lsof -i :8000
```

找到占用进程后停止它，或换一个端口：

```bash
uv run uvicorn app.main:app --reload --port 8001
```

## 8. Python 基础语法与 TypeScript 对照

| 概念 | Python | TypeScript |
|---|---|---|
| 定义函数 | `def hello():` | `function hello() {}` 或箭头函数 |
| 类型标注 | `def parse(text: str) -> str:` | `function parse(text: string): string {}` |
| 字典类型 | `dict[str, str]` | `Record<string, string>` |
| 数组类型 | `list[str]` | `string[]` |
| 空值 | `None` | `null` 或 `undefined` |
| 抛异常 | `raise ValueError("...")` | `throw new Error("...")` |
| 捕获异常 | `try/except` | `try/catch` |
| 导入模块 | `from app.models import JobDescription` | `import { JobDescription } from "./models"` |
| 装饰器 | `@app.get("/health")` | 装饰器语法，但 TS 中常用于类 |
| 主入口 | `if __name__ == "__main__":` | 没有直接等价写法 |

### 8.1 Python 函数

```python
def add(a: int, b: int) -> int:
    return a + b
```

对比 TypeScript：

```ts
function add(a: number, b: number): number {
  return a + b
}
```

### 8.2 Python 导入

Python 使用模块路径导入：

```python
from app.models import JobDescription
```

这表示从 `app/models.py` 中导入 `JobDescription`。

TypeScript 使用文件路径导入：

```ts
import { JobDescription } from "./models"
```

### 8.3 Python 装饰器

```python
@app.get("/health")
def health():
    return {"status": "ok"}
```

装饰器会把这个函数注册到 FastAPI 应用中。可以把它理解为“给函数附加一个能力”。

TypeScript 中也有装饰器语法，但在日常 React 项目里较少直接使用。

## 9. Day 2 检查清单

- [ ] 安装 `fastapi`、`uvicorn`、`pydantic`、`httpx`
- [ ] 创建 `app/models.py`
- [ ] 创建 `app/main.py`
- [ ] 创建 `tests/test_api.py`
- [ ] 测试全部通过
- [ ] 服务能启动并访问 `/docs`
- [ ] 能用 curl 访问 `/health`
- [ ] 能用 curl 访问 `/jd/parse`
- [ ] 理解路由、请求体校验和 response_model

## 10. 明天要做什么

Day 3 将把 `/jd/parse` 中的固定返回数据替换为真实 LLM 调用，并学习 Prompt 和结构化输出。
