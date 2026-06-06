from __future__ import annotations

from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: str = Field(alias="BOT_TOKEN")
    admin_ids: List[int] = Field(default_factory=list, alias="ADMIN_IDS")

    qr_default_fg: str = Field(default="#000000", alias="QR_DEFAULT_FG")
    qr_default_bg: str = Field(default="#FFFFFF", alias="QR_DEFAULT_BG")
    qr_box_size: int = Field(default=10, alias="QR_BOX_SIZE")
    qr_border: int = Field(default=4, alias="QR_BORDER")

    @field_validator("admin_ids", mode="before")
    @classmethod
    def parse_admin_ids(cls, value):
        if value is None or value == "":
            return []
        if isinstance(value, int):
            return [value]
        if isinstance(value, str):
            return [int(part.strip()) for part in value.split(",") if part.strip()]
        return value


def load_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
