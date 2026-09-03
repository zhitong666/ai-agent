# 用来验证“重启后不用重新 Embedding”。逻辑和 rag_cli.py 类似，但可以直接调用 store.query 观察 Chroma 的结果
from pathlib import Path
from app.rag import build_retriever


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("query")
    args = parser.parse_args()

    retriever = build_retriever(Path("data/knowledge_base.json"))

    for result in retriever.retrieve(args.query, top_k=5):
        doc = result["doc"]
        score = result["score"]
        print(f"{score:.3f} | {doc['chunk_id']} | {doc['title']} | {doc['text']}")


if __name__ == "__main__":
    main()