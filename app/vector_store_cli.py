import argparse

from app.vector_store import build_vector_store


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--store", default="chroma")
    parser.add_argument("--collection-name", default="job_knowledge")
    parser.add_argument("--dimension", type=int, default=512)
    parser.add_argument("--persist-dir", default="data/chroma")
    parser.add_argument("--qdrant-url", default="http://localhost:6333")
    args = parser.parse_args()

    store = build_vector_store(
        store_type=args.store,
        collection_name=args.collection_name,
        dimension=args.dimension,
        persist_dir=args.persist_dir,
        qdrant_url=args.qdrant_url,
    )

    print(f"store_type={args.store}")
    print(f"collection_name={args.collection_name}")
    print(f"store_class={type(store).__name__}")


if __name__ == "__main__":
    main()