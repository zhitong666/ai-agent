# Day 3 学习笔记

日期：2026-08-16

项目：`ai-job-agent`

目标：把 `/jd/parse` 从固定返回数据改为调用 DeepSeek 真实模型，并通过 JSON 输出和 Pydantic 完成结构化提取。

## 1. Day 3 整体架构

```mermaid
flowchart LR
    A[客户端] -->|POST /jd/parse| B[FastAPI 路由]
    B --> C[ParseRequest 请求体校验]
    C --> D[llm.parse_job_description]
    D --> E[DeepSeek API]
    E --> F[JSON 字符串]
    F --> G[json.loads]
    G --> H[JobDescription Pydantic 校验]
    H --> I[返回 JSON 给客户端]
```

详细流程：

1. 客户端发送 `POST /jd/parse`
2. FastAPI 匹配到 `parse_jd` 函数
3. FastAPI 使用 `ParseRequest` 校验请求体
4. `parse_jd` 调用 `parse_job_description`
5. `parse_job_description` 调用 DeepSeek
6. DeepSeek 返回 JSON 字符串
7. Python 用 `json.loads()` 把字符串转成字典
8. Pydantic 把字典校验并转成 `JobDescription`
9. FastAPI 把 `JobDescription` 转成 JSON 返回

## 2. 今天具体做了什么

### 2.1 安装依赖

```bash
uv add openai python-dotenv
```

- `openai`：使用 DeepSeek 的 OpenAI 兼容接口
- `python-dotenv`：读取 `.env` 环境变量文件

### 2.2 配置 DeepSeek

`.env`：

```text
OPENAI_API_KEY=你的DeepSeek密钥
OPENAI_MODEL=deepseek-chat
OPENAI_BASE_URL=https://api.deepseek.com
```

`.env.example`：

```text
OPENAI_API_KEY=
OPENAI_MODEL=deepseek-chat
OPENAI_BASE_URL=https://api.deepseek.com
```

### 2.3 新增 `app/llm.py`

`app/llm.py` 负责：

- 加载 `.env`
- 创建 OpenAI 客户端
- 定义 Prompt
- 调用 DeepSeek
- 解析 JSON
- 校验为 `JobDescription`

### 2.4 修改 `app/main.py`

`/jd/parse` 不再返回固定数据，改为调用 `parse_job_description`。

### 2.5 新增 mock 测试

`tests/test_llm.py` 用 mock 模拟 DeepSeek 返回，避免测试产生费用。

## 3. 核心代码与解释

### 3.1 加载环境变量

```python
import os

from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
```

解释：

- `import os` 导入 Python 标准库 `os`
- `from dotenv import load_dotenv` 从第三方包导入函数
- `load_dotenv()` 读取项目根目录的 `.env`
- `os.getenv("OPENAI_API_KEY")` 获取环境变量

### 3.2 创建 OpenAI 客户端

```python
from openai import OpenAI

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL"),
)
```

`OpenAI()` 创建客户端对象。由于 DeepSeek 兼容 OpenAI 接口，只需要把 `base_url` 改成 DeepSeek 地址。

### 3.3 调用 DeepSeek

```python
response = client.chat.completions.create(
    model=os.environ["OPENAI_MODEL"],
    messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": jd_text},
    ],
    response_format={"type": "json_object"},
    temperature=0.1,
)
```

解释：

- `client.chat.completions.create()` 发起一次对话补全请求
- `model` 指定模型
- `messages` 是消息列表，系统消息和用户消息都是字典
- `response_format={"type": "json_object"}` 要求模型输出 JSON
- `temperature=0.1` 让输出更稳定

### 3.4 获取模型返回内容

```python
content = response.choices[0].message.content
```

解释：

- `response.choices` 是模型返回的候选结果列表
- `[0]` 表示第一个结果
- `.message` 是消息对象
- `.content` 是消息正文，这里是 JSON 字符串

### 3.5 把字符串转成 Python 字典

```python
import json

data = json.loads(content)
```

`json.loads()` 把 JSON 字符串转换成 Python 字典。

对应 TypeScript：

```ts
const data = JSON.parse(content)
```

### 3.6 用 Pydantic 校验

```python
from app.models import JobDescription

job = JobDescription.model_validate(data)
return job
```

`model_validate()` 会把字典校验并转换成 Pydantic 模型。

## 4. 涉及的 Python 语法

### 4.1 import 和 from import

导入整个模块：

```python
import json
```

从模块导入指定内容：

```python
from app.models import JobDescription
```

对应 TypeScript：

```ts
import { JobDescription } from "./models"
```

### 4.2 函数定义和类型标注

```python
def parse_job_description(jd_text: str) -> JobDescription:
    return job
```

对应 TypeScript：

```ts
function parseJobDescription(jdText: string): JobDescription {
  return job
}
```

### 4.3 字典和列表

`messages` 是列表，每个元素是字典：

```python
messages = [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "..."},
]
```

对应 TypeScript：

```ts
const messages = [
  { role: "system", content: "..." },
  { role: "user", content: "..." },
]
```

