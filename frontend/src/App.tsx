import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { Check, LoaderCircle, Send, Trash2, X } from "lucide-react";
import { parseSSE } from "./lib/sseParser";
import "./App.css";

type Mode = "chat" | "agent";

type Step = {
  tool: string;
  input: string;
  observation: string;
};

type Approval = {
  request_id: string;
  tool: string;
  arguments: Record<string, string>;
};

type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  streaming?: boolean;
  steps?: Step[];
  approval?: Approval | null;
};

const SESSION_ID = "default";

export default function App() {
  const [mode, setMode] = useState<Mode>("agent");
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    listRef.current?.scrollTo({
      top: listRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();

    const question = input.trim();

    if (!question || sending) {
      return;
    }

    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: question,
    };

    const assistantId = crypto.randomUUID();
    const assistantMessage: Message = {
      id: assistantId,
      role: "assistant",
      content: "",
      streaming: true,
      steps: mode === "agent" ? [] : undefined,
      approval: null,
    };

    setMessages((current) => [...current, userMessage, assistantMessage]);
    setInput("");
    setSending(true);

    const endpoint = mode === "chat" ? "/chat/stream" : "/agent/stream";

    try {
      const response = await fetch(endpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          session_id: SESSION_ID,
          question,
        }),
      });

      if (!response.ok || !response.body) {
        throw new Error("请求失败");
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
        const { events, remaining } = parseSSE(buffer);
        buffer = remaining;

        for (const item of events) {
          if (item.event === "error") {
            setMessages((current) =>
              current.map((message) =>
                message.id === assistantId
                  ? {
                      ...message,
                      content: message.content || item.data,
                      streaming: false,
                      approval: null,
                    }
                  : message,
              ),
            );
          }

          if (item.event === "chunk") {
            setMessages((current) =>
              current.map((message) =>
                message.id === assistantId
                  ? { ...message, content: message.content + item.data }
                  : message,
              ),
            );
          }

          if (item.event === "answer") {
            setMessages((current) =>
              current.map((message) =>
                message.id === assistantId
                  ? { ...message, content: item.data }
                  : message,
              ),
            );
          }

          if (item.event === "step") {
            const step = JSON.parse(item.data) as Step;

            setMessages((current) =>
              current.map((message) =>
                message.id === assistantId
                  ? {
                      ...message,
                      steps: [...(message.steps ?? []), step],
                    }
                  : message,
              ),
            );
          }

          if (item.event === "approval") {
            const approval = JSON.parse(item.data) as Approval;

            setMessages((current) =>
              current.map((message) =>
                message.id === assistantId
                  ? { ...message, approval }
                  : message,
              ),
            );
          }

          if (item.event === "done") {
            setMessages((current) =>
              current.map((message) =>
                message.id === assistantId
                  ? { ...message, streaming: false }
                  : message,
              ),
            );
          }
        }
      }
    } catch (error) {
      setMessages((current) =>
        current.map((message) =>
          message.id === assistantId
            ? {
                ...message,
                content:
                  error instanceof Error ? error.message : "请求失败，请稍后重试。",
                streaming: false,
              }
            : message,
        ),
      );
    } finally {
      setSending(false);
    }
  }

  async function handleApproval(
    messageId: string,
    approval: Approval,
    approved: boolean,
  ) {
    await fetch("/agent/approve", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
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

  return (
    <main className="chat">
      <header className="chat-header">
        <div>
          <p className="eyebrow">AI Job Agent</p>
          <h1>岗位咨询助手</h1>
        </div>
        <div className="mode-switch">
          <button
            type="button"
            className={mode === "chat" ? "active" : ""}
            title="使用知识库问答"
            onClick={() => setMode("chat")}
          >
            问答
          </button>
          <button
            type="button"
            className={mode === "agent" ? "active" : ""}
            title="使用 Agent 自动调用工具"
            onClick={() => setMode("agent")}
          >
            Agent
          </button>
          <button
            className="icon-button"
            type="button"
            aria-label="清空对话"
            title="清空对话"
            onClick={() => setMessages([])}
          >
            <Trash2 size={18} />
          </button>
        </div>
      </header>

      <section ref={listRef} className="message-list">
        {messages.length === 0 ? (
          <div className="empty-state">
            输入一个岗位相关问题开始对话。
          </div>
        ) : (
          messages.map((message) => (
            <div
              key={message.id}
              className={`message ${message.role} ${
                message.streaming ? "streaming" : ""
              }`}
            >
              <p>{message.content}</p>

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

              {message.approval ? (
                <div className="approval">
                  <span>
                    是否批准 {message.approval.tool}？
                  </span>
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

      <form className="composer" onSubmit={handleSubmit}>
        <input
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder="例如：帮我分析这个岗位并投递"
          disabled={sending}
        />
        <button type="submit" disabled={!input.trim() || sending}>
          {sending ? <LoaderCircle className="spin" size={18} /> : <Send size={18} />}
        </button>
      </form>
    </main>
  );
}
