from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class RootResponse(BaseModel):
    name: str
    version: str
    docs_url: str
    health_url: str


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    environment: str
    version: str
    timestamp: datetime

