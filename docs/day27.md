# Day 27 学习笔记

日期：2026-09-11

项目：`ai-job-agent`

目标：给 Agent 增加一个本地可观测性模块，把每次 Agent 运行的工具调用、审批、最终答案、错误和结束事件记录下来，方便后续排查问题和接入 Langfuse / Phoenix 等外部可观测性工具。

## 1. Day 27 做了什么

Day 26 已经能评估 Agent 运行结果。但评估只能告诉我们“整体好还是不好”，不能告诉我们“这次运行中间到底发生了什么”。

Day 27 新增了：

- `app/observability.py`：记录 trace 和事件。
- `tests/test_observability.py`：测试 trace 记录逻辑。
- `app/main.py`：把 `/agent/stream` 包装成可记录 trace 的流。
- `GET /agent/traces/{trace_id}`：按 trace id 查询一次运行记录。

现在一次 Agent 运行会形成一条 trace，里面包含多个事件。

## 2. 今天改了哪些文件

| 文件 | 变化 | 作用 |
|---|---|---|
| `app/observability.py` | 新增 | trace 模型、事件记录、SSE 事件解析 |
| `app/main.py` | 修改 | 把 Agent 流包装成 trace 流，并增加查询接口 |
| `tests/test_observability.py` | 新增 | 验证 trace 记录和导出逻辑 |

## 3. 可观测性里的基础概念

### 3.1 trace

一次完整的 Agent 运行就是一条 trace。

例如用户问：

```text
帮我分析 AI Agent 这个岗位并投递
```

从开始执行到最终结束，这个过程就是一条 trace。

每条 trace 有一个唯一标识：

```text
trace_id
```

在本项目中，`trace_id` 复用了 `/agent/stream` 的 `request_id`。

### 3.2 event

一条 trace 由多个 event 组成。

Day 27 记录的事件：

| 事件 | 含义 |
|---|---|
| `step` | Agent 执行了一个工具 |
| `approval` | Agent 请求用户审批 |
| `answer` | Agent 给出最终答案 |
| `error` | Agent 执行失败 |
| `done` | 流结束 |

### 3.3 为什么要记录时间戳

`TraceEvent` 中包含：

```python
timestamp: str
```

如果没有时间戳，只能知道“发生了什么”，但不知道“哪一步比较慢”。

加上时间戳后，以后可以计算：

```text
第二步开始时间 - 第一步开始时间 = 第一步耗时
```

### 3.4 JSONL 是什么

JSONL 的英文是 JSON Lines。

普通 JSON 是：

```json
[
  {"a": 1},
  {"b": 2}
]
```

JSONL 则是每行一个 JSON 对象：

```json
{"a": 1}
{"b": 2}
```

这样每新增一条 trace，只需要追加一行，不需要重写整个大数组。后续工具读取时也可以一行一行处理，占用内存更少。

## 4. 项目闭环实际流程

```
flowchart TD
    A[浏览器请求 /agent/stream] --> B[FastAPI 生成 request_id]
    B --> C[创建 stream_react_loop 生成器]
    C --> D[trace_stream 包装 Agent 流]
    D --> E[ObservabilityStore.start_trace]
    E --> F[发送 event: trace 给客户端]
    F --> G[逐条读取 Agent SSE 事件]
    G --> H{sse_to_event 解析事件}
    H --> I[记录到 AgentTrace.events]
    I --> J[原样 yield 给客户端]
    J --> G
    G -->|流结束| K[trace 保存在内存中]
    K --> L[可通过 /agent/traces/{trace_id} 查询]
```

实际调用顺序：

1. 浏览器或 curl 请求 `/agent/stream`。
2. FastAPI 生成 `request_id`。
3. FastAPI 先创建 `stream_react_loop()` 生成器。
4. `trace_stream()` 把这个生成器包装起来。
5. `trace_stream()` 先调用 `start_trace()`，创建一条 trace。
6. 然后先发送一个 `event: trace`，让客户端能拿到 `trace_id`。
7. 之后逐条读取 Agent 产生的 SSE 事件。
8. 每条事件先通过 `sse_to_event()` 解析。
9. 解析结果记录到 `AgentTrace.events` 中。
10. 同时把原始 SSE 文本继续发送给客户端。
11. 流结束后，trace 保存在内存里，可通过接口查询。

## 5. 核心代码逐段解释

### 5.1 `TraceEvent`

```python
class TraceEvent(BaseModel):
    event_type: str
    timestamp: str
    data: dict = Field(default_factory=dict)
```

这是单条可观测事件。

- `event_type`：事件类型，例如 `step`。
- `timestamp`：事件发生时间。
- `data`：事件携带的数据。

