import json
from pathlib import Path
import re


def load_eval_set(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def recall_at_k(retrieved_ids: list[str], relevant_ids: list[str]) -> float:
    if not relevant_ids:
        return 0.0
    relevant = set(relevant_ids)
    return len(relevant & set(retrieved_ids)) / len(relevant)


def precision_at_k(retrieved_ids: list[str], relevant_ids: list[str]) -> float:
    if not retrieved_ids:
        return 0.0
    relevant = set(relevant_ids)
    return len(relevant & set(retrieved_ids)) / len(retrieved_ids)
    # set 求交集得到“既是相关又检索到”的 chunk 数量。召回率除以“相关总数”，精确率除以“检索数量” 


def mrr(retrieved_ids_list: list[list[str]], relevant_ids_list: list[list[str]]) -> float:
    if not retrieved_ids_list:
        return 0.0

    scores = []

    for retrieved_ids, relevant_ids in zip(retrieved_ids_list, relevant_ids_list):
        relevant = set(relevant_ids)
        for index, chunk_id in enumerate(retrieved_ids, start=1):
            if chunk_id in relevant:
                scores.append(1 / index)
                break
        else:
            scores.append(0.0)
                
    return sum(scores) / len(scores)


def evaluate_retrieval(retriever, eval_set: list[dict], top_k: int = 3) -> dict:
    recalls = []
    precisions = []
    details = []
    retrieved_ids_list = []
    relevant_ids_list = []

    for case in eval_set:
        results = retriever.retrieve(case["query"], top_k=top_k)
        retrieved_ids = [result["doc"]["chunk_id"] for result in results]
        relevant_ids = case["relevant_chunk_ids"]

        recall = recall_at_k(retrieved_ids, relevant_ids)
        precision = precision_at_k(retrieved_ids, relevant_ids)

        recalls.append(recall)
        precisions.append(precision)
        retrieved_ids_list.append(retrieved_ids)
        relevant_ids_list.append(relevant_ids)

        details.append(
            {
                "query": case["query"],
                "recall": recall,
                "precision": precision,
                "retrieved_ids": retrieved_ids,
                "relevant_chunk_ids": relevant_ids,
            }
        )
    
    return {
        "avg_recall": sum(recalls) / len(recalls),
        "avg_precision": sum(precisions) / len(precisions),
        "avg_mrr": mrr(retrieved_ids_list, relevant_ids_list),
        "details": details,
    }


def citation_coverage(reply: str, source_ids: list[str]) -> float:
    cited = re.findall(r"\[([A-Za-z0-9_-]+)\]", reply)
    if not cited:
        return 0.0

    valid = set(source_ids)
    matched = [chunk_id for chunk_id in cited if chunk_id in valid]
    return len(matched) / len(cited)
    # 如果模型回答里引用了 [doc-fastapi-0]，而 sources 里有这个 id，就认为引用一致。这个指标不是真正的语义忠实度，但作为初学者理解“评估回答”已经足够

