export type SSEEvent = {
    event: string;
    data: string;
};

export type ParsedSSE = {
    events: SSEEvent[];
    remaining: string;
};

export function parseSSE(chunk: string): ParsedSSE {
    const events: SSEEvent[] = [];
    const splitIndex = chunk.lastIndexOf("\n\n");

    if (splitIndex === -1) {
        return { events, remaining: chunk };
    }

    const complete = chunk.slice(0, splitIndex + 2);
    const remaining = chunk.slice(splitIndex + 2);

    for (const block of complete.split("\n\n")) {
        if (!block.trim()) {
            continue;
        }

        let event = "message";
        const dataLines: string[] = [];

        for (const rawLine of block.split("\n")) {
            if (!rawLine || rawLine.startsWith(":")) {
                continue;
            }

            const colonIndex = rawLine.indexOf(":");
            const field = colonIndex === -1 ? rawLine : rawLine.slice(0, colonIndex);
            const value =
                colonIndex === -1 ? "" : rawLine.slice(colonIndex + 1).replace(/^ /, "");

            if (field === "event") {
                event = value;
            } else if (field === "data") {
                dataLines.push(value);
            }
        }

        events.push({
            event,
            data: dataLines.join("\n"),
        });
    }

    return { events, remaining };
}