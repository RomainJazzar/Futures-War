from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    GPU_URL: str = "http://37.26.187.4:8000"
    GPU_TOKEN: str = "tristanlovesia"
    LLM_MODEL: str = "llama3.1:8b"
    LLM_MODEL_FALLBACK: str = "llama3.2:1b"
    IMAGE_MODEL: str = "Tongyi-MAI/Z-Image-Turbo"
    IMAGE_WIDTH: int = 1024
    IMAGE_HEIGHT: int = 1024
    STT_TIMEOUT: float = 30.0
    LLM_TIMEOUT: float = 30.0
    IMAGE_TIMEOUT: float = 90.0

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
