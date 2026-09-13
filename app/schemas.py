from pydantic import BaseModel, Field


class ClassifyRequest(BaseModel):
    title: str
    channel: str = ""
    description: str = ""
    thumbnail_url: str | None = None
    user_id: str = "default"


class ClassifyResponse(BaseModel):
    category: str | None
    label: str | None
    confidence: float
    focus_score: float = 0.5
    method: str  # "embedding" | "llm" | "cache" | "trusted_channel" | "none"
    used_vision: bool = False
    cached: bool = False


class TrustRequest(BaseModel):
    user_id: str = "default"
    channel: str


class TrustedChannelOut(BaseModel):
    channel: str

    class Config:
        from_attributes = True


class SettingsIn(BaseModel):
    enabled: bool
    allowed_categories: list[str] = Field(default_factory=list)
    debug: bool = False


class SettingsOut(SettingsIn):
    user_id: str

    class Config:
        from_attributes = True
