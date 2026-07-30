from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit


@dataclass(frozen=True)
class Settings:
    openrouter_api_key: str
    openrouter_model: str
    optimizer_url: str
    workspace_path: Path
    model_timeout_seconds: float
    optimizer_timeout_seconds: float
    log_level: str

    @classmethod
    def from_environ(cls, environ: Mapping[str, str]) -> "Settings":
        optimizer_url = environ["OPTIMIZER_URL"].rstrip("/")
        parsed_optimizer_url = urlsplit(optimizer_url)
        if parsed_optimizer_url.scheme not in {"http", "https"} or not parsed_optimizer_url.netloc:
            raise ValueError("OPTIMIZER_URL must be an absolute HTTP URL")

        workspace_path = Path(environ["WORKSPACE_PATH"])
        if not workspace_path.is_absolute():
            raise ValueError("WORKSPACE_PATH must be absolute")

        model_timeout_seconds = _positive_float(
            environ["MODEL_TIMEOUT_SECONDS"],
            "MODEL_TIMEOUT_SECONDS",
        )
        optimizer_timeout_seconds = _positive_float(
            environ["OPTIMIZER_TIMEOUT_SECONDS"],
            "OPTIMIZER_TIMEOUT_SECONDS",
        )

        log_level = environ["LOG_LEVEL"].upper()
        if log_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("LOG_LEVEL is invalid")

        return cls(
            openrouter_api_key=environ["OPENROUTER_API_KEY"],
            openrouter_model=environ["OPENROUTER_MODEL"],
            optimizer_url=optimizer_url,
            workspace_path=workspace_path,
            model_timeout_seconds=model_timeout_seconds,
            optimizer_timeout_seconds=optimizer_timeout_seconds,
            log_level=log_level,
        )


def _positive_float(value: str, name: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise ValueError(f"{name} must be positive")
    return parsed