### 4.4 os.environ 和 os.getenv

两者都可以读取环境变量：

```python
os.environ["OPENAI_MODEL"]
os.getenv("OPENAI_MODEL")
```

区别：

- `os.environ["KEY"]` 如果键不存在会报 `KeyError`
- `os.getenv("KEY")` 如果键不存在会返回 `None`

### 4.5 json.loads 和 json.dumps

| 函数 | 作用 | TypeScript 对应 |
|---|---|---|
| `json.loads(text)` | 字符串转 Python 对象 | `JSON.parse()` |
| `json.dumps(obj)` | Python 对象转 JSON 字符串 | `JSON.stringify()` |

### 4.6 MagicMock 和 patch

测试中使用 mock 模拟外部服务：

```python
from unittest.mock import MagicMock, patch

fake_response = MagicMock()
fake_response.choices = [fake_choice]

with patch.object(llm.client.chat.completions, "create", return_value=fake_response):
    result = llm.parse_job_description("某 JD 文本")
```

解释：

- `MagicMock` 创建一个假对象
- `patch.object()` 临时替换指定对象的指定属性
- `with` 结束后自动恢复原函数

这类似前端测试中用 Jest mock：

```ts
jest.spyOn(client.chat.completions, "create").mockResolvedValue(fakeResponse)
```

## 5. 测试策略

Day 3 有两个层面的测试：

### 5.1 接口测试

`test_api.py` 只测试 FastAPI 路由和请求体校验，不调用真实模型。

正确做法是 mock `app.main.parse_job_description`：

```python
with patch("app.main.parse_job_description", return_value=fake_job):
    response = client.post("/jd/parse", json={"text": "..."})
```

注意 patch 的路径是 `app.main.parse_job_description`，不是 `app.llm.parse_job_description`。

原因：

```python
from app.llm import parse_job_description
```

这行代码把函数导入到了 `app.main` 命名空间，FastAPI 调用的是 `app.main` 中的引用，所以 mock 必须替换这个引用。

### 5.2 模型调用测试

`test_llm.py` 只测试 `parse_job_description` 的解析逻辑。

它 mock 的是：

```python
llm.client.chat.completions.create
```

让测试不访问网络、不产生 DeepSeek 费用。

## 6. 今天遇到的问题

### 6.1 接口测试期望值过期

失败：

```text
assert '某公司' == '示例公司'
```

原因：

`test_api.py` 还在断言 Day 2 的固定返回 `示例公司`，但 `/jd/parse` 已经改为真实模型，模型会把 `某公司` 解析出来。

解决：

- 在接口测试中 mock `parse_job_description`
- 不要在接口测试里真实调用 DeepSeek

### 6.2 DeepSeek 不支持严格 JSON Schema

DeepSeek 的 `response_format={"type": "json_object"}` 只保证返回合法 JSON 对象，不保证完全符合自定义 Schema。

解决：

- Prompt 中明确字段规则
- 用 Pydantic 做二次校验
- 解析或校验失败时重试

## 7. 没有 Python 语法基础怎么办

你已经有前端经验，所以最好的方法不是从头学 Python，而是用 TypeScript 对照学习。

建议做法：

1. 每天只学当天代码涉及的语法，不追求一次学完 Python
2. 每看到一个不认识的语法，问自己“它在 TypeScript 里等价于什么”
3. 把对应关系写进 `docs/python-notes.md`
4. 每个知识点写一个最小示例并运行
5. 不要只看代码，自己敲一遍，再用 `print()` 观察结果
6. 用 `type()` 查看变量类型
7. 用 `dir()` 查看对象有哪些方法
8. 用 `help()` 查看函数或类说明

例如在终端运行：

```bash
uv run python
```

然后输入：

```python
job = {"company": "字节跳动", "title": "工程师"}
type(job)
dir(job)
help(dict)
```

这比单纯读教程更容易形成记忆。

## 8. 建议创建的 Python 语法对照表

在 `docs/python-notes.md` 中记录：

| 前端概念 | Python 概念 |
|---|---|
| `const obj = {}` | `obj = {}` |
| `JSON.parse()` | `json.loads()` |
| `JSON.stringify()` | `json.dumps()` |
| `import { x } from "./x"` | `from app.x import x` |
| `throw new Error()` | `raise ValueError()` |
| `try/catch` | `try/except` |
| `null/undefined` | `None` |
| `jest.spyOn()` | `unittest.mock.patch()` |

## 9. Day 3 检查清单

- [x] 安装 `openai` 和 `python-dotenv`
- [x] 配置 DeepSeek 环境变量
- [x] 创建 `app/llm.py`
- [x] 修改 `app/main.py`
- [x] 用 3 条 JD 真实测试成功
- [x] 接口测试改为 mock
- [x] `test_llm.py` 通过
- [x] 所有测试通过
- [x] 理解 import、函数、字典、列表、json.loads、Pydantic 校验

## 10. 明天要做什么

Day 4 将学习 DeepSeek 的 function calling，让模型调用 `save_job_description` 工具，而不是直接输出 JSON。
