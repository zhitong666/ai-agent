import argparse
from pathlib import Path

from app.rag import build_retriever
from app.rag_evaluate import evaluate_rag_end_to_end, load_eval_set


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--eval-set", default="data/rag_eval_set.json")
    parser.add_argument("--top-k", type=int, default=3)
    args = parser.parse_args()

    retriever = build_retriever(Path("data/knowledge_base.json"))
    eval_set = load_eval_set(Path(args.eval_set))

    report = evaluate_rag_end_to_end(
        retriever,
        eval_set,
        top_k=args.top_k,
    )

    print(f"avg_recall@{args.top_k}: {report['avg_recall']:.3f}")
    print(f"avg_precision@{args.top_k}: {report['avg_precision']:.3f}")
    print(f"avg_ndcg@{args.top_k}: {report['avg_ndcg']:.3f}")
    print(f"avg_mrr@{args.top_k}: {report['avg_mrr']:.3f}")
    print(f"avg_keyword_coverage: {report['avg_keyword_coverage']:.3f}")
    print(f"avg_citation_coverage: {report['avg_citation_coverage']:.3f}")

    print("\n明细：")
    for detail in report["details"]:
        print(detail["query"])
        print("  recall:", detail["recall"])
        print("  precision:", detail["precision"])
        print("  ndcg:", detail["ndcg"])
        print("  retrieved:", detail["retrieved_ids"])
        print("  relevant:", detail["relevant_chunk_ids"])


if __name__ == "__main__":
    main()