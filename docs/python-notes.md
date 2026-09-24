# Python 语言与后端基础笔记

这份笔记专门写给前端背景、主要熟悉 JavaScript 和 TypeScript 的开发者。所有内容尽量结合当前 `ai-job-agent` 项目的真实代码，并用 JS/TS 做类比。

---

## 1. TypedDict 与 Pydantic 的关系和区别

### 1.1 它们分别解决什么问题

| 工具 | 主要作用 | 运行时是否校验 | 类比 |
|---|---|---|---|
| `TypedDict` | 给普通字典加静态类型提示 | 不校验 | TypeScript 的 `interface` |
| `Pydantic BaseModel` | 在运行时解析、校验、转换数据 | 校验并转换 | TypeScript 的 `zod` |

`TypedDict` 更接近 TypeScript 的 `interface`：

```ts
interface ParsedJob {
  company: string
  title: string
}
```

TypeScript 的 `interface` 在编译成 JavaScript 后会消失，运行时不会检查对象字段。Python 的 `TypedDict` 也一样，主要给 IDE、类型检查器使用，运行时它仍然是一个普通 `dict`。

### 1.2 TypedDict 的语法

```python
from typing import TypedDict


class ParsedJob(TypedDict):
    company: str
    title: str


def parse_text(text: str) -> ParsedJob:
    return {
        "company": "字节跳动",
        "title": "AI Agent 工程师",
    }
```

你完全可以多传字段或少传字段，代码运行时不会自动报错：

```python
job: ParsedJob = {
    "company": "字节跳动",
    "title": "AI Agent 工程师",
    "salary": "50k",  # 运行时不会报错
}
```

当前项目里的 `app/day1.py` 使用了 `TypedDict`，它的目的是先理解“字典 + 类型提示”这种基础写法。

### 1.3 Pydantic 的语法

```python
from pydantic import BaseModel, Field
from typing import Literal


class JobDescription(BaseModel):
    company: str = Field(..., min_length=1, description="公司名称")
    title: str = Field(..., min_length=1, description="岗位名称")
    seniority: Literal["junior", "mid", "senior", "staff", "unknown"] = "unknown"
    requirements: list[str] = Field(default_factory=list)
```

与 `TypedDict` 最大的不同是，Pydantic 会在运行时真正创建对象、校验字段、转换类型，并且能生成 JSON Schema。

### 1.4 项目里分别用在哪里

- 早期 `app/day1.py` 用 `TypedDict` 学习“字典的结构应该怎样描述”。
- 正式 API、LLM 输出、Agent 状态用 Pydantic，例如：
  - `app/models.py` 的 `JobDescription`、`JobAnalysis`、`ChatResponse`
  - `app/agent_state.py` 的 `AgentState`
  - `app/auth_models.py` 的请求和 Token 模型

原因是：LLM 返回的内容是不可信字符串，必须先解析 JSON，再用 Pydantic 校验，才能进入业务逻辑。`TypedDict` 没有运行时校验能力，不适合承担这个边界。

### 1.5 记忆方式

```text
TypedDict = 只给 dict 穿上类型外衣，运行时还是 dict。
Pydantic = 数据进入系统时的门卫，会检查、转换、报错、生成 Schema。
```

类比：

```text
TypeScript interface -> 编译期类型
Python TypedDict   -> 静态类型提示
TypeScript zod     -> 运行时校验
Python Pydantic    -> 运行时校验
```

---

## 2. Python 推导式

### 2.1 你看到的那行代码

```python
new_job = {key: value for key, value in job.items() if value}
```

这是字典推导式，等价于：

```python
new_job = {}

for key, value in job.items():
    if value:
        new_job[key] = value
```

翻译成 JS/TS：

```ts
const newJob = Object.fromEntries(
  Object.entries(job).filter(([, value]) => value),
)
```

### 2.2 四种常见推导式

列表推导式：

```python
numbers = [1, 2, 3, 4]
squares = [n * n for n in numbers]
# [1, 4, 9, 16]

evens = [n for n in numbers if n % 2 == 0]
# [2, 4]
```

字典推导式：

```python
job = {"company": "字节", "title": "AI Agent", "extra": ""}
filtered = {key: value for key, value in job.items() if value}
# {"company": "字节", "title": "AI Agent"}
```

集合推导式：

```python
words = ["a", "b", "a", "c"]
unique = {word for word in words}
# {"a", "b", "c"}
```

生成器推导式：

```python
gen = (n * 2 for n in range(5))
# 不会立刻计算全部，而是按需生成
```

### 2.3 语法规则

基本格式：

```text
[表达式 for 临时变量 in 可迭代对象 if 条件]
```

