import json
import math
from pathlib import Path

from app.evaluate import (
    citation_coverage,
    mrr,
    precision_at_k,
    recall_at_k,
)


def load_eval_set(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def ndcg_at_k(
    retrieved_ids: list[str],
    relevant_ids: list[str],
    k: int | None = None,
) -> float:
    k = k or len(retrieved_ids)

    if k <= 0:
        return 0.0

    relevant = set(relevant_ids)

    dcg = sum(
        (1.0 if chunk_id in relevant else 0.0) / math.log2(index + 2)
        for index, chunk_id in enumerate(retrieved_ids[:k])
    )

    ideal_count = min(len(relevant_ids), k)
    ideal_dcg = sum(
        1.0 / math.log2(index + 2)
        for index in range(ideal_count)
    )

    if ideal_dcg == 0:
        return 0.0

    return dcg / ideal_dcg


def answer_keyword_coverage(
    answer: str,
    required_keywords: list[str],
) -> float:
    if not required_keywords:
        return 1.0

    normalized_answer = (answer or "").strip().lower()

    if not normalized_answer:
        return 0.0

    matched = sum(
        1
        for keyword in required_keywords
        if keyword.strip().lower() in normalized_answer
    )

    return matched / len(required_keywords)


def evaluate_rag_end_to_end(
    retriever,
    eval_set: list[dict],
    top_k: int = 3,
    answer_fn=None,
) -> dict:
    recalls = []
    precisions = []
    ndcgs = []
    keyword_coverages = []
    citation_coverages = []
    details = []

    retrieved_ids_list = []
    relevant_ids_list = []

    for case in eval_set:
        query = case.get("query", "")
        relevant_ids = case.get("relevant_chunk_ids", [])
        required_keywords = case.get("required_keywords", [])

        results = retriever.retrieve(query, top_k=top_k)
        retrieved_ids = [
            result["doc"].get("chunk_id", result["doc"].get("id", "unknown"))
            for result in results
        ]

        recall = recall_at_k(retrieved_ids, relevant_ids)
        precision = precision_at_k(retrieved_ids, relevant_ids)
        ndcg = ndcg_at_k(retrieved_ids, relevant_ids, top_k)

        if answer_fn is not None:
            answer = answer_fn(case, results)
        else:
            answer = case.get("reference_answer", "")

        keyword_coverage = answer_keyword_coverage(
            answer,
            required_keywords,
        )
        citation = citation_coverage(answer, retrieved_ids)

        recalls.append(recall)
        precisions.append(precision)
        ndcgs.append(ndcg)
        keyword_coverages.append(keyword_coverage)
        citation_coverages.append(citation)

        retrieved_ids_list.append(retrieved_ids)
        relevant_ids_list.append(relevant_ids)

        details.append(
            {
                "query": query,
                "recall": recall,
                "precision": precision,
                "ndcg": ndcg,
                "keyword_coverage": keyword_coverage,
                "citation_coverage": citation,
                "retrieved_ids": retrieved_ids,
                "relevant_chunk_ids": relevant_ids,
            }
        )

    total = max(len(eval_set), 1)

    return {
        "avg_recall": sum(recalls) / total,
        "avg_precision": sum(precisions) / total,
        "avg_ndcg": sum(ndcgs) / total,
        "avg_keyword_coverage": sum(keyword_coverages) / total,
        "avg_citation_coverage": sum(citation_coverages) / total,
        "avg_mrr": mrr(retrieved_ids_list, relevant_ids_list),
        "details": details,
    }
