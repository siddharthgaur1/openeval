from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://openeval:openeval@localhost:5432/openeval"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "change-me-in-prod"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24
    # Defaults to a local Ollama model so a fresh install never calls a paid API by accident.
    judge_model: str = "ollama/llama3"
    rate_limit_per_minute: int = 120

    class Config:
        env_file = ".env"


settings = Settings()
