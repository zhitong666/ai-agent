# Day 1 学习笔记

日期：2026-08-16

项目：`ai-job-agent`

目标：完成 Python 环境和语言基础，能独立写一个简单的 `parse_text()`，并用 pytest 验证。

## 1. uv 和 venv 解决了什么问题

### 1.1 venv 解决的问题

Python 项目不能像前端一样每个项目都直接使用全局 `node_modules` 的替代品，如果所有项目共用同一个全局 Python 环境，会出现依赖版本冲突。

例如：

- 项目 A 需要 `openai==1.0.0`
- 项目 B 需要 `openai==2.0.0`

如果都安装到系统 Python，两个项目就会互相影响。

`venv` 会在项目目录下创建一个隔离的虚拟环境：

```text
.venv/
  bin/
  lib/
  pyvenv.cfg
```

安装依赖时，包只进入当前项目的 `.venv`，不会污染系统 Python。

### 1.2 uv 解决的问题

`uv` 可以同时理解为 Python 版的：

- `nvm`，管理 Python 版本
- `npm`，管理项目依赖
- `pnpm`，安装速度快
- `package-lock.json`，通过 `uv.lock` 锁定依赖版本

常用命令：

```bash
uv python install 3.12
uv init --name ai-job-agent --python 3.12
uv add fastapi
uv add --dev pytest
uv run pytest
uv run python app/day1.py
```

本项目本机系统 Python 是 `3.9.6`，比较旧。通过 `uv python install 3.12`，项目可以在不覆盖系统 Python 的情况下使用 `3.12.14`。

### 1.3 相关文件

| 文件 | 作用 |
|---|---|
| `pyproject.toml` | 项目元信息、依赖、构建配置，类似 `package.json` |
| `uv.lock` | 锁定所有依赖的精确版本，类似 lockfile |
| `.python-version` | 指定当前项目使用的 Python 版本 |
| `.venv/` | 项目独立虚拟环境 |

## 2. TypedDict 和 TypeScript interface 的区别

### 2.1 TypeScript interface

TypeScript 的 `interface` 描述对象的静态类型：

```ts
interface ParsedJob {
  company: string
  title: string
}

const job: ParsedJob = {
  company: "字节跳动",
  title: "AI Agent 工程师",
}
```

`interface` 只在 TypeScript 编译期生效，编译成 JavaScript 后会被擦除，运行时不会做任何检查。

### 2.2 Python TypedDict

Python 的 `TypedDict` 也为字典提供类型提示：

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

`TypedDict` 同样主要在静态检查阶段提供提示，Python 运行时不会强制校验字段类型。

### 2.3 关键区别

| 维度 | TypeScript interface | Python TypedDict |
|---|---|---|
| 主要作用 | 静态类型检查 | 类型提示和 IDE 补全 |
| 运行时校验 | 无 | 无 |
| 对应数据 | 对象 | 字典 |
| 更严格的运行时校验方案 | `zod` | `Pydantic` |

第一周后续会用 `Pydantic` 替代 `TypedDict`，因为 LLM 返回的数据需要在运行时严格校验。

## 3. dict 和 list 的常用操作

### 3.1 dict

```python
job = {
    "company": "字节跳动",
    "title": "AI Agent 工程师",
}

# 取值
job["company"]

# 安全取值，键不存在时返回 None
job.get("domain")

# 键不存在时提供默认值
job.get("domain", "unknown")

# 设置值
job["domain"] = "AI 应用"

# 批量更新
job.update({"seniority": "mid"})

# 判断键是否存在
if "company" in job:
    print("has company")

# 遍历键
for key in job:
    print(key)

# 遍历键值对
for key, value in job.items():
    print(key, value)

# 字典推导式
new_job = {key: value for key, value in job.items() if value}
```

### 3.2 list

```python
skills = ["Python", "FastAPI"]

# 追加
skills.append("Docker")

# 合并另一个列表
skills.extend(["Redis", "PostgreSQL"])

# 插入
skills.insert(0, "LLM")

# 访问和切片
skills[0]
skills[-1]
skills[1:3]

# 删除
skills.remove("Redis")
last = skills.pop()

# 判断
"Python" in skills

# 排序
skills.sort()

# 列表推导式
lower_skills = [skill.lower() for skill in skills]
```

