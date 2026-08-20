import argparse
from pathlib import Path

from app.rag import build_retriever

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("query")
    args = parser.parse_args()

    retriever = build_retriever(Path("data/knowledge_base.json"))

    for result in retriever.retrieve(args.query, top_k=3):
        doc = result["doc"]
        score = result["score"]
        print(f"{score:.3f} | {doc['id']} | {doc['title']}")

if __name__ == "__main__":
    main()