`Field(default_factory=dict)` 表示每条事件默认拥有一个空字典，避免多个事件共享同一个字典。

### 5.2 `AgentTrace`

```python
class AgentTrace(BaseModel):
    trace_id: str
    question: str
    events: list[TraceEvent] = Field(default_factory=list)
```

这是整条 trace。

- `trace_id`：唯一标识。
- `question`：这次运行的问题。
- `events`：这次运行产生的所有事件。

### 5.3 `ObservabilityStore`

```python
class ObservabilityStore:
    def __init__(self):
        self._traces: dict[str, AgentTrace] = {}
```

`ObservabilityStore` 负责保存所有 trace。

`_traces` 是一个字典：

- key 是 `trace_id`。
- value 是 `AgentTrace`。

这样查找一条 trace 时，时间复杂度是 O(1)，也就是非常快。

### 5.4 `start_trace()`

```python
def start_trace(self, question, trace_id=None):
    trace_id = trace_id or str(uuid.uuid4())
    self._traces[trace_id] = AgentTrace(
        trace_id=trace_id,
        question=question,
    )
    return trace_id
```

`trace_id = trace_id or str(uuid.uuid4())` 的含义是：

- 如果传入了 `trace_id`，就使用传入值。
- 如果没有传，就自动生成一个 UUID。

UUID 是一长串随机字符串，冲突概率非常低。

### 5.5 `record()`

```python
def record(self, trace_id, event_type, **data):
    trace = self._traces.setdefault(
        trace_id,
        AgentTrace(trace_id=trace_id, question=""),
    )
    trace.events.append(
        TraceEvent(
            event_type=event_type,
            timestamp=_now(),
            data=data,
        )
    )
```

`**data` 允许调用时传入任意字段。

例如：

```python
store.record(trace_id, "step", tool="search_knowledge", input="FastAPI")
```

最终事件的数据是：

```python
{"tool": "search_knowledge", "input": "FastAPI"}
```

`setdefault()` 的作用是：

- 如果 `trace_id` 已经存在，就返回它。
- 如果不存在，先创建一个新的 `AgentTrace`，再返回它。

这样可以防止记录事件时找不到 trace。

### 5.6 `event_counts()`

```python
for event in trace.events:
    counts[event.event_type] = counts.get(event.event_type, 0) + 1
```

`counts.get(key, 0)` 表示：

- 如果 `key` 已存在，返回当前数量。
- 如果不存在，返回 `0`。

这样第一次遇到 `step` 时得到 0，再加 1，变成 1。第二次遇到 `step` 时得到 1，再加 1，变成 2。

### 5.7 `export_jsonl()`

```python
def export_jsonl(self, path):
    with path.open("w", encoding="utf-8") as file:
        for trace in self._traces.values():
            file.write(trace.model_dump_json() + "\n")
```

`model_dump_json()` 是 Pydantic 提供的方法，它把对象转成 JSON 字符串。

每写一条 trace，就加一个换行符，形成 JSONL 格式。

### 5.8 `sse_to_event()`

```python
def sse_to_event(raw_event):
    event_name = "message"
    data_lines = []

    for line in raw_event.splitlines():
        if line.startswith("event:"):
            event_name = line.removeprefix("event:").strip()
        elif line.startswith("data:"):
            data_lines.append(line.removeprefix("data:").strip())

    text = "\n".join(data_lines)
```

SSE 文本可能是：

```text
event: step
data: {"tool": "search_knowledge"}
```

这个函数把 `event:` 和 `data:` 分别取出来。

`removeprefix("data:")` 会删除字符串开头的 `data:`，`.strip()` 再删除首尾空格。

### 5.9 `trace_stream()`

```python
def trace_stream(store, question, trace_id, stream):
    store.start_trace(question, trace_id)

    yield f"event: trace\ndata: {trace_id}\n\n"

    for raw_event in stream:
        event_name, data = sse_to_event(raw_event)
        ...
        yield raw_event
```

这里有两个关键点：

1. 先创建 trace。
2. 先输出一个 `trace` 事件，让客户端知道这次运行的 `trace_id`。

然后每读取一条 Agent 事件，就：

- 解析事件。
- 记录到 trace。
- 原样发送给客户端。

这样“记录可观测数据”不会破坏原来的 SSE 输出。

## 6. `app/main.py` 的集成方式

原来 `/agent/stream` 直接返回：

```python
StreamingResponse(
    stream_react_loop(...),
    media_type="text/event-stream",
)
```

Day 27 改成：

```python
stream = stream_react_loop(
    request.question,
    approve_tool_call=approve_tool_call,
    approval_request_id=request_id,
)

return StreamingResponse(
    trace_stream(
        observability_store,
        request.question,
        request_id,
        stream,
    ),
    media_type="text/event-stream",
)
```

