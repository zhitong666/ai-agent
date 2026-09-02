def chunk_text_fixed(text: str, chunk_size: int = 80, overlap: int = 16) -> list[str]:
    # overlap 让下一块开头往回退几个字符，避免语义刚好卡在块边界被切断。
    if overlap >= chunk_size:
        raise ValueError("overlap 必须小于 chunk_size")

    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start = end - overlap
    return chunks
    

def chunk_text_by_paragraph(text: str) -> list[str]:
    return [p.strip() for p in text.split("\n") if p.strip()]
    # 真实项目会再对过长的段落按 。 二次切分，这里先保留段落边界即可。

# 把“切块策略”和“元数据生成”收敛到一个函数：
def chunk_documents(documents, strategy="fixed", chunk_size=80, overlap=16):
    chunks = []
    for doc in documents:
        if strategy == "paragraph":
            pieces = chunk_text_by_paragraph(doc["text"])
        else:
            pieces = chunk_text_fixed(doc["text"], chunk_size, overlap)

        for index, piece in enumerate(pieces):
            chunks.append({
                "chunk_id": f"{doc['id']}-{index}",
                "doc_id": doc["id"],
                "title": doc["title"],
                "text": piece,
                "chunk_index": index,
            })
    return chunks
# 这样 RAGRetriever 仍然拿到的是一份 list[dict]，不需要改它内部的 encode 和 retrieve，只要传入的是 chunk 列表即可。