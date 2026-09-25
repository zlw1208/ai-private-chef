from typing import Any, TypedDict


class RecognitionState(TypedDict, total=False):
    object_key: str
    user_text: str
    recognition: dict[str, Any]
