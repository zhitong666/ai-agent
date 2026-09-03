import chromadb
import numpy as np

class ChromaStore:
    def __init__(self, persist_dir: str, collection_name: str = "job_knowledge"):
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
            # metadata={"hnsw:space": "cosine"} 让 Chroma 用余弦距离，和我们归一化向量做点积的逻辑一致
        )
    
    # upsert 可以重复调用，会覆盖同 id 的数据
    def upsert(self, chunks: list[dict], embeddings: np.ndarray) -> None:
        self.collection.upsert(
            ids=[chunk["chunk_id"] for chunk in chunks],
            documents=[chunk["text"] for chunk in chunks],
            metadatas=[
                {
                    "doc_id": chunk["doc_id"],
                    "title": chunk["title"],
                    "chunk_index": chunk["chunk_index"],
                }
                for chunk in chunks
            ],
            embeddings=embeddings.tolist(),
        )

    def load_embeddings(self, chunk_ids: list[str]) -> np.ndarray:
        result = self.collection.get(ids=chunk_ids, include=["embeddings"])
        by_id = dict(zip(result["ids"], result["embeddings"]))
        return np.array([by_id[chunk_id] for chunk_id in chunk_ids])

    def query(self, query_embedding: np.ndarray, top_k: int) -> dict:
        return self.collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )