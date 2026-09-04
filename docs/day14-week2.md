# Day 14 / 第 2 周复盘

日期：2026-09-04

项目：`ai-job-agent`

本周主题：RAG 进阶、记忆、上下文管理。

## 1. 本周做出了什么可以演示的功能

第 2 周在 Day 6 的多步流程基础上，把 RAG 从“能用”推进到了“可评估、可追溯、可多轮对话”。

| 天 | 功能 | 可演示结果 |
|---|---|---|
| Day 8 | 文本切分 | 长文档被切成带 `chunk_id` 的小块，检索能定位到具体 chunk |
| Day 9 | 混合检索 | 向量检索和 BM25 词法检索结合，结果更稳 |
| Day 10 | 向量持久化 | 向量和元数据写入 Chroma，重启不用重新 Embedding |
| Day 11 | 会话记忆 | 同一个 `session_id` 的多轮对话能记住上下文 |
| Day 12 | RAG 引用来源 | `/chat` 返回 `reply` 和 `sources`，回答可追溯 |
| Day 13 | 检索评估 | 用召回率、精确率、MRR 量化检索质量 |
| Day 14 | 项目整合 | 测试、README、联调、复盘和提交 |

一句话总结：

> 现在可以通过 `/chat` 连续提问，系统会用 Chroma 里的向量和 BM25 做混合检索，把命中的来源一起返回，并且能通过评估脚本量化检索效果。

## 2. 掌握了哪些新概念

### 2.1 文本切分

- 固定长度切分、重叠切分、结构化切分。
- `chunk_id`、`doc_id`、`chunk_index` 这些元数据的作用。
- 为什么长文档要先切块再向量化。

### 2.2 改进检索

- BM25 的词法匹配原理：TF、IDF、`k1`、`b`。
- 中文 tokenize 为什么不能只按空格。
- 混合检索为什么要先归一化再加权。
- 重排 CrossEncoder 的作用。

### 2.3 向量库

- Chroma 的 `PersistentClient`、collection、`upsert`、`query`。
- 持久化的意义：重启不重复 Embedding。
- 余弦距离和 L2 距离的区别。

### 2.4 会话记忆

- 短期记忆就是消息列表。
- 模型本身没有记忆，每次靠传 `messages` 恢复上下文。
- `session_id` 和 `Memory`、`SessionStore` 的关系。

### 2.5 RAG 引用来源

- 为什么答案要可追溯。
- `Source` 和 `ChatResponse` 的 Pydantic 嵌套模型。
- 让模型在回答里标注 `[chunk_id]`。

### 2.6 检索评估

- 召回率、精确率、MRR 的公式和含义。
- 评估集和 ground truth 的作用。
- `citation_coverage` 作为答案忠实度的简单代理指标。

## 3. 哪些测试证明了代码正确

当前测试结果：

```text
34 passed
```

主要测试文件：

| 文件 | 证明什么 |
|---|---|
| `test_chunking.py` | 切块数量、重叠、段落切分和元数据正确 |
| `test_bm25.py` | 中文 tokenize 和 BM25 词法打分正确 |
| `test_hybrid.py` | 混合检索返回结构和归一化正确 |
| `test_persistent_retriever.py` | 第一次写入、第二次读取，不重复 Embedding |
| `test_memory.py` | 消息追加和会话隔离正确 |
| `test_chat.py` | 历史消息传回模型、返回 `reply` 和 `sources` |
| `test_evaluate.py` | 召回率、精确率、MRR、引用覆盖率计算正确 |

其他测试文件：

| 文件 | 证明什么 |
|---|---|
| `test_day1.py` | Day 1 的 `parse_text` 正确 |
| `test_api.py` | FastAPI 接口和参数校验正确 |
| `test_llm.py` | function calling 解析正确 |
| `test_rag.py` | 基础向量检索正确 |
| `test_agent.py` | 多步 JD 分析流程正确 |

## 4. 哪些问题还没解决

### 4.1 `data/chroma/` 被 Git 跟踪

`data/chroma/` 是本地生成的二进制索引，不应该提交。应该把 `data/chroma/` 加进 `.gitignore`，避免仓库变得很大、也和本机环境耦合。

### 4.2 答案忠实度只是简单代理

目前 `citation_coverage` 只检查回答里的 `[chunk_id]` 是否在 `sources` 中，不能真正判断答案内容是否被上下文支持。真正做需要 LLM judge 或人工评分。

### 4.3 rerank 还没接入主流程

Day 9 写了 `rerank()`，但 `build_retriever` 和 `/chat` 还没有调用它。后续可以把“混合检索粗排 -> CrossEncoder 精排”串起来。

### 4.4 会话记忆是内存态

`session_store` 只存在内存里，服务重启后会话历史会丢失。真实产品需要把会话存到数据库或 Redis。

### 4.5 评估集太小

`data/eval_set.json` 只有 3 条，而且每个 query 只标一个相关 chunk，导致 precision@3 固定很低。后续要扩充评估集，并加入多标签或 MRR 作为主要指标。

### 4.6 每个新模块都要配套测试

Day 13 的测试一开始漏写了，后来补了 `test_evaluate.py`。记录在这里提醒：以后每完成一个模块，就同步写测试，不要等功能全部写完再补。

## 5. 下周最重要的一个目标是什么

进入第 3 周 Day 1：ReAct 循环。

目标是把当前“检索 + 一次回答”的单轮 Agent，升级为“推理 + 行动”交替执行的多步 Agent。模型会自己判断下一步该调用哪个工具，直到任务完成。

下周第一天要完成的核心能力：

- 实现一个最简单的 ReAct 循环。
- 让模型根据当前状态选择行动。
- 把工具结果放回上下文继续推理。
- 用测试验证多步循环不会死循环。

## 6. 本周记录

本周完成的文档：

- `docs/day8.md`
- `docs/day9.md`
- `docs/day10.md`
- `docs/day11.md`
- `docs/day12.md`
- `docs/day13.md`
- `docs/day14-week2.md`

本周新增或修改的代码模块：

- `app/chunking.py`
- `app/bm25.py`
- `app/vector_store.py`
- `app/rag.py`
- `app/memory.py`
- `app/evaluate.py`
- `app/agent.py`
- `app/main.py`
- `app/models.py`
- `app/rag_cli.py`
- `app/chroma_cli.py`
- `app/eval_cli.py`
