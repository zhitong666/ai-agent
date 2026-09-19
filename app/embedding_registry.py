from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

from app.config import get_settings

EmbeddingScenario = Literal[
    "rag_chinese",
    "rag_multilingual",
    "rag_long_documents",
    "rag_low_latency",
]

EmbeddingLatencyTier = Literal["low", "medium", "high"]
QualityTier = Literal["low", "medium", "high"]


class EmbeddingRegistryError(ValueError):
    """Embedding 模型不存在或场景不合法时抛出。"""


@dataclass(frozen=True)
class EmbeddingProfile:
    name: str
    provider: str
    dimension: int # 向量有多少维，直接影响存储和计算成本
    max_sequence_length: int # 单条文本最多处理多少 token，超长会被截断
    supports_chinese: bool
    supports_multilingual: bool # 是否适合多语言混合场景
    normalize_embeddings: bool # 是否需要归一化，用于余弦相似度
    latency: EmbeddingLatencyTier # 响应快慢等级
    quality_tier: QualityTier # 检索质量等级
    languages: tuple[str, ...] = ()


EMBEDDING_REGISTRY: dict[str, EmbeddingProfile] = {
    "BAAI/bge-small-zh-v1.5": EmbeddingProfile(
        name="BAAI/bge-small-zh-v1.5",
        provider="BAAI",
        dimension=512,
        max_sequence_length=512,
        supports_chinese=True,
        supports_multilingual=False,
        normalize_embeddings=True,
        latency="low",
        quality_tier="medium",
        languages=("zh", "en"),
    ),
    "BAAI/bge-m3": EmbeddingProfile(
        name="BAAI/bge-m3",
        provider="BAAI",
        dimension=1024,
        max_sequence_length=8192,
        supports_chinese=True,
        supports_multilingual=True,
        normalize_embeddings=True,
        latency="medium",
        quality_tier="high",
        languages=("multilingual",),
    ),
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2": EmbeddingProfile(
        name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        provider="sentence-transformers",
        dimension=384,
        max_sequence_length=128,
        supports_chinese=True,
        supports_multilingual=True,
        normalize_embeddings=True,
        latency="low",
        quality_tier="low",
        languages=("multilingual",),
    ),
}


LATENCY_ORDER = {
    "low": 0,
    "medium": 1,
    "high": 2,
}

QUALITY_ORDER = {
    "low": 0,
    "medium": 1,
    "high": 2,
}

EMBEDDING_REQUIREMENTS = {
    "rag_chinese": {
        "requires_chinese": True,
        "requires_multilingual": False,
        "min_sequence_length": 256,
        "max_latency": "low",
        "prefer_quality": True,
    },
    "rag_multilingual": {
        "requires_chinese": False,
        "requires_multilingual": True,
        "min_sequence_length": 256,
        "max_latency": "medium",
        "prefer_quality": True,
    },
    "rag_long_documents": {
        "requires_chinese": False,
        "requires_multilingual": False,
        "min_sequence_length": 4096,
        "max_latency": "high",
        "prefer_quality": True,
    },
    "rag_low_latency": {
        "requires_chinese": False,
        "requires_multilingual": False,
        "min_sequence_length": 64,
        "max_latency": "low",
        "prefer_quality": False,
    },
}


def get_embedding_profile(name: str) -> EmbeddingProfile:
    profile = EMBEDDING_REGISTRY.get(name)

    if profile is None:
        raise EmbeddingRegistryError(f"未知 Embedding 模型：{name}")

    return profile


def select_embedding_model(scenario: str) -> str:
    requirements = EMBEDDING_REQUIREMENTS.get(scenario)

    if requirements is None:
        raise EmbeddingRegistryError(f"未知 Embedding 场景：{scenario}")

    candidates = []

    for profile in EMBEDDING_REGISTRY.values():
        if requirements["requires_chinese"] and not profile.supports_chinese:
            continue

        if requirements["requires_multilingual"] and not profile.supports_multilingual:
            continue

        if profile.max_sequence_length < requirements["min_sequence_length"]:
            continue

        if LATENCY_ORDER[profile.latency] > LATENCY_ORDER[requirements["max_latency"]]:
            continue

        candidates.append(profile)


    if not candidates:
        raise EmbeddingRegistryError(f"没有 Embedding 模型满足场景：{scenario}")

    if requirements["prefer_quality"]:
        return min(
            candidates,
            key=lambda profile: (
                -QUALITY_ORDER[profile.quality_tier],
                LATENCY_ORDER[profile.latency],
                profile.dimension,
            ),
        ).name

    return min(
        candidates,
        key=lambda profile: (
            LATENCY_ORDER[profile.latency],
            profile.dimension,
            QUALITY_ORDER[profile.quality_tier],
        ),
    ).name


def get_embedding_model_name(
    scenario: str = "rag_chinese",
    override: str | None = None,
) -> str:
    if override:
        return override
    
    return select_embedding_model(scenario)


@lru_cache(maxsize=8)
def load_embedding_model(name: str):
    settings = get_settings()

    if settings.embedding_provider == "remote":
        from app.remote_embedding import RemoteEmbeddingModel

        return RemoteEmbeddingModel(name)

    from sentence_transformers import SentenceTransformer

    get_embedding_profile(name)
    return SentenceTransformer(name)