执行顺序：

1. 遍历可迭代对象。
2. 把每个元素赋值给临时变量。
3. 如果有 `if`，条件为真才继续。
4. 计算最前面的表达式。
5. 收集结果。

你还可以在表达式里写三元表达式：

```python
labels = ["even" if n % 2 == 0 else "odd" for n in numbers]
```

但三元表达式不能替代 `elif`。复杂的过滤建议写普通 `for` 循环，可读性更重要。

### 2.4 使用场景

适合：

- 简单映射：`[transform(item) for item in items]`
- 简单过滤：`[item for item in items if condition]`
- 字典清洗：过滤空值、转换 key/value
- 简单去重：集合推导式

不适合：

- 一个推导式里写三层以上嵌套
- 复杂分支
- 需要逐步调试的逻辑

---

## 3. dict 和 list 的常用操作

### 3.1 dict

Python 的 `dict` 可以类比 JS 的 `Object` 或 `Map`。

| 方法 | 作用 | 是否修改原对象 | 示例 |
|---|---|---|---|
| `d[key]` | 取值，不存在会报 `KeyError` | 否 | `job["title"]` |
| `d.get(key)` | 安全取值，不存在返回 `None` | 否 | `job.get("domain")` |
| `d.get(key, default)` | 不存在时返回默认值 | 否 | `job.get("domain", "unknown")` |
| `d[key] = value` | 设置值 | 是 | `job["domain"] = "AI"` |
| `d.update(other)` | 批量更新 | 是 | `job.update({"level": "mid"})` |
| `d.setdefault(key, default)` | 不存在则写入默认值并返回 | 可能修改 | `d.setdefault("count", 0)` |
| `d.pop(key)` | 删除并返回值 | 是 | `job.pop("title")` |
| `d.pop(key, default)` | 不存在时返回默认值 | 是 | `job.pop("x", None)` |
| `d.popitem()` | 删除最后一个键值对 | 是 | `d.popitem()` |
| `d.keys()` | 返回键视图 | 否 | `job.keys()` |
| `d.values()` | 返回值视图 | 否 | `job.values()` |
| `d.items()` | 返回键值对视图 | 否 | `job.items()` |
| `"key" in d` | 判断键是否存在 | 否 | `"title" in job` |
| `len(d)` | 获取键值对数量 | 否 | `len(job)` |
| `del d[key]` | 删除键 | 是 | `del job["extra"]` |
| `d.clear()` | 清空字典 | 是 | `d.clear()` |
| `d.copy()` | 浅拷贝 | 否 | `new = d.copy()` |
| `d1 | d2` | 合并两个字典，右边覆盖左边 | 否 | `{**a, **b}` |

示例：

```python
job = {
    "company": "字节跳动",
    "title": "AI Agent 工程师",
}

job.get("domain")                 # None
job.get("domain", "unknown")      # "unknown"
job.setdefault("requirements", [])

for key, value in job.items():
    print(key, value)
```

### 3.2 list

Python 的 `list` 更接近 JS 的动态数组 `Array`。

| 方法 | 作用 | 是否修改原对象 | 示例 |
|---|---|---|---|
| `list.append(item)` | 在末尾追加 | 是 | `items.append("RAG")` |
| `list.extend(iterable)` | 合并另一个可迭代对象 | 是 | `items.extend(["a", "b"])` |
| `list.insert(index, item)` | 在指定位置插入 | 是 | `items.insert(0, "first")` |
| `list.pop(index)` | 删除并返回指定位置元素，默认最后 | 是 | `items.pop()` |
| `list.remove(value)` | 删除第一个匹配值 | 是 | `items.remove("RAG")` |
| `list.clear()` | 清空 | 是 | `items.clear()` |
| `list.index(value)` | 获取第一个匹配下标 | 否 | `items.index("RAG")` |
| `list.count(value)` | 统计出现次数 | 否 | `items.count("RAG")` |
| `list.sort()` | 原地排序 | 是 | `items.sort()` |
| `list.reverse()` | 原地反转 | 是 | `items.reverse()` |
| `list.copy()` | 浅拷贝 | 否 | `new = items.copy()` |
| `len(list)` | 获取长度 | 否 | `len(items)` |
| `item in list` | 判断是否存在 | 否 | `"RAG" in items` |
| 切片 `list[start:end:step]` | 获取子列表 | 否 | `items[1:3]` |

示例：

```python
skills = []
skills.append("Python")       # ["Python"]
skills.append("FastAPI")      # ["Python", "FastAPI"]
skills.insert(0, "TypeScript") # ["TypeScript", "Python", "FastAPI"]

first = skills.pop(0)         # "TypeScript"
```