还增加了查询接口：

```python
@app.get("/agent/traces/{trace_id}")
def get_agent_trace(trace_id: str):
    trace = observability_store.get_trace(trace_id)

    if trace is None:
        raise HTTPException(status_code=404, detail="trace not found")

    return trace.model_dump()
```

这样运行 Agent 后，可以使用：

```text
GET /agent/traces/{trace_id}
```

查看这次运行。

## 7. 测试文件和用例分析

测试文件是 `tests/test_observability.py`。

| 测试 | 验证内容 |
|---|---|
| `test_start_trace_and_record_event` | 能创建 trace 并记录事件 |
| `test_event_counts` | 能统计不同事件数量 |
| `test_export_jsonl` | 能导出 JSONL 文件 |
| `test_sse_to_event_parses_step` | 能解析 step 事件为字典 |
| `test_sse_to_event_parses_multiline_answer` | 能拼接多行 answer |
| `test_trace_stream_records_events_and_still_yields` | 包装流时能记录事件并继续输出 |

### 7.1 `make_step_event()`

```python
def make_step_event(tool="search_knowledge"):
    return (
        'event: step\n'
        f'data: {{"tool": "{tool}", "input": "FastAPI", '
        '"observation": "ok"}\n\n'
    )
```

这个函数制造一条假 `step` SSE 事件。

测试中不调用真实模型，也不需要网络。这样能快速验证 trace 逻辑是否正确。

### 7.2 `test_export_jsonl()`

```python
path = tmp_path / "traces.jsonl"
store.export_jsonl(path)

lines = path.read_text(encoding="utf-8").strip().splitlines()
payload = json.loads(lines[0])
```

`tmp_path` 是 pytest 自动提供的临时目录。每个测试都会得到一个新的临时目录，不会污染项目文件。

`lines[0]` 是第一行 JSON 文本，`json.loads()` 把它转成 Python 字典。

## 8. 常见报错及原因

### 8.1 `AttributeError: 'str' object has no attribute 'read'`

现象：

```text
app/observability.py:86: in sse_to_event
    data = json.load(text)
AttributeError: 'str' object has no attribute 'read'
```

原因：

`json.load()` 需要读取文件对象，而 `json.loads()` 才用来解析字符串。

这里 `text` 是字符串，所以应该写成：

```python
data = json.loads(text)
```

### 8.2 日志里找不到 trace_id

原因：

`trace_id` 只保存在 `ObservabilityStore` 内存中，原本不会自动打印到终端。

解决方式：

`trace_stream()` 增加了一行：

```python
yield f"event: trace\ndata: {trace_id}\n\n"
```

这样 curl 或前端一开始就能看到：

```text
event: trace
data: 09e672af-3fbc-4d17-bf4f-4a0a787fca90
```

### 8.3 curl 执行到 `approval` 后停住

这是正常现象。

`approval` 事件表示 Agent 正在等待审批。curl 本身不会点击“批准”或“拒绝”。

如果要用 curl 完整测试审批流程，需要在另一个终端执行：

```bash
curl -X POST http://localhost:8000/agent/approve \
  -H "Content-Type: application/json" \
  -d '{"request_id": "09e672af-3fbc-4d17-bf4f-4a0a787fca90", "approved": true}'
```

原来的 `/agent/stream` 请求就会继续。

### 8.4 增加 `event: trace` 后，原测试多了一个事件导致失败

当前测试：

```python
output = list(trace_stream(store, "问题", "trace-4", stream))
assert output == events
```

但 `trace_stream()` 现在会先输出：

```text
event: trace
data: trace-4
```

所以 `output` 会比 `events` 多一条 `trace` 事件，旧断言会失败。

应该把测试改成：

```python
trace_event = f"event: trace\ndata: trace-4\n\n"
assert output == [trace_event, *events]
```

这样测试才符合当前实现。

## 9. 验证记录

Day 27 中，`json.load` 改为 `json.loads` 后：

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_observability.py -q
```

结果：

```text
.....F
5 passed, 1 failed
```

失败原因是上面的“trace 事件导致旧断言不匹配”。修正测试后应全部通过。

真实运行：

```bash
curl -N -X POST http://localhost:8000/agent/stream \
  -H "Content-Type: application/json" \
  -d '{"question": "帮我分析 AI Agent 这个岗位并总结"}'
```

现在响应开头会包含：

```text
event: trace
data: <trace_id>
```

后续 `step`、`answer`、`done` 事件会正常输出，并且这些事件会同步记录到 trace store 中。
