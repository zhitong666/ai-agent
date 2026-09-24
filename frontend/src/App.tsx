import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import {
  BookOpen,
  Bot,
  Briefcase,
  Check,
  FileText,
  GitBranch,
  LoaderCircle,
  MessageCircle,
  Network,
  Send,
  Server,
  Trash2,
  Users,
  Workflow,
  X,
} from "lucide-react";
import { LoginDialog } from "./components/LoginDialog";
import { MarkdownMessage } from "./components/MarkdownMessage";
import { QuotaBadge } from "./components/QuotaBadge";
import {
  apiFetch,
  clearSession,
  createGuestSession,
  createId,
  fetchQuota,
  getAccessToken,
  login,
  storeSession,
} from "./lib/api";
import { parseSSE } from "./lib/sseParser";
import type {
  Approval,
  JobAnalysis,
  Message,
  Mode,
  QuotaStatus,
  Step,
} from "./lib/types";
import "./App.css";

type ModeDefinition = {
  id: Mode;
  label: string;
  icon: typeof Bot;
  endpoint: "chat" | "agent" | "jd" | "plan" | "supervisor" | "graph" | "mcp";
};

const MAIN_MODES: ModeDefinition[] = [
  { id: "job", label: "求职 Agent", icon: Bot, endpoint: "agent" },
  { id: "project", label: "知识库", icon: BookOpen, endpoint: "chat" },
  { id: "general", label: "通用问答", icon: MessageCircle, endpoint: "chat" },
  { id: "interview", label: "模拟面试", icon: Users, endpoint: "chat" },
  { id: "resume", label: "简历诊断", icon: FileText, endpoint: "chat" },
  { id: "jd", label: "JD 分析", icon: Briefcase, endpoint: "jd" },
];

const AGENT_MODES: ModeDefinition[] = [
  { id: "plan", label: "Plan", icon: Workflow, endpoint: "plan" },
  { id: "supervisor", label: "Supervisor", icon: Network, endpoint: "supervisor" },
  { id: "graph", label: "Graph", icon: GitBranch, endpoint: "graph" },
  { id: "mcp", label: "MCP", icon: Server, endpoint: "mcp" },
];

const QUICK_PROMPTS: Array<{ mode: Mode; label: string; prompt: string }> = [
  {
    mode: "job",
    label: "分析 AI Agent 岗位",
    prompt: "帮我分析 AI Agent 工程师这个岗位，并说明需要补什么。",
  },
  {
    mode: "general",
    label: "解释 RAG 与 Agent",
    prompt: "请解释 RAG 和 Agent 的区别，并给出一个 FastAPI 示例。",
  },
  {
    mode: "interview",
    label: "开始模拟面试",
    prompt: "我要面试 AI Agent 应用工程师，请开始模拟面试。",
  },
  {
    mode: "resume",
    label: "诊断一段简历",
    prompt: "请帮我诊断简历：我在 FastAPI 和 RAG 项目中有开发经验，但缺乏生产部署和可观测性经验。",
  },
];

const AGENT_MODES_IDS = new Set<Mode>([
  "job",
  "plan",
  "supervisor",
  "graph",
  "mcp",
]);

function formatJobAnalysis(job: JobAnalysis) {
  const lines = [
    "## 岗位概览",
    "",
    job.summary,
    "",
    "### 已具备能力",
    "",
    ...job.matched_skills.map((item) => `- ${item}`),
    "",
    "### 需要补齐",
    "",
    ...job.missing_skills.map((item) => `- ${item}`),
    "",
    "### 可能面试题",
    "",
    ...job.interview_questions.map((item) => `- ${item}`),
    "",
    "### 学习建议",
    "",
    ...job.study_plan.map((item) => `- ${item}`),
  ];

  return lines.join("\n");
}

