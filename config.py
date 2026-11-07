from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    llm_api_key: str = ""
    llm_model: str = "doubao-seed-2-1-pro-260915"
    llm_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    postgres_uri: str = "postgresql://postgres:123456@localhost:5432/langgraph_db"
    database_url: str = "postgresql+asyncpg://postgres:123456@localhost:5432/langgraph_db"
    jwt_secret: str = "32F34FDSVWAEF23F"

settings = Settings()


