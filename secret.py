from pydantic_settings import BaseSettings

class Secrets(BaseSettings):
    reddit_client_id: str
    reddit_client_secret: str
    reddit_user_agent: str
    anthropic_api_key: str
    elevenlabs_api_key: str

    class Config:
        env_file = ".env"

secrets = Secrets()


video_path = "data/bg.mp4"
music_path = "data/music.mp3"