function placeholderFor(mode: Mode) {
  if (mode === "job") {
    return "例如：帮我分析 AI Agent 岗位并规划学习路径";
  }

  if (mode === "project") {
    return "例如：FastAPI 后端需要掌握什么";
  }

  if (mode === "general") {
    return "可以问 Python、FastAPI、RAG、Agent、Docker 等";
  }

  if (mode === "interview") {
    return "例如：我要面试 AI Agent 应用工程师，请开始";
  }

  if (mode === "resume") {
    return "粘贴简历和岗位 JD，我来诊断";
  }

  if (mode === "jd") {
    return "粘贴一段招聘 JD";
  }

  return "输入一个 AI Agent 相关问题";
}

export default function App() {
  const [authKind, setAuthKind] = useState<"loading" | "guest" | "user">(
    "loading",
  );
  const [quota, setQuota] = useState<QuotaStatus | null>(null);
  const [showLogin, setShowLogin] = useState(false);
  const [mode, setMode] = useState<Mode>("job");
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [sessionId, setSessionId] = useState(`session-${createId()}`);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    listRef.current?.scrollTo({
      top: listRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages]);

  useEffect(() => {
    void initAuth();
  }, []);

  async function refreshQuota() {
    try {
      setQuota(await fetchQuota());
    } catch {
      setQuota(null);
    }
  }

  async function initAuth() {
    if (!getAccessToken()) {
      await switchToGuest();
      return;
    }

    try {
      const status = await fetchQuota();
      setQuota(status);
      setAuthKind(status.authenticated ? "user" : "guest");
    } catch {
      clearSession();
      await switchToGuest();
    }
  }

  async function switchToGuest() {
    const token = await createGuestSession();
    storeSession(token.access_token, "guest");
    setAuthKind("guest");
    await refreshQuota();
  }

  async function handleLogin(username: string, password: string) {
    const token = await login(username, password);
    storeSession(token.access_token, "user");
    setAuthKind("user");
    await refreshQuota();
  }

  async function handleLogout() {
    clearSession();
    resetConversation();
    await switchToGuest();
  }

  function resetConversation(nextMode: Mode = mode) {
    setMessages([]);
    setSessionId(`session-${nextMode}-${createId()}`);
  }

  function changeMode(nextMode: Mode) {
    if (nextMode === mode) {
      return;
    }

    setMode(nextMode);
    resetConversation(nextMode);
  }

  async function submitQuestion(questionOverride?: string) {
    const question = (questionOverride ?? input).trim();

    if (!question || sending || authKind === "loading") {
      return;
    }

    setInput("");

    if (mode === "jd") {
      await submitJd(question);
      return;
    }

    await submitChatOrAgent(question);
  }

  async function submitJd(question: string) {
    const userMessage: Message = {
      id: createId(),
      role: "user",
      content: question,
    };
    const assistantId = createId();
    const assistantMessage: Message = {
      id: assistantId,
      role: "assistant",
      content: "",
      streaming: true,
    };

    setMessages((current) => [...current, userMessage, assistantMessage]);
    setSending(true);

    try {
      const response = await apiFetch("/jd/analyze", {
        method: "POST",
        body: JSON.stringify({ text: question }),
      });

      if (response.status === 401) {
        clearSession();
        await switchToGuest();
        setMessageContent(
          assistantId,
          "登录状态已过期，已切换为游客模式。",
        );
        return;
      }

      if (!response.ok) {
        throw new Error(await readError(response));
      }

      const job = (await response.json()) as JobAnalysis;
      setMessageContent(assistantId, formatJobAnalysis(job));
    } catch (error) {
      setMessageContent(
        assistantId,
        error instanceof Error ? error.message : "请求失败，请稍后重试。",
      );
    } finally {
      setMessageStreaming(assistantId, false);
      setSending(false);
      await refreshQuota();
    }
  }

  async function submitChatOrAgent(question: string) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 120000);

    const definition = [...MAIN_MODES, ...AGENT_MODES].find(
      (item) => item.id === mode,
    )!;
    const userMessage: Message = {
      id: createId(),
      role: "user",
      content: question,
    };
    const assistantId = createId();
    const assistantMessage: Message = {
      id: assistantId,
      role: "assistant",
      content: "",
      streaming: true,
      steps: AGENT_MODES_IDS.has(mode) ? [] : undefined,
      approval: null,
      meta: AGENT_MODES_IDS.has(mode) ? [] : undefined,
    };

    setMessages((current) => [...current, userMessage, assistantMessage]);
    setSending(true);

    const path =
      definition.endpoint === "chat"
        ? "/chat/stream"
        : definition.endpoint === "plan"
          ? "/agent/plan/stream"
          : definition.endpoint === "supervisor"
            ? "/agent/supervisor/stream"
            : definition.endpoint === "graph"
              ? "/agent/graph/stream"
              : definition.endpoint === "mcp"
                ? "/agent/mcp/stream"
                : "/agent/stream";

    const body =
      definition.endpoint === "chat"
        ? { session_id: sessionId, question, scene: mode }
        : { question, scene: "job" };

    try {
      const response = await apiFetch(path, {
        method: "POST",
        body: JSON.stringify(body),
        signal: controller.signal,
      });

      if (response.status === 401) {
        clearSession();
        await switchToGuest();
        setMessageContent(
          assistantId,
          "登录状态已过期，已切换为游客模式。",
        );
        return;
      }

      if (!response.ok || !response.body) {
        throw new Error(await readError(response));
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();

        if (done) {
          break;
        }

        buffer += decoder.decode(value, { stream: true });
        const parsed = parseSSE(buffer);
        buffer = parsed.remaining;

        for (const item of parsed.events) {
          applySseEvent(assistantId, item.event, item.data);
        }
      }
    } catch (error) {
      const message =
        error instanceof DOMException && error.name === "AbortError"
          ? "请求超时，请稍后重试。"
          : error instanceof Error
            ? error.message
            : "请求失败，请稍后重试。";

      setMessageContent(assistantId, message);
    } finally {
      clearTimeout(timeout);
      setMessageStreaming(assistantId, false);
      setSending(false);
      await refreshQuota();
    }
  }

  function applySseEvent(messageId: string, event: string, data: string) {
    if (event === "error") {
      setMessageContent(messageId, data);
      setMessageStreaming(messageId, false);
      return;
    }

    if (event === "chunk") {
      setMessages((current) =>
        current.map((message) =>
          message.id === messageId
            ? { ...message, content: message.content + data }
            : message,
        ),
      );
      return;
    }

    if (event === "answer") {
      setMessageContent(messageId, data);
      return;
    }

    if (event === "step") {
      const step = JSON.parse(data) as Step;

      setMessages((current) =>
        current.map((message) =>
          message.id === messageId
            ? { ...message, steps: [...(message.steps ?? []), step] }
            : message,
        ),
      );
      return;
    }

    if (event === "approval") {
      const approval = JSON.parse(data) as Approval;

      setMessages((current) =>
        current.map((message) =>
          message.id === messageId ? { ...message, approval } : message,
        ),
      );
      return;
    }

    if (event === "done") {
      setMessageStreaming(messageId, false);
      setSending(false);
      return;
    }

    setMessages((current) =>
      current.map((message) =>
        message.id === messageId
          ? {
              ...message,
              meta: [...(message.meta ?? []), { event, data }],
            }
          : message,
      ),
    );
  }

  function setMessageContent(messageId: string, content: string) {
    setMessages((current) =>
      current.map((message) =>
        message.id === messageId ? { ...message, content } : message,
      ),
    );
  }

  function setMessageStreaming(messageId: string, streaming: boolean) {
    setMessages((current) =>
      current.map((message) =>
        message.id === messageId ? { ...message, streaming } : message,
      ),
    );
  }

  async function handleApproval(
    messageId: string,
    approval: Approval,
    approved: boolean,
  ) {
    await apiFetch("/agent/approve", {
      method: "POST",
      body: JSON.stringify({
        request_id: approval.request_id,
        approved,
      }),
    });

    setMessages((current) =>
      current.map((message) =>
        message.id === messageId ? { ...message, approval: null } : message,
      ),
    );
  }

  async function handleFormSubmit(event: FormEvent) {
    event.preventDefault();
    await submitQuestion();
  }

  function handleQuickPrompt(prompt: string, promptMode: Mode) {
    changeMode(promptMode);
    setInput(prompt);
  }

  return (
    <main className="app-shell">
      <header className="app-header">
        <div className="brand">
          <div className="brand-mark">
            <Bot size={22} />
          </div>
          <div>
            <p className="eyebrow">AI Job Agent</p>
            <h1>智能求职与 AI 面试助手</h1>
          </div>
        </div>
        <QuotaBadge
          quota={quota}
          onLogin={() => setShowLogin(true)}
          onLogout={handleLogout}
        />
      </header>

      <nav className="mode-strip" aria-label="功能模式">
        <div className="mode-group">
          {MAIN_MODES.map((item) => {
            const Icon = item.icon;

            return (
              <button
                key={item.id}
                type="button"
                className={mode === item.id ? "active" : ""}
                onClick={() => changeMode(item.id)}
              >
                <Icon size={16} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </div>
        <div className="mode-group">
          {AGENT_MODES.map((item) => {
            const Icon = item.icon;

            return (
              <button
                key={item.id}
                type="button"
                className={mode === item.id ? "active" : ""}
                onClick={() => changeMode(item.id)}
              >
                <Icon size={16} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </div>
      </nav>

      {messages.length === 0 ? (
        <section className="quick-strip">
          {QUICK_PROMPTS.map((item) => (
            <button
              key={item.label}
              type="button"
              onClick={() => handleQuickPrompt(item.prompt, item.mode)}
            >
              {item.label}
            </button>
          ))}
        </section>
      ) : null}

      <section ref={listRef} className="message-list">
        {messages.length === 0 ? (
          <div className="empty-state">
            选择一个场景，或使用上方示例开始。
          </div>
        ) : (
          messages.map((message) => (
            <div
              key={message.id}
              className={`message ${message.role} ${
                message.streaming ? "streaming" : ""
              }`}
            >
              {message.role === "assistant" ? (
                <MarkdownMessage content={message.content} />
              ) : (
                <p className="plain-message">{message.content}</p>
              )}

              {message.steps?.length ? (
                <ul className="steps">
                  {message.steps.map((step, index) => (
                    <li className="step" key={`${step.tool}-${index}`}>
                      <strong>{step.tool}</strong>
                      <span>{step.input}</span>
                      <small>{step.observation}</small>
                    </li>
                  ))}
                </ul>
              ) : null}

              {message.meta?.length ? (
                <div className="trace-panel">
                  {message.meta.map((item, index) => (
                    <div className="trace-row" key={`${item.event}-${index}`}>
                      <code>{item.event}</code>
                      <span>{item.data}</span>
                    </div>
                  ))}
                </div>
              ) : null}

              {message.approval ? (
                <div className="approval">
                  <span>是否批准 {message.approval.tool}？</span>
                  <div className="approval-actions">
                    <button
                      type="button"
                      title="批准"
                      onClick={() =>
                        handleApproval(message.id, message.approval!, true)
                      }
                    >
                      <Check size={16} />
                    </button>
                    <button
                      type="button"
                      title="拒绝"
                      onClick={() =>
                        handleApproval(message.id, message.approval!, false)
                      }
                    >
                      <X size={16} />
                    </button>
                  </div>
                </div>
              ) : null}
            </div>
          ))
        )}
      </section>

      <form className="composer" onSubmit={handleFormSubmit}>
        <input
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder={placeholderFor(mode)}
          disabled={sending || authKind === "loading"}
        />
        <button
          type="button"
          className="icon-button"
          title="清空对话"
          onClick={() => resetConversation()}
        >
          <Trash2 size={18} />
        </button>
        <button type="submit" disabled={!input.trim() || sending}>
          {sending ? (
            <LoaderCircle className="spin" size={18} />
          ) : (
            <Send size={18} />
          )}
        </button>
      </form>

      {showLogin ? (
        <LoginDialog
          onClose={() => setShowLogin(false)}
          onLogin={handleLogin}
        />
      ) : null}
    </main>
  );
}

async function readError(response: Response) {
  const body = await response.json().catch(() => null);
  return body?.detail || "请求失败";
}