### 3.3 JS/TS 对照

| Python | JavaScript / TypeScript |
|---|---|
| `dict` | `Object` 或 `Map` |
| `list` | `Array` |
| `tuple` | 类似只读数组，但更强调不可变 |
| `set` | `Set` |
| `None` | `null` / `undefined`，但不完全一样 |
| `in` | `in`、`includes`、`has` |
| `list.append()` | `array.push()` |
| `list.insert(0, x)` | `array.unshift(x)` |
| `list.pop()` | `array.pop()` |
| `dict.get(key, default)` | `obj[key] ?? default` |

注意：Python 的 `list.pop()` 默认删除最后一项，而 JS 的 `array.pop()` 也是最后一项，这一点相同。

---

## 4. Python 和 TypeScript 的 async/await 运行机制差异

### 4.1 表面语法很像

Python：

```python
async def fetch_data():
    data = await api_call()
    return data
```

TypeScript：

```ts
async function fetchData() {
  const data = await apiCall()
  return data
}
```

表面都是“等待异步结果”。但底层对象和启动方式不同。

### 4.2 JS/TS 的模型

JS 是单线程加事件循环：

- `async function` 返回 `Promise`。
- `await` 会把当前函数挂起，让出执行权给事件循环。
- Promise 完成后，回调进入微任务队列。
- 浏览器和 Node.js 自带事件循环，你调用 `fetchData()` 后它会自动运行。

```ts
const promise = fetchData()
console.log(promise instanceof Promise) // true
```

### 4.3 Python 的模型

Python 也是单线程协作式并发，但对象不同：

- `async def` 返回的是 coroutine 对象，不是自动开始执行。
- 必须有一个事件循环来驱动 coroutine。
- `asyncio.run()` 会启动事件循环。
- `await` 在遇到可等待对象时，挂起当前 coroutine，把控制权交回事件循环。

```python
import asyncio


async def fetch_data():
    return "data"


coroutine = fetch_data()
print(coroutine)  # <coroutine object fetch_data at ...>

result = asyncio.run(coroutine)
```

### 4.4 关键差异

| 维度 | Python | JavaScript / TypeScript |
|---|---|---|
| `async` 函数返回 | coroutine 对象 | `Promise` |
| 谁启动事件循环 | 需要 `asyncio.run()` 或框架 | JS 运行时自动拥有事件循环 |
| `await` 后面 | 可等待对象，如 coroutine、Task、Future | 通常是 Promise |
| 并发 API | `asyncio.gather()`、`asyncio.create_task()` | `Promise.all()`、`Promise.race()` |
| 取消 | 通常用 Task 的 `cancel()` | `AbortController` |
| 错误处理 | 类似同步 `try/except` | `try/catch` + Promise rejection |
| 生成器 | 普通生成器、异步生成器 | `function*`、`async function*` |

### 4.5 Python 里常见的启动方式

```python
import asyncio


async def fetch_one():
    return "one"


async def fetch_two():
    return "two"


async def main():
    one, two = await asyncio.gather(fetch_one(), fetch_two())
    print(one, two)


asyncio.run(main())
```

在 FastAPI 中，框架已经替你运行了事件循环，所以路由可以直接写成：

```python
@app.get("/health")
async def health():
    return {"status": "ok"}
```

这里的 `async def` 表示这个路由在事件循环中运行，遇到 I/O 可以交出控制权，从而服务其他请求。

### 4.6 记忆方式

```text
JS 的 async/await：
  单线程 + 自带事件循环 + Promise + 微任务队列。

Python 的 async/await：
  单线程 + 事件循环需要显式启动 + coroutine/Task + 显式 await 挂起。
```

类比：

- JS 的 `async function` 像一个已经接上电源的遥控车，你按开关它就动。
- Python 的 `async def` 更像一组遥控车，但你需要先用 `asyncio.run()` 打开总电源。

---

## 5. FastAPI、Uvicorn、ASGI 和 lifespan

### 5.1 FastAPI 主要做什么

FastAPI 是 Python 的 Web 应用框架，主要负责：

- 定义路由和 HTTP 方法。
- 解析请求参数、请求体和 Header。
- 使用 Pydantic 校验输入输出。
- 依赖注入。
- 自动生成 OpenAPI 和 Swagger 文档。
- 返回 JSON、SSE、文件等响应。

它负责的是“应用逻辑”，不负责直接监听 socket。项目中：

```python
app = FastAPI(
    title="AI Job Agent",
    version="0.1.0",
    lifespan=lifespan,
)
```

### 5.2 FastAPI 是不是构建应用入口

