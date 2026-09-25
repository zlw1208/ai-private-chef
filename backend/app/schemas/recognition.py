from typing import Annotated
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class Ingredient(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name_zh: str = Field(description="食材的简洁中文名称")
    quantity_estimate: str = Field(description="图片可见数量或大致份量")
    visible_state: str = Field(description="食材当前可见状态")
    confidence: Annotated[float, Field(ge=0, le=1, description="识别置信度")]


class IngredientRecognition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_food_image: bool = Field(description="图片是否包含可辨认的食材或食品")
    summary: str = Field(description="对图片内容的一句简短中文概括")
    ingredients: list[Ingredient] = Field(description="图片中清晰可见的食材")
    possible_non_food_items: list[str] = Field(description="可能被误认为食材的非食品物品")
    uncertainty_note: str = Field(description="识别不确定性的简短说明，没有则为空字符串")


class RecognitionRequest(BaseModel):
    object_key: str = Field(min_length=1, max_length=512)
    user_text: str = Field(default="", max_length=1000)
    thread_id: UUID = Field(default_factory=uuid4)


class RecognitionResponse(BaseModel):
    thread_id: UUID
    object_key: str
    recognition: IngredientRecognition

