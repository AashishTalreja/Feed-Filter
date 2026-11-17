from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg2://ycf:ycf@localhost:5432/ycf"
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dim: int = 384
    confidence_threshold: float = 0.42  # cosine similarity gate for LLM fallback
    # LLM fallback: any OpenAI-compatible provider (see app/llm.py).
    llm_provider: str = "groq"  # groq | gemini | openai
    llm_api_key: str | None = None
    llm_model: str | None = None  # None -> provider default
    llm_base_url: str | None = None  # None -> provider default
    rag_neighbor_count: int = 3


settings = Settings()