可以说 `app = FastAPI(...)` 是应用的 Python 对象入口，但真正让这个应用在网络上运行的是 Uvicorn。

类比：

```text
FastAPI = Express / NestJS 应用实例
Uvicorn = 真正启动 HTTP 服务的运行时
```

启动命令：

```bash
uv run uvicorn app.main:app --reload
```

解释：

- `app.main`：Python 模块路径。
- `app`：该模块里的 `FastAPI()` 实例。
- `--reload`：开发时自动重载。

### 5.3 ASGI 是什么

ASGI 是 Asynchronous Server Gateway Interface，异步服务器网关接口。

它规定了：

```text
服务器 -> 应用
```

之间如何传递：

- `scope`：请求元数据，例如方法、路径、Header。
- `receive`：接收请求体。
- `send`：发送响应。

可以把它理解为“Python Web 应用和服务器之间的合同”。FastAPI 是 ASGI 应用，Uvicorn 是 ASGI 服务器。

对比其他语言：

| 概念 | Python | JavaScript/TypeScript | Java |
|---|---|---|---|
| Web 框架 | FastAPI / Flask / Django | Express / NestJS / Next.js | Spring MVC / JAX-RS |
| 服务器 | Uvicorn / Hypercorn | Node.js HTTP server | Tomcat / Netty |
| 接口规范 | ASGI / WSGI | 通常由运行时直接提供 | Servlet |

### 5.4 lifespan 参数代表什么

`lifespan` 是一个异步上下文管理器，负责应用启动前和关闭后的资源管理。

```python
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app):
    # 启动时执行
    app.state.async_client = create_async_client()
    app.state.postgres_pool = await create_postgres_pool()
    app.state.redis = create_redis_client()
    app.state.queue = await create_queue()

    try:
        yield
    finally:
        # 关闭时执行
        await app.state.async_client.close()
        await app.state.postgres_pool.close()
        await app.state.queue.aclose()
        await app.state.redis.aclose()
```

`yield` 之前是启动逻辑，`yield` 之后是关闭逻辑。

类比：

- NestJS 的 `onModuleInit` 和 `onModuleDestroy`
- React 的 `useEffect` 清理函数
- Express 中 `server.listen` 前后的初始化逻辑

在项目中，`lifespan` 会创建：

- 异步 LLM 客户端
- LLM 并发信号量
- PostgreSQL 连接池
- Redis 客户端
- arq 任务队列
- 限流器
- 任务存储
- 用户仓储
- Redis + PostgreSQL 会话存储

---

## 6. Pydantic 基本概念

### 6.1 BaseModel

`BaseModel` 是所有 Pydantic 模型的父类。

```python
from pydantic import BaseModel


class User(BaseModel):
    username: str
    age: int
```

使用：

```python
user = User(username="alex", age=18)
print(user.username)      # "alex"
print(user.model_dump())  # {"username": "alex", "age": 18}
```

如果类型不匹配，Pydantic 会尝试转换：

```python
User(username="alex", age="18")
# age 被转换为 18
```

无法转换时会抛 `ValidationError`。

### 6.2 Field

`Field` 用来给字段增加约束和元信息。

```python
from pydantic import BaseModel, Field


class JobDescription(BaseModel):
    company: str = Field(..., min_length=1, description="公司名称")
    title: str = Field(..., min_length=1, description="岗位名称")
    keywords: list[str] = Field(default_factory=list)
```

重要规则：

- `Field(...)` 表示必填。
- `Field(default=...)` 表示有默认值。
- `Field(default_factory=list)` 表示每次创建对象时生成新的空列表，避免共享可变默认值。
- `description` 会进入 JSON Schema，用于文档和 LLM Function Calling 的参数说明。

### 6.3 Literal

`Literal` 限制值只能是若干固定值之一。

```python
from typing import Literal
from pydantic import BaseModel


class JobDescription(BaseModel):
    seniority: Literal["junior", "mid", "senior", "staff", "unknown"] = "unknown"
```

类比 TS：

```ts
type Seniority = "junior" | "mid" | "senior" | "staff" | "unknown"
```

### 6.4 可选字段

```python
from pydantic import BaseModel


class Response(BaseModel):
    message: str | None = None
```

等价于 `Optional[str] = None`。

### 6.5 嵌套模型

```python
from pydantic import BaseModel


class Source(BaseModel):
    chunk_id: str
    title: str


class ChatResponse(BaseModel):
    reply: str
    sources: list[Source] = []
```

`ChatResponse` 可以校验 `sources` 里的每个对象都符合 `Source`。

### 6.6 校验和转换方法

