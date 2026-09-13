from collections import Counter


# 只保留字母和数字，中文也会保留
def normalize_text(text: str) -> str:
    return "".join(char for char in text.lower() if char.isalnum())


# 判断关键词是否出现在输出中
def keyword_coverage(output: str, keywords: list[str]) -> float:
    if not keywords:
        return 1.0

    normalized = normalize_text(output)
    matched = sum(
        1
        for keyword in keywords
        if normalize_text(keyword) in normalized
    )

    return matched / len(keywords)


# 判断更长的必需短语是否出现
def required_phrase_coverage(output: str, phrases: list[str]) -> float:
    if not phrases:
        return 1.0

    normalized = normalize_text(output)
    matched = sum(
        1
        for phrase in phrases
        if normalize_text(phrase) in normalized
    )

    return matched / len(phrases)


# 计算多组输出在某个字段上的多数一致程度
def field_consistency(outputs: list[dict], field: str) -> float:
    if not outputs:
        return 0.0

    values = [
        normalize_text(str(output.get(field, "")))
        for output in outputs
    ]

    _, count = Counter(values).most_common(1)[0]
    return count / len(outputs)


# 汇总所有指标，robustness_rate 表示通过全部检查的输出占比
def evaluate_prompt_batch(
    outputs: list[dict],
    fields: list[str],
    keywords: list[str],
    phrases: list[str] | None = None,
) -> dict:
    if not outputs:
        return {
            "avg_field_consistency": 0.0,
            "avg_keyword_coverage": 0.0,
            "avg_required_phrase_coverage": 0.0,
            "robustness_rate": 0.0,
        }
    
    phrases = phrases or []

    field_scores = [
        field_consistency(outputs, field)
        for field in fields
    ]

    avg_field_consistency = (
        sum(field_scores) / len(field_scores)
        if field_scores
        else 1.0
    )

    keyword_scores = [
        keyword_coverage(output.get("text", ""), keywords)
        for output in outputs
    ]

    phrase_scores = [
        required_phrase_coverage(output.get("text", ""), phrases)
        for output in outputs
    ]

    avg_keyword_coverage = sum(keyword_scores) / len(keyword_scores)
    avg_required_phrase_coverage = sum(phrase_scores) / len(phrase_scores)

    passed_count = sum(
        1
        for output in outputs
        if keyword_coverage(output.get("text", ""), keywords) == 1.0
        and required_phrase_coverage(output.get("text", ""), phrases) == 1.0
    )

    robustness_rate = passed_count / len(outputs)

    return {
        "avg_field_consistency": avg_field_consistency,
        "avg_keyword_coverage": avg_keyword_coverage,
        "avg_required_phrase_coverage": avg_required_phrase_coverage,
        "robustness_rate": robustness_rate,
    }
