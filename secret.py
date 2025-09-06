from pydantic_settings import BaseSettings

class Secrets(BaseSettings):
    reddit_client_id: str
    reddit_client_secret: str
    reddit_user_agent: str

    class Config:
        env_file = ".env"

secrets = Secrets()