```python
data = {"company": "字节", "title": "AI Agent"}
job = JobDescription.model_validate(data)

as_dict = job.model_dump()
as_json = job.model_dump_json()
schema = JobDescription.model_json_schema()
```

项目里最重要的用法：

```python
parse_and_validate(raw_json, JobDescription)
```

这会把模型返回的 JSON 字符串解析成 `JobDescription`。

### 6.7 field_validator

用于自定义字段校验。

```python
from pydantic import BaseModel, field_validator


class Config(BaseModel):
    environment: str

    @field_validator("environment")
    @classmethod
    def check_environment(cls, value: str) -> str:
        allowed = {"development", "test", "staging", "production"}

        if value not in allowed:
            raise ValueError("environment is invalid")

        return value
```

### 6.8 BaseSettings

`BaseSettings` 用于从环境变量或 `.env` 文件读取配置。

```python
from pydantic_settings import BaseSettings
from pydantic import Field, SecretStr


class Settings(BaseSettings):
    openai_api_key: SecretStr = Field(min_length=1)
    openai_model: str = "deepseek-chat"
    llm_max_concurrency: int = 10
```

项目中的 `app/config.py` 就是典型用法。

### 6.9 SecretStr

`SecretStr` 用于保护敏感字段，避免在日志和错误信息中直接暴露。

```python
settings.openai_api_key.get_secret_value()
```

### 6.10 常用类型速查

| Pydantic / Python | TS 类比 |
|---|---|
| `str` | `string` |
| `int` | `number` |
| `float` | `number` |
| `bool` | `boolean` |
| `list[str]` | `string[]` |
| `dict[str, int]` | `Record<string, number>` |
| `str \| None` | `string \| null` |
| `Literal["a", "b"]` | `"a" \| "b"` |
| `BaseModel` | interface + zod schema |

---

## 7. `client.chat.completions.create()` 到底做了什么

### 7.1 创建客户端

```python
from openai import OpenAI


client = OpenAI(
    api_key="your-api-key",
    base_url="https://api.deepseek.com",
)
```

这一步只是创建一个客户端对象，保存：

- API Key
- Base URL
- 超时时间
- 可能的重试配置
- 其他默认设置

它通常不会立刻发起网络请求。

### 7.2 发起一次对话补全

```python
response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[
        {"role": "system", "content": "你是 AI 岗位咨询助手。"},
        {"role": "user", "content": "FastAPI 需要掌握什么？"},
    ],
)
```

这一步相当于：

```text
POST {base_url}/chat/completions
Authorization: Bearer {api_key}
Content-Type: application/json

{
  "model": "deepseek-chat",
  "messages": [...]
}
```

所以你的理解基本正确：

- `OpenAI(...)` 根据 `api_key` 和 `base_url` 创建客户端。
- `.chat.completions.create()` 向三方大模型服务发起 HTTP 请求。
- 因为 DeepSeek 提供 OpenAI 兼容接口，所以可以用 OpenAI SDK 调 DeepSeek。

### 7.3 常用参数

| 参数 | 含义 | 场景 |
|---|---|---|
| `model` | 使用哪个模型 | `deepseek-chat`、`deepseek-reasoner` |
| `messages` | 对话消息数组 | system、user、assistant、tool |
| `tools` | 可调用工具 Schema | Function Calling |
| `tool_choice` | 控制模型是否必须调用工具 | `auto`、`none`、指定函数 |
| `temperature` | 随机性 | 生成类任务可调高，结构化任务应调低 |
| `top_p` | 核采样概率 | 控制候选 token 范围 |
| `max_tokens` | 最大生成 token 数 | 控制长度和成本 |
| `stop` | 停止词 | 让模型提前停止 |
| `stream` | 是否流式返回 | 前端逐字显示 |
| `response_format` | 输出格式 | JSON 对象等 |
| `timeout` | 请求超时时间 | 防止长时间卡住 |

### 7.4 messages 的角色

| role | 含义 |
|---|---|
| `system` | 系统角色、全局指令 |
| `user` | 用户输入 |
| `assistant` | 模型历史回答或模型建议的 tool_calls |
| `tool` | 工具执行结果，必须带 `tool_call_id` |

### 7.5 Function Calling 示例

```python
response = client.chat.completions.create(
    model="deepseek-chat",
    messages=messages,
    tools=[
        {
            "type": "function",
            "function": {
                "name": "search_knowledge",
                "description": "在岗位知识库中检索相关内容",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"}
                    },
                    "required": ["query"],
                },
            },
        }
    ],
    tool_choice="auto",
)
```

模型返回的不是工具执行结果，而是“我希望调用哪个工具，参数是什么”。真正执行工具的是 Python 代码。

### 7.6 流式请求

