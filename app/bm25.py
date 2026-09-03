import math
from collections import Counter


def tokenize(text: str) -> list[str]:
    tokens = []
    for part in text.lower().split():
        has_chinese = any("\u4e00" <= ch <= "\u9fff" for ch in part)
        if has_chinese:
            chars = [ch for ch in part if "\u4e00" <= ch <= "\u9fff"]
            tokens.extend(chars)
            tokens.extend(chars[i] + chars[i + 1] for i in range(len(chars) - 1))
        else:
            tokens.append(part)
    return tokens


# 再实现一个简化版 BM25，fit 建立倒排统计，score 计算每篇文档对 query 的得分
# 说明：k1 控制词频饱和程度，b 控制文档长度惩罚，avg_len 用来归一化不同长度的文档。
class BM25:
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus_tokens = []
        self.doc_freq = Counter()
        self.doc_len = []
        self.avg_len = 0.0
        self.n_docs = 0

    # fit 建立倒排统计
    def fit(self, corpus: list[str]) -> None:
        self.corpus_tokens = [tokenize(text) for text in corpus]
        self.n_docs = len(self.corpus_tokens)
        self.doc_len = [len(tokens) for tokens in self.corpus_tokens]
        self.avg_len = sum(self.doc_len) / max(1, self.n_docs)

        for tokens in self.corpus_tokens:
            for term in set(tokens):
                self.doc_freq[term] += 1

    # score 计算每篇文档对 query 的得分
    def score(self, query: str) -> list[float]:
        query_tokens = tokenize(query)
        scores = []

        for tokens in self.corpus_tokens:
            tf = Counter(tokens)
            doc_len = len(tokens)
            total = 0.0

            for term in query_tokens:
                if term not in tf:
                    continue
                df = self.doc_freq.get(term, 0)
                idf = math.log((self.n_docs - df + 0.5) / (df + 0.5) + 1)
                numerator = tf[term] * (self.k1 + 1)
                denominator = tf[term] + self.k1 * (
                    1 - self.b + self.b * doc_len / self.avg_len
                )
                total += idf * numerator / denominator

            scores.append(total)

        return scores