from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    service: str
    version: str
    environment: str
    llm_provider: str
    llm_configured: bool


class PaperCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    file_name: str = Field(min_length=1, max_length=500)


class PaperResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    file_name: str
    status: str
    created_at: datetime

