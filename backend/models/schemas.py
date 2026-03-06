from enum import Enum
from pydantic import BaseModel


class Category(str, Enum):
    SE_LOGER = "se_loger"
    SE_DEPLACER = "se_deplacer"
    MANGER = "manger"
    SE_DIVERTIR = "se_divertir"
    ACCES_NATURE = "acces_nature"
    TRAVAILLER = "travailler"


class PipelineResponse(BaseModel):
    image_base64: str
    prompt_original: str
    prompt_enriched: str
    category: str
    source: str  # "speech" or "text"
    generation_time_seconds: float


class HealthResponse(BaseModel):
    status: str
    gpu_server_reachable: bool
    gpu_stats: dict | None = None
