import argparse
import json
from pathlib import Path

from app.chunking import chunk_documents
from app.rag import load_documents


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--knowledge-base", default="data/knowledge_base.json")
    parser.add_argument("--strategy", default="semantic")
    parser.add_argument("--max-chars", type=int, default=120)
    parser.add_argument("--overlap", type=int, default=24)
    args = parser.parse_args()

    documents = load_documents(Path(args.knowledge_base))
    chunks = chunk_documents(
        documents,
        strategy=args.strategy,
        chunk_size=args.max_chars,
        overlap=args.overlap,
    )

    for chunk in chunks:
        print(json.dumps(chunk, ensure_ascii=False))


if __name__ == "__main__":
    main()