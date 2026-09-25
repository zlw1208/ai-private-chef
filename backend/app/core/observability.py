import os

from backend.app.core.config import Settings


def configure_langsmith(settings: Settings) -> None:
    os.environ["LANGSMITH_TRACING"] = str(settings.langsmith_tracing).lower()
    os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
    os.environ["LANGSMITH_HIDE_INPUTS"] = str(settings.langsmith_hide_inputs).lower()
    os.environ["LANGSMITH_HIDE_OUTPUTS"] = str(settings.langsmith_hide_outputs).lower()
    if settings.langsmith_api_key is not None:
        api_key = settings.langsmith_api_key.get_secret_value()
        if api_key:
            os.environ["LANGSMITH_API_KEY"] = api_key
