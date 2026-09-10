import { FormEvent, useEffect, useRef, useState } from "react";
import { LoaderCircle, Send, Trash2 } from "lucide-react";
import { parseSSE } from "./lib/sseParser";
import "./App.css";

type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  streaming?: boolean;
};

const SESSION_ID = "default";

export default function App() {
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
    };

    setMessages((current) => [...current, userMessage, assistantMessage]);
    setInput("");
    setSending(true);

    try {
      const response = await fetch("/chat/stream", {
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
          if (item.event === "chunk") {
            setMessages((current) =>
              current.map((message) =>
                message.id === assistantId
                  ? { ...message, content: message.content + item.data }
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
    } finally {
      setSending(false);
    }
  }

  return (
    <main className="chat">
      <header className="chat-header">
        <div>
          <p className="eyebrow">AI Job Agent</p>
          <h1>岗位咨询助手</h1>
        </div>
        <button
          className="icon-button"
          type="button"
          aria-label="清空对话"
          onClick={() => setMessages([])}
        >
          <Trash2 size={18} />
        </button>
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
            </div>
          ))
        )}
      </section>

      <form className="composer" onSubmit={handleSubmit}>
        <input
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder="例如：FastAPI 需要掌握什么？"
          disabled={sending}
        />
        <button type="submit" disabled={!input.trim() || sending}>
          {sending ? <LoaderCircle className="spin" size={18} /> : <Send size={18} />}
        </button>
      </form>
    </main>
  );
}