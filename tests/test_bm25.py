from app.bm25 import BM25, tokenize


def test_tokenize_chinese_splits_characters_and_bigrams():
    tokens = tokenize("FastAPI 部署")

    assert "fastapi" in tokens
    assert "部" in tokens
    assert "署" in tokens
    assert "部署" in tokens


def test_bm25_scores_documents_containing_query_term_higher():
    bm25 = BM25()
    bm25.fit(["python backend", "docker container", "python docker"])

    scores = bm25.score("docker")

    assert scores[0] == 0
    assert scores[1] > 0
    assert scores[2] > 0