```python
response = client.chat.completions.create(
    model="deepseek-chat",
    messages=messages,
    stream=True,
)

for chunk in response:
    delta = chunk.choices[0].delta.content

    if delta:
        print(delta, end="")
```

`stream=True` 表示模型边生成边返回，不需要等完整答案生成完。

### 7.7 异步客户端

项目里生产链路使用：

```python
from openai import AsyncOpenAI


client = AsyncOpenAI(
    api_key=settings.openai_api_key.get_secret_value(),
    base_url=settings.openai_base_url,
)

response = await client.chat.completions.create(
    model="deepseek-chat",
    messages=messages,
)
```

`AsyncOpenAI` 对应异步版本，配合 `await` 使用，避免阻塞 FastAPI 事件循环。

---

## 8. `unittest.mock.patch` 详解

### 8.1 它解决什么问题

测试时，我们不想真的：

- 请求 DeepSeek
- 连接 PostgreSQL
- 调用 Redis
- 睡眠几秒

`patch` 可以在测试期间临时替换某个对象、函数或属性，测试结束后自动恢复。

类比前端：

```text
Python patch = Jest jest.spyOn / vi.spyOn / mockImplementation
```

### 8.2 基本语法

```python
from unittest.mock import patch


with patch("app.agent.parse_job_description", return_value=fake_job):
    result = analyze_job("JD 文本")
```

解释：

- `"app.agent.parse_job_description"` 是一个字符串路径。
- 它表示“去 `app.agent` 模块里，替换名字叫 `parse_job_description` 的对象”。
- `return_value=fake_job` 表示调用这个替换对象时，返回 `fake_job`。
- `with` 块结束后，原来的对象自动恢复。

### 8.3 参数

| 参数 | 含义 |
|---|---|
| `target` | 字符串路径，例如 `"app.agent.session_store"` |
| `new` | 替换成哪个对象 |
| `return_value` | 被替换对象被调用时返回什么 |
| `side_effect` | 被调用时抛异常、依次返回不同值，或执行函数 |
| `autospec` | 让 mock 自动模拟原对象签名 |

示例：

```python
with patch("app.tools.apply_job", return_value="已投递") as mock_apply:
    result = apply_job_tool()

    mock_apply.assert_called_once()
```

`side_effect`：

```python
mock.side_effect = [1, 2, 3]   # 第 1 次返回 1，第 2 次返回 2
mock.side_effect = RuntimeError("boom")  # 调用时抛异常
```

### 8.4 patch 对象属性

```python
with patch.object(
    agent.client.chat.completions,
    "create",
    return_value=response,
) as mock_create:
    agent.answer_question("s1", "什么是 RAG", retriever=FakeRetriever())
```

`patch.object` 适合已经有真实对象，只需要替换它的某个方法。

### 8.5 一次 patch 多个对象

```python
with patch("app.agent.session_store", store), patch.object(
    agent.client.chat.completions,
    "create",
    return_value=response,
) as mock_create:
    ...
```

这里用逗号连接多个 `patch` 上下文管理器。

### 8.6 最容易踩的坑

必须 patch “使用处”，不是“定义处”。

例如 `app/agent.py`：

```python
from app.memory import session_store
```

这时 `app.agent` 模块里有一个自己的名字 `session_store`。

正确：

```python
patch("app.agent.session_store", store)
```

错误：

```python
patch("app.memory.session_store", store)
```

原因：如果 patch 原始模块，`app.agent.session_store` 仍然是原来的对象，测试不会生效。

### 8.7 MagicMock 和 AsyncMock

- `MagicMock`：普通 mock。
- `AsyncMock`：异步 mock，调用后返回可等待对象。

项目测试里经常这样写：

```python
from unittest.mock import AsyncMock, MagicMock

client.chat.completions.create = AsyncMock(return_value=fake_response)
```

因为异步代码中：

```python
await client.chat.completions.create(...)
```

需要一个异步 mock，否则 `await` 普通对象会报错。

---

## 9. 流式输出中的 async/await 和 yield

### 9.1 普通函数和生成器的区别

普通函数：

```python
def build_list():
    return [1, 2, 3]


result = build_list()
# result 立刻是完整列表
```

生成器函数：

```python
def build_stream():
    yield 1
    yield 2
    yield 3
```

调用它不会立刻执行完，而是返回一个生成器：

```python
gen = build_stream()
next(gen)  # 1
next(gen)  # 2
next(gen)  # 3
```

`yield` 的意思是：

```text
暂停当前函数，先把值交出去。
下次继续执行时，从 yield 的下一行接着跑。
```

类比 JS：

```js
function* buildStream() {
  yield 1
  yield 2
  yield 3
}
```

