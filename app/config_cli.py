import argparse
import secrets

from app.config import get_settings


def _secret_label(secret) -> str:
    try:
        return "***" if secret.get_secret_value() else "<missing>"
    except Exception:
        return "<missing>"


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Job Agent 配置工具")
    parser.add_argument(
        "command",
        choices=["check", "show", "generate-secret"],
        help="check: 验证配置；show: 查看非敏感配置；generate-secret: 生成 JWT 密钥",
    )
    args = parser.parse_args()

    if args.command == "check":
        settings = get_settings()
        print(f"config ok: environment={settings.environment}")

    elif args.command == "show":
        settings = get_settings()
        print(f"environment={settings.environment}")
        print(f"debug={settings.debug}")
        print(f"openai_model={settings.openai_model}")
        print(f"openai_base_url={settings.openai_base_url}")
        print(f"openai_api_key={_secret_label(settings.openai_api_key)}")
        print(f"llm_max_concurrency={settings.llm_max_concurrency}")
        print(f"database_url_configured={bool(settings.database_url)}")
        print(f"redis_url={settings.redis_url}")
        print(f"jwt_secret={_secret_label(settings.jwt_secret)}")
        print(f"jwt_algorithm={settings.jwt_algorithm}")
        print(f"jwt_expire_minutes={settings.jwt_expire_minutes}")
        print(f"embedding_model={settings.embedding_model}")
        print(f"vector_store={settings.vector_store}")
        print(f"qdrant_url={settings.qdrant_url}")
        print(f"rerank_enabled={settings.rerank_enabled}")
        print(f"candidate_top_k={settings.candidate_top_k}")
        print(f"hybrid_alpha={settings.hybrid_alpha}")
        print(f"hf_endpoint={settings.hf_endpoint}")
        print(f"hf_home={settings.hf_home}")

    elif args.command == "generate-secret":
        print(secrets.token_urlsafe(48))


if __name__ == "__main__":
    main()