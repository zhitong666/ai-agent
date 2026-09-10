from asyncio import run

from app import streaming


def test_sse_event_uses_message_event_by_default():
    assert streaming.sse_event(None, "hello") == "data: hello\n\n"


def test_sse_event_includes_named_event():
    assert streaming.sse_event("chunk", "hello") == "event: chunk\ndata: hello\n\n"


def test_sse_event_splits_multiline_payload():
    assert streaming.sse_event("chunk", "第一行\n第二行") == (
        "event: chunk\n"
        "data: 第一行\n"
        "data: 第二行\n\n"
    )


def test_text_chunk_stream_emits_chunks_then_done_event():
    async def collect():
        return [
            item
            async for item in streaming.text_chunk_stream(
                "abcdef",
                chunk_size=2,
            )
        ]

    events = run(collect())

    assert events == [
        streaming.sse_event("chunk", "ab"),
        streaming.sse_event("chunk", "cd"),
        streaming.sse_event("chunk", "ef"),
        streaming.sse_event("done", ""),
    ]