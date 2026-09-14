import argparse

from app.embedding_registry import (
    EMBEDDING_REGISTRY,
    get_embedding_model_name,
    get_embedding_profile,
    load_embedding_model,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", default="rag_chinese")
    parser.add_argument("--model", default=None)
    parser.add_argument("--text", default="AI Agent 需要掌握什么")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()

    if args.list:
        for profile in EMBEDDING_REGISTRY.values():
            print(
                profile.name,
                "|",
                profile.dimension,
                "dims |",
                profile.max_sequence_length,
                "max tokens |",
                profile.latency,
                "latency",
            )
        return 

    model_name = args.model or get_embedding_model_name(args.scenario)
    profile = get_embedding_profile(model_name)
    model = load_embedding_model(model_name)

    vector = model.encode(
        [args.text],
        normalize_embeddings=profile.normalize_embeddings,
    )[0]

    print(f"model={model_name}")
    print(f"provider={profile.provider}")
    print(f"dimension={profile.dimension}")
    print(f"max_sequence_length={profile.max_sequence_length}")
    print(f"normalize_embeddings={profile.normalize_embeddings}")
    print(f"vector_len={len(vector)}")
    print(f"vector_head={vector[:5].tolist()}")

if __name__ == "__main__":
    main()