### 9.2 异步生成器

```python
async def stream_answer():
    yield sse_event("chunk", "你")
    yield sse_event("chunk", "好")
    yield sse_event("done", "")
```

这是异步生成器：

- `async def` 表示它是一个异步函数。
- `yield` 表示它一次产生一个值。
- 消费者需要用 `async for` 或异步迭代。

```python
async for event in stream_answer():
    print(event)
```

### 9.3 项目中流式输出的实际流程

```python
response = await client.chat.completions.create(
    model=...,
    messages=...,
    stream=True,
)

async for chunk in response:
    delta = chunk.choices[0].delta.content

    if delta:
        yield sse_event("chunk", delta)

yield sse_event("done", "")
```

流程：

1. `await client.chat.completions.create(...)` 发起流式请求。
2. 得到一个异步可迭代对象 `response`。
3. `async for chunk in response` 每次拿到一小块模型输出。
4. `yield` 把这一小块转成 SSE 字符串，交给 FastAPI。
5. FastAPI 再把 SSE 字符串写给浏览器。
6. 浏览器边接收边渲染。

### 9.4 为什么这样不会一次性占满内存

如果没有生成器，可能要先把完整答案拼出来：

```python
parts = []

async for chunk in response:
    parts.append(chunk)

full_answer = "".join(parts)
return full_answer
```

这样所有内容都保存在内存里，直到最后才返回。

使用 `yield`：

```python
async for chunk in response:
    yield chunk
```

可以拿到一块就返回一块，内存占用更低，用户也能更快看到内容。

类比：

- `return` 像下载完整文件后再播放。
- `yield` 像在线视频流，边加载边播放。

### 9.5 TypeScript 对应语法

普通生成器：

```ts
function* buildStream(): Generator<number> {
  yield 1
  yield 2
  yield 3
}
```

异步生成器：

```ts
async function* streamAnswer(): AsyncGenerator<string> {
  yield "chunk: 你"
  yield "chunk: 好"
}
```

消费：

```ts
for await (const value of streamAnswer()) {
  console.log(value)
}
```

### 9.6 Python 与 TS 在流式生成器上的差异

| 维度 | Python | JavaScript / TypeScript |
|---|---|---|
| 普通生成器 | `def f(): yield` | `function* f()` |
| 异步生成器 | `async def f(): yield` | `async function* f()` |
| 消费普通生成器 | `for item in gen` | `for (const item of gen)` |
| 消费异步生成器 | `async for item in agen` | `for await (const item of agen)` |
| 驱动异步生成器 | 需要事件循环 | JS 运行时自带事件循环 |
| 流式来源 | 常配合 `StreamingResponse` | 常配合 `ReadableStream` |

---

## 10. 项目文件对照

| 问题 | 项目对应文件 |
|---|---|
| TypedDict 和 Pydantic | `app/day1.py`、`app/models.py`、`app/structured_output.py` |
| 推导式 | `docs/day1.md`、`docs/day8.md` |
| dict / list 操作 | `docs/day1.md` |
| async/await | `app/async_agent.py`、`app/async_llm.py` |
| FastAPI / lifespan | `app/main.py` |
| Uvicorn / ASGI | `app/main.py`、`Dockerfile` |
| Pydantic 概念 | `app/models.py`、`app/config.py` |
| OpenAI 对话补全 | `app/llm.py`、`app/async_llm.py`、`app/function_calling.py` |
| patch | `tests/test_chat.py`、`tests/test_react.py`、`tests/test_async_backend.py` |
| 流式输出 | `app/streaming.py`、`app/async_agent.py`、`frontend/src/App.tsx` |

---

## 11. 给前端开发者的速记清单

1. Python 用缩进表示代码块，TS 用 `{}`。
2. Python 的 `None` 类似 `null`，但不等于 `undefined`。
3. `dict` 类似对象，`list` 类似数组，`tuple` 类似不可变数组。
4. Pydantic 类似 zod，TypedDict 类似 interface。
5. Python 的 `async def` 返回 coroutine，需要事件循环驱动。
6. FastAPI 负责应用逻辑，Uvicorn 负责网络服务。
7. ASGI 是 Python Web 服务器和异步应用之间的接口标准。
8. `lifespan` 是启动和关闭资源的生命周期钩子。
9. `yield` 不是 return，而是暂停并交出一个值。
10. `patch` 是在测试期间临时替换依赖，测试结束自动恢复。
11. 调 DeepSeek 本质是向 OpenAI 兼容接口发 HTTP 请求。
12. Function Calling 中模型只返回“调用哪个工具”，真正的工具执行在 Python 代码里。

---

