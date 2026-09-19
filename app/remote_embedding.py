import numpy as np
from openai import OpenAI

from app.config import get_settings


class RemoteEmbeddingModel:
    def __init__(self, model_name: str):
        settings = get_settings()
        self.model_name = model_name
        self.client = OpenAI(
            api_key=settings.remote_embedding_api_key.get_secret_value(),
            base_url=settings.remote_embedding_base_url,
        )

    def encode(
        self,
        texts: list[str] | str,
        normalize_embeddings: bool = True,
        **_kwargs,
    ) -> np.ndarray:
        response = self.client.embeddings.create(
            model=self.model_name,
            input=texts,
        )

        vectors = [item.embedding for item in response.data]
        matrix = np.asarray(vectors, dtype=np.float32)

        if normalize_embeddings:
            norms = np.linalg.norm(matrix, axis=1, keepdims=True)
            norms[norms == 0] = 1
            matrix = matrix / norms

        return matrix