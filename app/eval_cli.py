import argparse
from pathlib import Path

from app.evaluate import evaluate_retrieval, load_eval_set
from app.rag import build_retriever


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--eval-set", default="data/eval_set.json")
    parser.add_argument("--top-k", type=int, default=3)
    args = parser.parse_args()

    retriever = build_retriever(Path("data/knowledge_base.json"))
    eval_set = load_eval_set(Path(args.eval_set))
    report = evaluate_retrieval(retriever, eval_set, top_k=args.top_k)

    print(f"avg_recall@{args.top_k}: {report['avg_recall']:.3f}")
    print(f"avg_precision@{args.top_k}: {report['avg_precision']:.3f}")
    print(f"avg_mrr@{args.top_k}: {report['avg_mrr']:.3f}")

    for detail in report["details"]:
        print(detail["query"])
        print("  recall:", detail["recall"], "precision:", detail["precision"])
        print("  relevant:", detail["relevant_chunk_ids"])
        print("  retrieved:", detail["retrieved_ids"])

if __name__ == "__main__":
    main()