from app.prompt_evaluate import (
    evaluate_prompt_batch,
    field_consistency,
    keyword_coverage,
    normalize_text,
    required_phrase_coverage,
)


def test_normalize_text_removes_spaces_and_punctuation():
    assert normalize_text("Hello, World!") == "helloworld"
    assert normalize_text("AI Agent") == "aiagent"


def test_keyword_coverage_returns_matched_ratio():
    output = "需要掌握 Python 和 RAG"

    assert keyword_coverage(output, ["Python"]) == 1.0
    assert keyword_coverage(output, ["Python", "Docker"]) == 0.5
    assert keyword_coverage(output, []) == 1.0


def test_required_phrase_coverage_uses_normalized_text():
    output = "请先分析岗位，再给出答案"

    assert required_phrase_coverage(output, ["先分析岗位"]) == 1.0
    assert required_phrase_coverage(output, ["先分析", "Docker"]) == 0.5
    assert required_phrase_coverage(output, []) == 1.0


def test_field_consistency_returns_majority_ratio():
    outputs = [
        {"summary": "AI Agent 岗位"},
        {"summary": "AI Agent 岗位"},
        {"summary": "后端岗位"},
    ]

    assert field_consistency(outputs, "summary") == 2 / 3


def test_field_consistency_returns_zero_for_empty_outputs():
    assert field_consistency([], "summary") == 0.0


def test_evaluate_prompt_batch_aggregates_metrics():
    outputs = [
        {
            "summary": "AI Agent 岗位需要掌握 Python 和 RAG。",
            "text": "需要掌握 Python 和 RAG。",
        },
        {
            "summary": "AI Agent 岗位需要掌握 Python 和 RAG。",
            "text": "需要学习 Python 和 RAG。",
        },
    ]

    report = evaluate_prompt_batch(
        outputs,
        fields=["summary"],
        keywords=["Python", "RAG"],
        phrases=["掌握 Python"],
    )

    assert report["avg_field_consistency"] == 1.0
    assert report["avg_keyword_coverage"] == 1.0
    assert report["avg_required_phrase_coverage"] == 0.5
    assert report["robustness_rate"] == 0.5


def test_evaluate_prompt_batch_returns_zero_for_empty_outputs():
    report = evaluate_prompt_batch(
        [],
        fields=["summary"],
        keywords=["Python"],
        phrases=["RAG"],
    )

    assert report["avg_field_consistency"] == 0.0
    assert report["avg_keyword_coverage"] == 0.0
    assert report["avg_required_phrase_coverage"] == 0.0
    assert report["robustness_rate"] == 0.0