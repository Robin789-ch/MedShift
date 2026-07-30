from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    service: Literal["agent", "optimizer"]
    status: Literal["ok", "error"]
    checks: dict[str, Literal["ok", "error", "not_checked"]]