## 12. `sum(1 for ... if ...)` 到底是什么意思

`docs/day34.md` 中有类似写法：

```python
matched = sum(
    1
    for phrase in phrases
    if normalize_text(phrase) in normalized
)
```

### 12.1 先拆开看

这行代码里有两个语法叠在一起：

1. 生成器表达式。
2. `sum()`。

生成器部分：

```python
1 for phrase in phrases if normalize_text(phrase) in normalized
```

它逐个遍历 `phrases`：

- 如果某个 `phrase` 满足条件，就产生一个 `1`。
- 如果不满足，就什么都不产生。

`sum()` 再把这些 `1` 全部加起来。

因此 `matched` 最终不是某个短语，而是“满足条件的短语数量”。

### 12.2 为什么参数传 `1`

这里的 `1` 不是业务数据，而是计数单位。

可以理解为：

```text
每命中一个目标，就往总分里加 1 分。
```

### 12.3 等价的普通 for 循环

```python
matched = 0

for phrase in phrases:
    if normalize_text(phrase) in normalized:
        matched += 1
```

### 12.4 等价的 JS/TS

```ts
const matched = phrases.filter(
  (phrase) => normalized.includes(normalizeText(phrase)),
).length
```

### 12.5 为什么要用 `sum(1 for ... if ...)`

它不用先创建中间列表，内存更轻：

```python
matched = sum(
    1 for phrase in phrases
    if normalize_text(phrase) in normalized
)
```

而下面这种写法会先生成整个列表：

```python
matched = len([
    phrase
    for phrase in phrases
    if normalize_text(phrase) in normalized
])
```

在当前场景里 `phrases` 通常很小，两种写法结果相同；但生成器写法是更通用的计数技巧。

### 12.6 执行顺序

```text
1. 创建生成器表达式，此时还没有开始计算。
2. sum() 开始迭代生成器。
3. 取出第一个 phrase。
4. 检查 if 条件。
5. 如果成立，产生数字 1。
6. sum() 把 1 加到累计值。
7. 重复 3 到 6，直到所有 phrase 处理完。
8. 返回最终累计值。
```

---

## 13. `text.encode("utf-8")`、字节和 bit

`docs/day36.md` 中有：

```python
hashlib.sha1(text.encode("utf-8")).hexdigest()
```

### 13.1 `text.encode("utf-8")` 做了什么

Python 里的 `str` 是文本，`bytes` 是二进制数据。两者不是一回事。

```python
text = "你好"
data = text.encode("utf-8")

print(type(text))  # <class 'str'>
print(type(data))  # <class 'bytes'>
print(data)        # b'\xe4\xbd\xa0\xe5\xa5\xbd'
```

`encode` 把“字符”按照 UTF-8 规则转换成“字节序列”。

### 13.2 转完之后大概长什么样

英文字母通常占 1 个字节：

```python
"A".encode("utf-8")
# b'A'
```

中文通常占 3 个字节：

```python
"你".encode("utf-8")
# b'\xe4\xbd\xa0'
```

所以：

```python
len("A".encode("utf-8"))   # 1
len("你".encode("utf-8"))  # 3
```

这也能解释为什么不能用字符长度直接估算 token 或字节大小。

### 13.3 为什么要转成字节

哈希算法、加密、网络传输、文件存储这些底层操作，处理的是字节，不是 Python 的 `str` 对象。

`hashlib.sha1()` 需要传入 bytes：

```python
import hashlib

hashlib.sha1("abc".encode("utf-8")).hexdigest()
# a9993e364706816aba3e25717850c26c9cd0d89d
```

如果直接传字符串会报错：

```python
hashlib.sha1("abc")
# TypeError: Strings must be encoded before hashing
```

### 13.4 byte 和 bit 的关系

```text
bit 是最小单位，只有 0 或 1。
byte 等于 8 个 bit。
```

例如：

```text
1 byte = 8 bits
1024 bytes = 1 KB
1024 KB = 1 MB
```

一个字节可以表示：

```text
00000000 到 11111111
```

也就是十进制的 `0` 到 `255`。

### 13.5 UTF-8 为什么不是固定长度

UTF-8 是一种变长编码：

- ASCII 字符通常 1 字节。
- 拉丁字符通常 2 字节。
- 中文常见字符通常 3 字节。
- Emoji 通常 4 字节。

这样既能兼容英文，也能表示全世界字符。

### 13.6 和 JS/TS 对照

```ts
const bytes = new TextEncoder().encode("你好")
// Uint8Array，不是字符串
```

Python 的 `str.encode("utf-8")` 和 JS 的 `TextEncoder` 做的事情类似，都是把文本转成底层字节。