### 3.3 对比 TypeScript

| Python | TypeScript |
|---|---|
| `dict[str, str]` | `Record<string, string>` |
| `list[str]` | `string[]` |
| `key in dict` | `key in object` 或 `Object.hasOwn` |
| `[x for x in items if x]` | `items.filter(Boolean)` |

## 4. async/await 的基本用法

### 4.1 什么是异步

Python 的 `async/await` 和 TypeScript 的 `async/await` 概念接近，都表示在等待某个 IO 操作时，不阻塞当前线程。

不同之处是：

- JavaScript 通常天然围绕事件循环工作
- Python 需要显式创建或进入事件循环，例如 `asyncio.run()`

### 4.2 基本例子

```python
import asyncio


async def fetch_name(name: str) -> str:
    await asyncio.sleep(0.1)
    return name


async def main() -> None:
    result = await fetch_name("Agent")
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
```

### 4.3 并发执行多个异步任务

```python
import asyncio


async def fetch_name(name: str) -> str:
    await asyncio.sleep(0.1)
    return name


async def main() -> None:
    results = await asyncio.gather(
        fetch_name("A"),
        fetch_name("B"),
        fetch_name("C"),
    )
    print(results)


if __name__ == "__main__":
    asyncio.run(main())
```

### 4.4 容易犯的错误

异步函数内部不要使用阻塞操作，例如 `time.sleep()`：

```python
import time


async def bad_example() -> None:
    time.sleep(1)
```

这会阻塞整个事件循环。异步代码中应优先使用：

```python
await asyncio.sleep(1)
```

第一周后面会用 FastAPI，所以掌握 `async def`、`await` 和 `asyncio.gather` 已经足够。

## 5. 今天遇到的报错和解决方式

### 5.1 pytest 提示 ModuleNotFoundError: No module named 'app'

错误信息：

```text
E   ModuleNotFoundError: No module named 'app'
```

原因：

pytest 默认会把 `tests/` 目录加入导入路径，但不会自动把项目根目录加入导入路径。因此测试文件执行 `from app.day1 import parse_text` 时，Python 找不到 `app` 包。

解决方法：

在 `pyproject.toml` 中加入：

```toml
[tool.pytest.ini_options]
pythonpath = ["."]
```

这表示把项目根目录加入 Python 导入路径。

### 5.2 pytest 提示 ModuleNotFoundError: No module named 'app.day1'

错误信息：

```text
E   ModuleNotFoundError: No module named 'app.day1'
```

原因：

`pyproject.toml` 配置仍然正确，但 `app/day1.py` 和 `app/__init__.py` 文件被意外撤回或删除。目录中只剩下 `__pycache__` 缓存，无法正常导入。

解决方法：

恢复 `app/__init__.py` 和 `app/day1.py` 源文件，然后重新运行：

```bash
uv run pytest
```

结果：

```text
2 passed
```

### 5.3 终端提示 command not found: uv

如果新开的终端找不到 `uv`，通常是因为安装脚本把 `uv` 放到了 `~/.local/bin`，但当前 shell 还没有重新加载配置。

执行：

```bash
source ~/.zshrc
```

或重新打开终端，然后检查：

```bash
uv --version
```

## 6. Day 1 检查清单

- [x] 使用 uv 安装 Python 3.12
- [x] 初始化 `ai-job-agent` 项目
- [x] 创建 `app` 和 `tests` 目录
- [x] 编写 `parse_text()` 函数
- [x] 编写 pytest 测试
- [x] 配置 pytest 导入路径
- [x] 修复文件丢失问题
- [x] 测试通过

## 7. 明天要做什么

Day 2 开始引入 FastAPI 和 Pydantic，把今天的 `parse_text()` 从普通函数升级为 HTTP API，并通过 Pydantic 定义岗位数据结构。
