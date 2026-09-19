import argparse

from app.agent import get_retriever
from app.llm import client
from app.query_rewriter import (
    fallback_rewrite,
    multi_query_retrieve,
    rewrite_query_safe,
)


def print_rewrite_diff(question: str, plan) -> None:
    print("=" * 60)
    print(f"原始问题：{question}")
    print(f"改写问题：{plan.rewritten_query}")
    print("子查询：")

    if plan.sub_queries:
        for index, query in enumerate(plan.sub_queries, start=1):
            print(f"  {index}. {query}")
    else:
        print("  （无）")

    print(f"改写理由：{plan.reason or '（无）'}")
    print("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("question")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--no-rewrite", action="store_true")
    args = parser.parse_args()

    retriever = get_retriever()

    if args.no_rewrite:
        plan = fallback_rewrite(args.question)
    else:
        plan = rewrite_query_safe(client, args.question)

    print_rewrite_diff(args.question, plan)

    results = multi_query_retrieve(
        retriever,
        args.question,
        top_k=args.top_k,
        rewrite_fn=lambda question: plan,
    )

    print("\n检索结果：")

    if not results:
        print("（无结果）")
        return

    for result in results:
        doc = result["doc"]
        print(
            f"{result['score']:.3f} | "
            f"{doc.get('chunk_id')} | "
            f"{doc.get('title')} | "
            f"{doc.get('text')}"
        )


if __name__ == "__main__":
    main()