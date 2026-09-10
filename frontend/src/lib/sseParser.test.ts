import { describe, expect, it } from "vitest";
import { parseSSE } from "./sseParser";

describe("parseSSE", () => {
  it("parses a named event with data", () => {
    const result = parseSSE("event: chunk\ndata: 你好\n\n");

    expect(result.events).toEqual([
      {
        event: "chunk",
        data: "你好",
      },
    ]);
    expect(result.remaining).toBe("");
  });

  it("uses message as the default event name", () => {
    const result = parseSSE("data: hello\n\n");

    expect(result.events).toEqual([
      {
        event: "message",
        data: "hello",
      },
    ]);
  });

  it("parses multiple events in one chunk", () => {
    const result = parseSSE(
      "event: chunk\ndata: 你\n\nevent: done\ndata: \n\n",
    );

    expect(result.events).toEqual([
      { event: "chunk", data: "你" },
      { event: "done", data: "" },
    ]);
  });

  it("joins multiple data lines back into one multiline value", () => {
    const result = parseSSE(
      "event: chunk\ndata: 第一行\ndata: 第二行\n\n",
    );

    expect(result.events).toEqual([
      {
        event: "chunk",
        data: "第一行\n第二行",
      },
    ]);
  });

  it("keeps incomplete events in remaining", () => {
    const result = parseSSE("event: chunk\ndata: 你");

    expect(result.events).toEqual([]);
    expect(result.remaining).toBe("event: chunk\ndata: 你");
  });
});