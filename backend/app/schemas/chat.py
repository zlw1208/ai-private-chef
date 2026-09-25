from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class ChatStreamRequest(BaseModel):
    message: str = Field(default="", max_length=2000)
    object_key: str | None = Field(default=None, max_length=1024)
    thread_id: UUID = Field(default_factory=uuid4)

    @model_validator(mode="after")
    def require_message_or_image(self) -> "ChatStreamRequest":
        if not self.message.strip() and not self.object_key:
            raise ValueError("message or object_key is required")
        return self
